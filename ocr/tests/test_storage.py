from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.storage import BudgetExceeded, ChunkCache, UsageLedger


def test_cache_key_deterministic_and_ttl(settings):
    cache = ChunkCache(settings)
    key = cache.key(b"image", "model", "prompt", "text", "v1")
    assert key == cache.key(b"image", "model", "prompt", "text", "v1")
    assert key != cache.key(b"image2", "model", "prompt", "text", "v1")
    cache.put(key, {"text": "hello"})
    assert cache.get(key)["text"] == "hello"

    path = cache.root / f"{key}.json"
    payload = __import__("json").loads(path.read_text(encoding="utf-8"))
    payload["created_at"] = (datetime.now(UTC) - timedelta(days=100)).isoformat()
    path.write_text(__import__("json").dumps(payload), encoding="utf-8")
    assert cache.get(key) is None


def test_cache_disabled(settings):
    settings.cache_enabled = False
    cache = ChunkCache(settings)
    cache.put("abc", {"text": "x"})
    assert cache.get("abc") is None


@pytest.mark.asyncio
async def test_daily_request_cap(settings):
    settings.max_requests_per_day = 1
    ledger = UsageLedger(settings)
    first = await ledger.reserve_attempt()
    assert first["attempts"] == 1
    with pytest.raises(BudgetExceeded):
        await ledger.reserve_attempt()

    free = UsageLedger(settings)
    assert (await free.today())["attempts"] == 1


@pytest.mark.asyncio
async def test_corrupt_ledger_blocks_new_requests(settings):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "usage.json").write_text("{not-json", encoding="utf-8")
    ledger = UsageLedger(settings)
    with pytest.raises(BudgetExceeded, match="账本损坏"):
        await ledger.reserve_attempt()


@pytest.mark.asyncio
async def test_job_budget_limits(settings):
    from app.storage import JobBudget

    settings.max_requests_per_job = 2
    settings.max_requests_per_day = 10
    budget = JobBudget(settings, UsageLedger(settings), "job")
    await budget.reserve()
    await budget.reserve()
    with pytest.raises(BudgetExceeded):
        await budget.reserve()
    assert budget.used == 2
    assert budget.remaining == 0
