from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from .config import Settings

logger = logging.getLogger(__name__)


class PolicyViolation(RuntimeError):
    """Raised when a cloud call is not provably free."""


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    display_name: str
    role: str
    note: str = ""


# Only these models may ever be called by the pipeline. Adding a model requires
# updating this registry and the free-status verifier.
MODEL_REGISTRY: dict[str, ModelSpec] = {
    "deepseek-ai/DeepSeek-OCR": ModelSpec(
        model_id="deepseek-ai/DeepSeek-OCR",
        display_name="DeepSeek-OCR",
        role="primary",
        note="官方定价页 2026-11-01 显示 price=0、操作标签为“限免”。",
    ),
    "PaddlePaddle/PaddleOCR-VL-1.5": ModelSpec(
        model_id="PaddlePaddle/PaddleOCR-VL-1.5",
        display_name="PaddleOCR-VL-1.5",
        role="review",
        note="官方定价页 2026-11-01 显示“免费”。",
    ),
}

ZERO_PRICE_RE = re.compile(r'"price":"(?:0|0\.0|0\.00)"')
NONZERO_PRICE_RE = re.compile(r'"price":"(?!0(?:\.0+)?")[^"]+"')
MODEL_NAME_RE = re.compile(r'"modelName":"([^"]+)"')


def _normalize_html(html: str) -> str:
    # The pricing page is a Next.js payload. Escaped quotes/newlines make
    # escaped JSON valid enough for structural marker checks.
    return html.replace('\\"', '"').replace("\\n", "\n")


def check_model_free(html: str, model_id: str) -> dict[str, Any]:
    """Conservatively verify a model is free on the official pricing page.

    The page embeds each model as an object spread across Next.js chunks, so
    full JSON parsing is not reliable. We instead isolate the region belonging
    to the model and require every price marker to be zero. Any ambiguity
    fails closed.
    """

    text = _normalize_html(html)
    occurrences = [m.start() for m in re.finditer(rf'"modelName":"{re.escape(model_id)}"', text)]
    if not occurrences:
        return {
            "free": False,
            "reason": "model_not_found_on_official_pricing_page",
            "model_id": model_id,
        }

    last_reason = "no_valid_occurrence"
    for pos in occurrences:
        next_match = MODEL_NAME_RE.search(text, pos + 1)
        end = next_match.start() if next_match else min(len(text), pos + 8000)
        window = text[pos:end]
        markers = {
            "status_normal": '"status":"normal"' in window,
            "deprecated_empty": '"deprecatedTime":{}' in window,
            "price_zero": bool(ZERO_PRICE_RE.search(window)),
            "input_price_zero": '"inputPrice":"0"' in window or '"inputPrice":0' in window,
            "balance_not_required": '"onlyByChargeBalance":false' in window,
            "no_nonzero_price": not bool(NONZERO_PRICE_RE.search(window)),
        }
        # If a concrete pricing array is present, every component must be zero.
        pricing_arrays = re.findall(r'"pricing":\[(.*?)\]', window, flags=re.S)
        if pricing_arrays:
            markers["pricing_array_zero"] = all(
                bool(ZERO_PRICE_RE.search(f"[{arr}]")) and not NONZERO_PRICE_RE.search(f"[{arr}]")
                for arr in pricing_arrays
            )

        op_match = re.search(r'"operationLabel":"([^"]*)"', window)
        operation_label = op_match.group(1) if op_match else ""

        if all(markers.values()):
            return {
                "free": True,
                "reason": "official_pricing_page_price_zero",
                "model_id": model_id,
                "operation_label": operation_label,
                "markers": markers,
            }
        failed = [name for name, ok in markers.items() if not ok]
        last_reason = "markers_failed:" + ",".join(failed)

    return {"free": False, "reason": last_reason, "model_id": model_id}


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class FreePolicy:
    """Runtime free-model guard backed by the official pricing page.

    Calls are blocked when the page cannot be refreshed and the last verified
    snapshot is older than the configured limit. There is deliberately no
    bypass that permits paid models.
    """

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self._transport = transport
        self._snapshot: dict[str, Any] | None = None
        self._lock = asyncio.Lock()
        self._last_error: str | None = None
        self._load_snapshot()

    def _load_snapshot(self) -> None:
        for path in (self.settings.policy_snapshot_path, self.bundled_snapshot_path):
            if path.exists():
                try:
                    self._snapshot = json.loads(path.read_text(encoding="utf-8"))
                    return
                except (OSError, ValueError):
                    continue

    @property
    def bundled_snapshot_path(self) -> Path:
        return Path(__file__).resolve().parent / "data" / "free_models_snapshot.json"

    def _snapshot_age(self) -> timedelta | None:
        if not self._snapshot:
            return None
        try:
            checked = datetime.fromisoformat(self._snapshot["checked_at"])
            if checked.tzinfo is None:
                checked = checked.replace(tzinfo=UTC)
            return datetime.now(UTC) - checked
        except (KeyError, TypeError, ValueError):
            return None

    def _snapshot_fresh_for_calls(self) -> bool:
        age = self._snapshot_age()
        if age is None:
            return False
        return age <= timedelta(hours=self.settings.policy_max_snapshot_age_hours)

    def model_status(self, model_id: str) -> dict[str, Any]:
        snapshot = self._snapshot or {}
        entry = (snapshot.get("models") or {}).get(model_id)
        if entry is None:
            return {
                "model_id": model_id,
                "free": False,
                "reason": "no_verification_snapshot",
                "registered": model_id in MODEL_REGISTRY,
            }
        return {
            "model_id": model_id,
            "free": bool(entry.get("free")),
            "reason": entry.get("reason"),
            "operation_label": entry.get("operation_label"),
            "registered": model_id in MODEL_REGISTRY,
        }

    def assert_free(self, model_id: str) -> None:
        if model_id not in MODEL_REGISTRY:
            raise PolicyViolation(f"模型 {model_id} 不在免费白名单注册表中，已阻止调用。")
        if not self._snapshot_fresh_for_calls():
            raise PolicyViolation(
                "免费策略快照缺失或已过期。为防止产生费用，已阻止所有云端 OCR 调用。"
                "请联网并刷新官方定价页后再试（GET /api/policy?refresh=true）。"
            )
        status = self.model_status(model_id)
        if not status["free"]:
            raise PolicyViolation(
                f"无法确认模型 {model_id} 当前免费（{status['reason']}），已阻止调用。"
                "请到硅基流动官方定价页人工核实。"
            )

    async def _fetch(self) -> str:
        url = self.settings.pricing_page_url
        async with httpx.AsyncClient(
            transport=self._transport,
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
            headers={"User-Agent": "Soran-OCR-FreeGuard/0.1"},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    async def refresh(self, force: bool = False) -> dict[str, Any]:
        async with self._lock:
            age = self._snapshot_age()
            if (
                not force
                and age is not None
                and age < timedelta(seconds=self.settings.policy_refresh_seconds)
            ):
                return self.status()

            try:
                html = await self._fetch()
            except (httpx.HTTPError, OSError) as exc:
                self._last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("Free policy refresh failed: %s", self._last_error)
                return self.status()

            models: dict[str, Any] = {}
            for model_id in MODEL_REGISTRY:
                models[model_id] = check_model_free(html, model_id)

            payload = {
                "checked_at": datetime.now(UTC).isoformat(),
                "source": self.settings.pricing_page_url,
                "source_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
                "models": models,
                "notes": (
                    "免费状态为官方定价页的运行时快照。模型可能随时调整价格；"
                    "快照过期后系统会自动阻止云端调用。"
                ),
            }
            self._snapshot = payload
            self._last_error = None
            _atomic_write_json(self.settings.policy_snapshot_path, payload)
            return self.status()

    def status(self, refresh_error: str | None = None) -> dict[str, Any]:
        age = self._snapshot_age()
        models = {mid: self.model_status(mid) for mid in MODEL_REGISTRY}
        return {
            "checked_at": (self._snapshot or {}).get("checked_at"),
            "age_seconds": int(age.total_seconds()) if age else None,
            "snapshot_fresh": self._snapshot_fresh_for_calls(),
            "max_snapshot_age_hours": self.settings.policy_max_snapshot_age_hours,
            "source": self.settings.pricing_page_url,
            "models": models,
            "paid_models_allowed": False,
            "registered_models": [spec.__dict__ for spec in MODEL_REGISTRY.values()],
            "refresh_error": refresh_error or self._last_error,
        }
