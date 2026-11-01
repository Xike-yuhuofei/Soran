from __future__ import annotations

import base64
import json

import httpx
import pytest

from app.config import Settings
from app.policy import PolicyViolation
from app.siliconflow import (
    AuthError,
    OCRRequestError,
    OCRResponse,
    PaymentRejectedError,
    SiliconFlowOCRClient,
    build_prompt,
)
from app.storage import ChunkCache, JobBudget, UsageLedger


class StubPolicy:
    def __init__(self, free: bool = True):
        self.free = free
        self.checked: list[str] = []

    def assert_free(self, model_id: str) -> None:
        self.checked.append(model_id)
        if not self.free:
            raise PolicyViolation("not verified free")


def make_budget(settings: Settings) -> JobBudget:
    return JobBudget(settings, UsageLedger(settings), "test-job")


def success_payload(text: str = "识别文本") -> dict:
    return {
        "id": "req-1",
        "choices": [
            {
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
    }


@pytest.mark.asyncio
async def test_success_and_prompt(settings):
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json=success_payload("面料成分：92%莫代尔 8%氨纶"))

    client = SiliconFlowOCRClient(
        settings, StubPolicy(), ChunkCache(settings), transport=httpx.MockTransport(handler)
    )
    budget = make_budget(settings)
    response = await client.ocr_chunk(
        model=settings.primary_model,
        image_bytes=b"abcdef",
        mime="image/jpeg",
        mode="text",
        budget=budget,
    )
    assert isinstance(response, OCRResponse)
    assert response.text.startswith("面料成分")
    assert response.attempts == 1
    payload = captured[0]
    assert payload["model"] == settings.primary_model
    assert payload["messages"][0]["content"][1]["text"] == build_prompt(
        settings.primary_model, "text", settings.review_model
    )
    image_url = payload["messages"][0]["content"][0]["image_url"]["url"]
    assert image_url.startswith("data:image/jpeg;base64,")
    assert base64.b64decode(image_url.split(",", 1)[1]) == b"abcdef"
    assert budget.used == 1
    assert budget.cache_hits == 0


@pytest.mark.asyncio
async def test_cache_hit_avoids_second_request(settings):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json=success_payload("缓存文本"))

    client = SiliconFlowOCRClient(
        settings, StubPolicy(), ChunkCache(settings), transport=httpx.MockTransport(handler)
    )
    budget = make_budget(settings)
    await client.ocr_chunk(
        model=settings.primary_model,
        image_bytes=b"same-bytes",
        mime="image/jpeg",
        mode="text",
        budget=budget,
    )
    second = await client.ocr_chunk(
        model=settings.primary_model,
        image_bytes=b"same-bytes",
        mime="image/jpeg",
        mode="text",
        budget=budget,
    )
    assert calls["count"] == 1
    assert second.from_cache is True
    assert second.attempts == 0
    assert budget.cache_hits == 1
    assert budget.used == 1


@pytest.mark.asyncio
async def test_retry_on_429(settings):
    settings.max_retries = 2
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, text="rate limited")
        return httpx.Response(200, json=success_payload("重试成功"))

    client = SiliconFlowOCRClient(
        settings, StubPolicy(), ChunkCache(settings), transport=httpx.MockTransport(handler)
    )
    budget = make_budget(settings)
    response = await client.ocr_chunk(
        model=settings.primary_model,
        image_bytes=b"retry",
        mime="image/jpeg",
        mode="text",
        budget=budget,
    )
    assert response.text == "重试成功"
    assert response.attempts == 2
    assert budget.used == 2


@pytest.mark.asyncio
async def test_final_5xx_raises(settings):
    settings.max_retries = 1
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(503, text="unavailable")

    client = SiliconFlowOCRClient(
        settings, StubPolicy(), ChunkCache(settings), transport=httpx.MockTransport(handler)
    )
    budget = make_budget(settings)
    with pytest.raises(OCRRequestError) as info:
        await client.ocr_chunk(
            model=settings.primary_model,
            image_bytes=b"fail",
            mime="image/jpeg",
            mode="text",
            budget=budget,
        )
    assert info.value.attempts == 2
    assert calls["count"] == 2
    assert budget.used == 2


@pytest.mark.asyncio
async def test_timeout_is_retried(settings):
    settings.max_retries = 1
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ReadTimeout("timeout", request=request)
        return httpx.Response(200, json=success_payload("超时重试成功"))

    client = SiliconFlowOCRClient(
        settings, StubPolicy(), ChunkCache(settings), transport=httpx.MockTransport(handler)
    )
    budget = make_budget(settings)
    response = await client.ocr_chunk(
        model=settings.primary_model,
        image_bytes=b"timeout",
        mime="image/jpeg",
        mode="text",
        budget=budget,
    )
    assert response.attempts == 2
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_auth_error_not_retried(settings):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(401, text="bad key")

    client = SiliconFlowOCRClient(
        settings, StubPolicy(), ChunkCache(settings), transport=httpx.MockTransport(handler)
    )
    budget = make_budget(settings)
    with pytest.raises(AuthError):
        await client.ocr_chunk(
            model=settings.primary_model,
            image_bytes=b"auth",
            mime="image/jpeg",
            mode="text",
            budget=budget,
        )
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_payment_rejection_not_retried(settings):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(402, text="payment required")

    client = SiliconFlowOCRClient(
        settings, StubPolicy(), ChunkCache(settings), transport=httpx.MockTransport(handler)
    )
    budget = make_budget(settings)
    with pytest.raises(PaymentRejectedError):
        await client.ocr_chunk(
            model=settings.primary_model,
            image_bytes=b"pay",
            mime="image/jpeg",
            mode="text",
            budget=budget,
        )
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_policy_blocks_before_network(settings):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json=success_payload())

    client = SiliconFlowOCRClient(
        settings,
        StubPolicy(free=False),
        ChunkCache(settings),
        transport=httpx.MockTransport(handler),
    )
    budget = make_budget(settings)
    with pytest.raises(PolicyViolation):
        await client.ocr_chunk(
            model=settings.primary_model,
            image_bytes=b"blocked",
            mime="image/jpeg",
            mode="text",
            budget=budget,
        )
    assert calls["count"] == 0
    assert budget.used == 0


@pytest.mark.asyncio
async def test_missing_api_key_fails_before_network(settings):
    settings.siliconflow_api_key = None
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json=success_payload())

    client = SiliconFlowOCRClient(
        settings, StubPolicy(), ChunkCache(settings), transport=httpx.MockTransport(handler)
    )
    budget = make_budget(settings)
    with pytest.raises(AuthError):
        await client.ocr_chunk(
            model=settings.primary_model,
            image_bytes=b"no-key",
            mime="image/jpeg",
            mode="text",
            budget=budget,
        )
    assert calls["count"] == 0


@pytest.mark.asyncio
async def test_empty_content_is_rejected(settings):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=success_payload("   "))

    client = SiliconFlowOCRClient(
        settings, StubPolicy(), ChunkCache(settings), transport=httpx.MockTransport(handler)
    )
    budget = make_budget(settings)
    with pytest.raises(OCRRequestError, match="空文本"):
        await client.ocr_chunk(
            model=settings.primary_model,
            image_bytes=b"empty",
            mime="image/jpeg",
            mode="text",
            budget=budget,
        )


@pytest.mark.asyncio
async def test_truncated_finish_reason(settings):
    payload = success_payload("部分文本")
    payload["choices"][0]["finish_reason"] = "length"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = SiliconFlowOCRClient(
        settings, StubPolicy(), ChunkCache(settings), transport=httpx.MockTransport(handler)
    )
    response = await client.ocr_chunk(
        model=settings.primary_model,
        image_bytes=b"trunc",
        mime="image/jpeg",
        mode="text",
        budget=make_budget(settings),
    )
    assert response.truncated is True
