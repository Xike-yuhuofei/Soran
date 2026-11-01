from __future__ import annotations

import json

import pytest
from conftest import image_bytes, make_ecommerce_image

from app.config import Settings
from app.imaging import segment_image, validate_image_bytes
from app.pipeline import OCRPipeline
from app.policy import PolicyViolation
from app.schemas import (
    ChunkResult,
    ImageResult,
    OCRJobRequest,
    SessionInfo,
    utc_now,
)
from app.siliconflow import OCRRequestError, OCRResponse
from app.storage import JobStore, SessionStore, UsageLedger


class StubPolicy:
    def __init__(self, blocked: bool = False):
        self.blocked = blocked
        self.asserted: list[str] = []

    async def refresh(self, force: bool = False) -> dict:
        return self.status()

    def assert_free(self, model_id: str) -> None:
        self.asserted.append(model_id)
        if self.blocked:
            raise PolicyViolation("模型未确认免费")

    def status(self) -> dict:
        return {
            "snapshot_fresh": not self.blocked,
            "models": {
                "deepseek-ai/DeepSeek-OCR": {"free": not self.blocked},
                "PaddlePaddle/PaddleOCR-VL-1.5": {"free": not self.blocked},
            },
            "source": "test",
        }


class FakeClient:
    def __init__(
        self,
        settings: Settings,
        primary_texts: list[str],
        review_texts: list[str] | None = None,
        fail_primary_call: int | None = None,
        fail_review_call: int | None = None,
    ):
        self.settings = settings
        self.primary_texts = primary_texts
        self.review_texts = review_texts or []
        self.fail_primary_call = fail_primary_call
        self.fail_review_call = fail_review_call
        self.primary_calls = 0
        self.review_calls = 0

    async def ocr_chunk(self, *, model, image_bytes, mime, mode, budget, allow_cache=True):
        await budget.reserve()
        if model == self.settings.primary_model:
            index = self.primary_calls
            self.primary_calls += 1
            if self.fail_primary_call is not None and index == self.fail_primary_call:
                await budget.outcome(False)
                raise OCRRequestError("mock failure", attempts=1)
            await budget.outcome(True)
            text = self.primary_texts[index % len(self.primary_texts)]
        else:
            index = self.review_calls
            self.review_calls += 1
            if self.fail_review_call is not None and index == self.fail_review_call:
                await budget.outcome(False)
                raise OCRRequestError("mock review failure", attempts=1)
            await budget.outcome(True)
            text = self.review_texts[index % len(self.review_texts)] if self.review_texts else ""
            if not text:
                text = self.primary_texts[0]
        return OCRResponse(
            text=text,
            raw_text=text,
            usage={"total_tokens": 100},
            latency_ms=10,
            from_cache=False,
            cache_key="fake",
            model=model,
            attempts=1,
        )


def build_session(settings: Settings, height: int = 3000):
    image = make_ecommerce_image(height=height)
    loaded = validate_image_bytes(image_bytes(image), settings)
    sessions = SessionStore(settings)
    session_id, session_dir = sessions.create()
    info = sessions.add_image(
        session_dir,
        order=0,
        filename="sample.png",
        image=loaded.image,
        sha256=loaded.sha256,
        source_format=loaded.source_format,
    )
    session = SessionInfo(session_id=session_id, created_at=utc_now(), images=[info])
    sessions.save_session(session_dir, session)
    return sessions, session, loaded.image


def make_pipeline(settings, policy, client) -> OCRPipeline:
    return OCRPipeline(
        settings,
        policy,
        client,
        SessionStore(settings),
        JobStore(settings),
        UsageLedger(settings),
    )


def create_job(settings, session_id: str, **overrides):
    payload = OCRJobRequest(
        session_id=session_id,
        consent_cloud_upload=True,
        use_review=overrides.pop("use_review", True),
        use_cache=False,
        **overrides,
    )
    jobs = JobStore(settings)
    job_id = jobs.create(payload.model_dump())
    return jobs, job_id


def plan_count(settings, height: int = 3000) -> int:
    image = make_ecommerce_image(height=height)
    return len(segment_image(image, settings))


@pytest.mark.asyncio
async def test_pipeline_completes_and_dedupes(settings):
    sessions, session, image = build_session(settings)
    chunks = segment_image(image, settings)
    assert len(chunks) >= 2
    texts = [
        "# 素然之境\n**面料成分**：92%莫代尔 8%氨纶\n重叠行A\n重叠行B",
        "重叠行A\n重叠行B\n尺码表\nM 170/90A\n型号：SR-M2001",
        "M 170/90A\n价格：¥129.00\n温馨提示",
        "温馨提示\n请以实物为准。",
    ]
    client = FakeClient(settings, texts, review_texts=[texts[0]])
    policy = StubPolicy()
    pipeline = make_pipeline(settings, policy, client)
    jobs, job_id = create_job(settings, session.session_id)
    await pipeline.run_job(job_id)
    result = jobs.load_result(job_id)
    assert result.status == "completed"
    assert result.text
    assert "**" not in result.text
    assert "# 素然之境" not in result.text
    assert result.images[0].text.count("M 170/90A") <= 2
    assert result.api_requests >= len(chunks)
    assert result.total_chunks == len(chunks)
    assert result.completed_chunks == len(chunks)
    assert [chunk.index for chunk in result.images[0].chunks] == list(range(len(chunks)))
    assert result.images[0].chunks[0].y0 == 0
    assert result.images[0].chunks[-1].y1 == image.height


@pytest.mark.asyncio
async def test_pipeline_review_conflict_keeps_primary(settings):
    sessions, session, image = build_session(settings)
    primary = "面料成分：92%莫代尔 8%氨纶\n型号：SR-M2001"
    review = "面料成分：95%莫代尔 5%氨纶\n型号：SR-M2002"
    client = FakeClient(settings, [primary], review_texts=[review])
    policy = StubPolicy()
    pipeline = make_pipeline(settings, policy, client)
    jobs, job_id = create_job(settings, session.session_id, use_review=True)
    await pipeline.run_job(job_id)
    result = jobs.load_result(job_id)
    chunk = result.images[0].chunks[0]
    assert chunk.reviewed is True
    assert chunk.text == primary
    assert chunk.review_text == review
    assert chunk.conflicts
    assert chunk.needs_review is True
    assert result.needs_manual_check is True


@pytest.mark.asyncio
async def test_pipeline_partial_when_one_chunk_fails(settings):
    sessions, session, image = build_session(settings)
    chunks = segment_image(image, settings)
    assert len(chunks) >= 2
    client = FakeClient(settings, ["第一段\n面料成分：92%莫代尔 8%氨纶"], fail_primary_call=1)
    policy = StubPolicy()
    pipeline = make_pipeline(settings, policy, client)
    jobs, job_id = create_job(settings, session.session_id, use_review=False)
    await pipeline.run_job(job_id)
    result = jobs.load_result(job_id)
    assert result.status == "partial"
    assert result.images[0].chunks[1].error
    assert result.images[0].chunks[0].text
    assert result.images[0].needs_manual_check is True


@pytest.mark.asyncio
async def test_pipeline_uses_grounding_layout_blocks(settings):
    sessions, session, image = build_session(settings, height=800)
    grounding = """<|ref|>title<|/ref|><|det|>[[40, 20, 300, 60]]<|/det|>
左栏标题

<|ref|>text<|/ref|><|det|>[[40, 90, 300, 120]]<|/det|>
左栏正文

<|ref|>title<|/ref|><|det|>[[400, 20, 700, 60]]<|/det|>
右栏标题

<|ref|>text<|/ref|><|det|>[[400, 90, 700, 120]]<|/det|>
右栏正文
"""
    client = FakeClient(settings, [grounding])
    pipeline = make_pipeline(settings, StubPolicy(), client)
    jobs, job_id = create_job(settings, session.session_id, use_review=False, mode="markdown")
    await pipeline.run_job(job_id)
    result = jobs.load_result(job_id)
    chunk = result.images[0].chunks[0]
    assert chunk.layout_method == "grounding_xy_cut"
    assert len(chunk.layout_blocks) == 4
    assert chunk.layout_blocks[0].bbox[0] > 0
    assert "左栏标题" in chunk.text
    assert "右栏正文" in chunk.text
    assert result.images[0].text.index("左栏标题") < result.images[0].text.index("右栏标题")


@pytest.mark.asyncio
async def test_pipeline_review_can_be_enabled_per_job(settings):
    settings.review_enabled = False
    sessions, session, _ = build_session(settings, height=800)
    client = FakeClient(
        settings, ["面料成分：92%莫代尔 8%氨纶"], review_texts=["面料成分：92%莫代尔 8%氨纶"]
    )
    pipeline = make_pipeline(settings, StubPolicy(), client)
    jobs, job_id = create_job(settings, session.session_id, use_review=True)
    await pipeline.run_job(job_id)
    result = jobs.load_result(job_id)
    assert result.images[0].chunks[0].reviewed is True


@pytest.mark.asyncio
async def test_pipeline_blocks_when_policy_not_free(settings):
    sessions, session, _ = build_session(settings, height=800)
    client = FakeClient(settings, ["文本"])
    policy = StubPolicy(blocked=True)
    pipeline = make_pipeline(settings, policy, client)
    jobs, job_id = create_job(settings, session.session_id)
    await pipeline.run_job(job_id)
    result = jobs.load_result(job_id)
    assert result.status == "blocked"
    assert client.primary_calls == 0
    assert "免费" in result.errors[0]


@pytest.mark.asyncio
async def test_pipeline_requires_consent(settings):
    sessions, session, _ = build_session(settings, height=800)
    client = FakeClient(settings, ["文本"])
    pipeline = make_pipeline(settings, StubPolicy(), client)
    jobs = JobStore(settings)
    payload = OCRJobRequest(session_id=session.session_id, consent_cloud_upload=False)
    job_id = jobs.create(payload.model_dump())
    await pipeline.run_job(job_id)
    result = jobs.load_result(job_id)
    assert result.status == "blocked"
    assert client.primary_calls == 0


@pytest.mark.asyncio
async def test_pipeline_blocks_without_key_or_local(settings):
    settings.siliconflow_api_key = None
    sessions, session, _ = build_session(settings, height=800)
    client = FakeClient(settings, ["文本"])
    pipeline = make_pipeline(settings, StubPolicy(), client)
    jobs, job_id = create_job(settings, session.session_id)
    await pipeline.run_job(job_id)
    result = jobs.load_result(job_id)
    assert result.status == "blocked"
    assert "SILICONFLOW_API_KEY" in result.errors[0]


@pytest.mark.asyncio
async def test_pipeline_resume(settings):
    sessions, session, image = build_session(settings)
    client = FakeClient(settings, ["第一段", "第二段"], fail_primary_call=1)
    pipeline = make_pipeline(settings, StubPolicy(), client)
    jobs, job_id = create_job(settings, session.session_id, use_review=False)
    await pipeline.run_job(job_id)
    first = jobs.load_result(job_id)
    assert first.status == "partial"
    client.fail_primary_call = None
    await pipeline.run_job(job_id, resume=True)
    second = jobs.load_result(job_id)
    assert second.status == "completed"
    assert second.api_requests >= first.api_requests


@pytest.mark.asyncio
async def test_apply_review_text_and_restore_primary(settings):
    sessions, session, _ = build_session(settings, height=800)
    primary = "面料成分：92%莫代尔 8%氨纶"
    review = "面料成分：95%莫代尔 5%氨纶"
    client = FakeClient(settings, [primary], review_texts=[review])
    pipeline = make_pipeline(settings, StubPolicy(), client)
    jobs, job_id = create_job(settings, session.session_id, use_review=True)
    await pipeline.run_job(job_id)
    result = jobs.load_result(job_id)
    image = result.images[0]
    chunk = image.chunks[0]
    assert chunk.review_text == review

    applied = pipeline.apply_chunk_text(
        job_id,
        image_id=image.image_id,
        chunk_index=0,
        source="review",
    )
    chunk = applied.images[0].chunks[0]
    assert chunk.text == review
    assert chunk.manual_override is True
    assert chunk.override_source == "review"
    assert chunk.original_text == primary
    assert review in applied.text

    restored = pipeline.apply_chunk_text(
        job_id,
        image_id=image.image_id,
        chunk_index=0,
        source="primary",
    )
    chunk = restored.images[0].chunks[0]
    assert chunk.text == primary
    assert chunk.manual_override is False
    assert chunk.original_text is None
    assert review not in restored.text


@pytest.mark.asyncio
async def test_apply_review_requires_review_text(settings):
    sessions, session, _ = build_session(settings, height=800)
    client = FakeClient(settings, ["主模型文本"])
    pipeline = make_pipeline(settings, StubPolicy(), client)
    jobs, job_id = create_job(settings, session.session_id, use_review=False)
    await pipeline.run_job(job_id)
    result = jobs.load_result(job_id)
    with pytest.raises(ValueError, match="复核文本"):
        pipeline.apply_chunk_text(
            job_id,
            image_id=result.images[0].image_id,
            chunk_index=0,
            source="review",
        )


def test_apply_edits_updates_exports(settings):
    sessions, session, image = build_session(settings, height=800)
    client = FakeClient(settings, ["面料成分：92%莫代尔 8%氨纶\n价格：¥129.00"])
    pipeline = make_pipeline(settings, StubPolicy(), client)
    jobs, job_id = create_job(settings, session.session_id, use_review=False)
    import asyncio

    asyncio.run(pipeline.run_job(job_id))
    result = jobs.load_result(job_id)
    assert result.images[0].text
    from app.schemas import EditDocument

    updated = pipeline.apply_edits(
        job_id,
        [EditDocument(image_id=result.images[0].image_id, text="人工修正后的文本\n品牌：SORAN")],
    )
    assert updated.text.startswith("人工修正后的文本")
    assert updated.images[0].edited is True
    assert updated.markdown


@pytest.mark.asyncio
async def test_variant_a_forces_single_chunk(settings):
    sessions, session, image = build_session(settings)
    client = FakeClient(settings, ["单块文本"])
    pipeline = make_pipeline(settings, StubPolicy(), client)
    jobs, job_id = create_job(settings, session.session_id, use_review=False, variant="A")
    await pipeline.run_job(job_id)
    result = jobs.load_result(job_id)
    assert len(result.images[0].chunks) == 1
    assert result.total_chunks == 1
    assert result.api_requests == 1


def test_session_result_contains_no_secret(settings):
    # Guard against accidental key leakage in the serialized result.
    sessions, session, image = build_session(settings, height=800)
    client = FakeClient(settings, ["文本"])
    pipeline = make_pipeline(settings, StubPolicy(), client)
    jobs, job_id = create_job(settings, session.session_id, use_review=False)
    import asyncio

    asyncio.run(pipeline.run_job(job_id))
    dumped = json.dumps(jobs.load_result(job_id).model_dump(mode="json"), ensure_ascii=False)
    assert "test-key-not-real" not in dumped
    assert "sk-" not in dumped


def test_finalize_excludes_fabricated_blank_chunk(settings):
    pipeline = make_pipeline(settings, StubPolicy(), FakeClient(settings, ["unused"]))
    chunks = [
        ChunkResult(
            chunk_id="image:0",
            index=0,
            image_id="image",
            y0=0,
            y1=1200,
            overlap_top=0,
            overlap_bottom=120,
            scale=0.6,
            forced_cut=False,
            text="久坐不闷汗\n穿一整天也不黏腻感",
            ink_ratio=0.1372,
        ),
        ChunkResult(
            chunk_id="image:1",
            index=1,
            image_id="image",
            y0=1080,
            y1=2988,
            overlap_top=120,
            overlap_bottom=0,
            scale=0.6,
            forced_cut=False,
            text="<table><tr><td>Category</td><td>Value</td></tr><tr><td>Blue</td><td>100</td></tr></table>",
            ink_ratio=0.0016,
            quality_flags=["text_without_ink"],
            suspected_hallucination=True,
            needs_review=True,
        ),
    ]
    image = ImageResult(
        image_id="image",
        filename="sample.png",
        order=0,
        width=2480,
        height=2988,
        text="",
        markdown="",
        chunks=chunks,
    )
    warnings: list[str] = []
    pipeline._finalize_image(image, "text", warnings)
    assert "久坐不闷汗" in image.text
    assert "Category" not in image.text
    assert image.needs_manual_check
    assert any("编造" in warning for warning in image.warnings)
