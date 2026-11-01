from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.policy import FreePolicy, PolicyViolation, check_model_free


def test_check_model_free_true_and_false(pricing_html):
    assert check_model_free(pricing_html, "deepseek-ai/DeepSeek-OCR")["free"] is True
    assert check_model_free(pricing_html, "PaddlePaddle/PaddleOCR-VL-1.5")["free"] is True
    paid = check_model_free(pricing_html, "vendor/paid-model")
    assert paid["free"] is False
    assert "price_zero" in paid["reason"]


def test_unregistered_and_unknown_models_blocked(settings):
    policy = FreePolicy(settings)
    with pytest.raises(PolicyViolation):
        policy.assert_free("openai/gpt-4o")


@pytest.mark.asyncio
async def test_refresh_from_official_pricing_page(settings, pricing_html):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.siliconflow.cn":
            return httpx.Response(200, text=pricing_html)
        return httpx.Response(404)

    policy = FreePolicy(settings, transport=httpx.MockTransport(handler))
    status = await policy.refresh(force=True)
    assert status["models"]["deepseek-ai/DeepSeek-OCR"]["free"] is True
    assert status["models"]["PaddlePaddle/PaddleOCR-VL-1.5"]["free"] is True
    policy.assert_free("deepseek-ai/DeepSeek-OCR")
    assert settings.policy_snapshot_path.exists()


@pytest.mark.asyncio
async def test_refresh_failure_keeps_fresh_snapshot(settings, free_policy):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    policy = FreePolicy(settings, transport=httpx.MockTransport(handler))
    status = await policy.refresh(force=True)
    assert status["snapshot_fresh"] is True
    policy.assert_free("deepseek-ai/DeepSeek-OCR")
    assert status["refresh_error"]


def test_stale_snapshot_blocks_calls(settings, free_policy):
    stale = datetime.now(UTC) - timedelta(hours=settings.policy_max_snapshot_age_hours + 1)
    from conftest import make_free_snapshot

    make_free_snapshot(settings.policy_snapshot_path, checked_at=stale)
    policy = FreePolicy(settings)
    with pytest.raises(PolicyViolation):
        policy.assert_free("deepseek-ai/DeepSeek-OCR")
    assert policy.status()["snapshot_fresh"] is False


def test_snapshot_marked_not_free_blocks(settings):
    from conftest import make_free_snapshot

    make_free_snapshot(settings.policy_snapshot_path, free=False)
    policy = FreePolicy(settings)
    with pytest.raises(PolicyViolation):
        policy.assert_free("deepseek-ai/DeepSeek-OCR")
