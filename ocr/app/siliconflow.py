from __future__ import annotations

import asyncio
import base64
import json
import random
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from .config import Settings
from .policy import FreePolicy, PolicyViolation
from .storage import BudgetExceeded, ChunkCache, JobBudget

PIPELINE_VERSION = "soran-ocr-v1"

PROMPT_TEXT = "<image>\nFree OCR."
PROMPT_MARKDOWN = "<image>\n<|grounding|>Convert the document to markdown."
PROMPT_REVIEW = (
    "请逐字识别图片中的全部文字，严格保持原始阅读顺序、换行和标点。"
    "只输出识别结果，不要总结、翻译、改写、补全或添加商品卖点。"
    "无法辨认的字符请保留可辨认部分并用 ⟦UNCERTAIN⟧ 标记，禁止猜测。"
    "<image>"
)


class OCRRequestError(RuntimeError):
    def __init__(self, message: str, attempts: int = 0, status_code: int | None = None):
        super().__init__(message)
        self.attempts = attempts
        self.status_code = status_code


class AuthError(OCRRequestError):
    pass


class PaymentRejectedError(OCRRequestError):
    pass


@dataclass
class OCRResponse:
    text: str
    raw_text: str
    usage: dict[str, Any] | None
    latency_ms: int
    from_cache: bool
    cache_key: str
    model: str
    attempts: int = 1
    finish_reason: str | None = None
    truncated: bool = False
    request_id: str | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def build_prompt(model: str, mode: str, review_model: str) -> str:
    if model == review_model:
        return PROMPT_REVIEW
    return PROMPT_MARKDOWN if mode == "markdown" else PROMPT_TEXT


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


class SiliconFlowOCRClient:
    def __init__(
        self,
        settings: Settings,
        policy: FreePolicy,
        cache: ChunkCache,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.settings = settings
        self.policy = policy
        self.cache = cache
        self._transport = transport
        self._semaphore = asyncio.Semaphore(max(1, settings.max_concurrent_requests))
        self._interval_lock = asyncio.Lock()
        self._last_request_at = 0.0

    def _headers(self) -> dict[str, str]:
        key = self.settings.api_key_value
        if not key:
            raise AuthError(
                "未配置 SILICONFLOW_API_KEY，无法调用云端 OCR。请在 .env 或环境变量中配置。"
            )
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _payload(self, model: str, image_bytes: bytes, mime: str, prompt: str) -> dict[str, Any]:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{encoded}",
                                "detail": "high",
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "stream": False,
            "temperature": 0,
            "top_p": 1,
            "max_tokens": self.settings.max_output_tokens,
        }

    async def _throttle(self) -> None:
        if self.settings.request_min_interval_ms <= 0:
            return
        async with self._interval_lock:
            now = time.monotonic()
            wait = (self.settings.request_min_interval_ms / 1000) - (now - self._last_request_at)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_at = time.monotonic()

    async def list_models(self) -> list[str]:
        headers = self._headers()
        async with httpx.AsyncClient(
            transport=self._transport,
            timeout=httpx.Timeout(30.0, connect=10.0),
            base_url=self.settings.siliconflow_base_url,
        ) as client:
            response = await client.get("/models", headers=headers)
            response.raise_for_status()
            payload = response.json()
            return [item.get("id", "") for item in payload.get("data", [])]

    async def ocr_chunk(
        self,
        *,
        model: str,
        image_bytes: bytes,
        mime: str,
        mode: str,
        budget: JobBudget,
        allow_cache: bool = True,
    ) -> OCRResponse:
        prompt = build_prompt(model, mode, self.settings.review_model)
        cache_key = self.cache.key(image_bytes, model, prompt, mode, PIPELINE_VERSION)
        if allow_cache:
            cached = self.cache.get(cache_key)
            if cached:
                budget.cache_hits += 1
                return OCRResponse(
                    text=cached.get("text", ""),
                    raw_text=cached.get("raw_text", cached.get("text", "")),
                    usage=cached.get("usage"),
                    latency_ms=int(cached.get("latency_ms", 0)),
                    from_cache=True,
                    cache_key=cache_key,
                    model=model,
                    attempts=0,
                    finish_reason=cached.get("finish_reason"),
                    truncated=bool(cached.get("truncated")),
                    metadata={"source": "cache"},
                )

        # Fail closed before any network request.
        self.policy.assert_free(model)

        payload = self._payload(model, image_bytes, mime, prompt)
        headers = self._headers()
        errors: list[str] = []
        attempts = 0

        async with self._semaphore:
            for attempt in range(self.settings.max_retries + 1):
                attempts = attempt + 1
                await budget.reserve()  # counts every actual attempt
                started = time.monotonic()
                retryable = False
                status_code: int | None = None

                try:
                    async with httpx.AsyncClient(
                        transport=self._transport,
                        timeout=httpx.Timeout(self.settings.request_timeout_seconds, connect=15.0),
                        base_url=self.settings.siliconflow_base_url,
                    ) as client:
                        await self._throttle()
                        response = await client.post(
                            "/chat/completions", headers=headers, json=payload
                        )
                    status_code = response.status_code
                    if response.status_code >= 400:
                        body = response.text[:1200]
                        if response.status_code in {401, 403}:
                            await budget.outcome(False)
                            raise AuthError(
                                "硅基流动鉴权失败（401/403）。请检查 API Key。",
                                attempts=attempts,
                                status_code=response.status_code,
                            )
                        if response.status_code == 402:
                            await budget.outcome(False)
                            raise PaymentRejectedError(
                                "云端返回 402（余额/计费拒绝），已立即停止且不会自动切换付费模型。",
                                attempts=attempts,
                                status_code=response.status_code,
                            )
                        if response.status_code == 429 or response.status_code >= 500:
                            retryable = True
                            errors.append(f"HTTP {response.status_code}: {body[:200]}")
                            await budget.outcome(False)
                            if attempt < self.settings.max_retries:
                                await self._sleep_backoff(attempt, response)
                                continue
                            raise OCRRequestError(
                                f"OCR 请求失败，已重试 {attempts} 次：{errors[-1]}",
                                attempts=attempts,
                                status_code=response.status_code,
                            )
                        await budget.outcome(False)
                        raise OCRRequestError(
                            f"OCR 请求被拒绝（HTTP {response.status_code}）：{body}",
                            attempts=attempts,
                            status_code=response.status_code,
                        )

                    data = response.json()
                    return await self._handle_success(
                        data=data,
                        model=model,
                        cache_key=cache_key,
                        latency_ms=int((time.monotonic() - started) * 1000),
                        attempts=attempts,
                        budget=budget,
                    )
                except (BudgetExceeded, PolicyViolation):
                    raise
                except (AuthError, PaymentRejectedError, OCRRequestError):
                    raise
                except httpx.TimeoutException as exc:
                    retryable = True
                    errors.append(f"timeout: {exc}")
                    await budget.outcome(False)
                    if attempt >= self.settings.max_retries:
                        raise OCRRequestError(
                            f"OCR 请求超时，已重试 {attempts} 次。",
                            attempts=attempts,
                        ) from exc
                except httpx.HTTPError as exc:
                    retryable = True
                    errors.append(f"{type(exc).__name__}: {exc}")
                    await budget.outcome(False)
                    if attempt >= self.settings.max_retries:
                        raise OCRRequestError(
                            f"OCR 网络请求失败，已重试 {attempts} 次：{exc}",
                            attempts=attempts,
                        ) from exc
                except (KeyError, ValueError, TypeError) as exc:
                    retryable = False
                    errors.append(f"响应解析失败: {exc}")
                    await budget.outcome(False)
                    raise OCRRequestError(f"云端响应解析失败：{exc}", attempts=attempts) from exc

                if retryable and attempt < self.settings.max_retries:
                    await self._sleep_backoff(attempt)
                    continue

        raise OCRRequestError(
            f"OCR 请求失败，已重试 {attempts} 次：{'；'.join(errors[:3])}",
            attempts=attempts,
            status_code=status_code,
        )

    async def _handle_success(
        self,
        *,
        data: dict[str, Any],
        model: str,
        cache_key: str,
        latency_ms: int,
        attempts: int,
        budget: JobBudget,
    ) -> OCRResponse:
        choices = data.get("choices") or []
        if not choices:
            await budget.outcome(False)
            raise OCRRequestError("云端响应缺少 choices。", attempts=attempts)
        message = choices[0].get("message") or {}
        text = _content_to_text(message.get("content"))
        raw_text = text
        finish_reason = choices[0].get("finish_reason")
        truncated = finish_reason == "length"
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
        request_id = data.get("id")
        if not text.strip():
            await budget.outcome(False)
            raise OCRRequestError(
                "模型返回空文本。已保留请求记录，请检查图片或重试。",
                attempts=attempts,
            )
        await budget.outcome(True)
        self.cache.put(
            cache_key,
            {
                "text": text,
                "raw_text": raw_text,
                "usage": usage,
                "latency_ms": latency_ms,
                "finish_reason": finish_reason,
                "truncated": truncated,
                "model": model,
                "request_id": request_id,
            },
        )
        return OCRResponse(
            text=text,
            raw_text=raw_text,
            usage=usage,
            latency_ms=latency_ms,
            from_cache=False,
            cache_key=cache_key,
            model=model,
            attempts=attempts,
            finish_reason=finish_reason,
            truncated=truncated,
            request_id=request_id,
            confidence=None,
            metadata={"provider": "siliconflow", "truncated": truncated},
        )

    async def _sleep_backoff(self, attempt: int, response: httpx.Response | None = None) -> None:
        retry_after = None
        if response is not None:
            header = response.headers.get("Retry-After")
            if header:
                try:
                    retry_after = float(header)
                except ValueError:
                    retry_after = None
        base = 1.5 * (2**attempt)
        delay = min(20.0, retry_after if retry_after is not None else base)
        delay += random.uniform(0, 0.6)
        await asyncio.sleep(delay)


def response_to_dict(response: OCRResponse) -> dict[str, Any]:
    return {
        "text": response.text,
        "usage": response.usage,
        "latency_ms": response.latency_ms,
        "from_cache": response.from_cache,
        "model": response.model,
        "attempts": response.attempts,
        "truncated": response.truncated,
        "request_id": response.request_id,
    }


__all__ = [
    "AuthError",
    "OCRRequestError",
    "OCRResponse",
    "PaymentRejectedError",
    "SiliconFlowOCRClient",
    "build_prompt",
    "json",
]
