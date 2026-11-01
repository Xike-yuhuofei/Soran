from __future__ import annotations

import asyncio
import logging
import random
import re
import time

from PIL import Image

from .config import Settings
from .fields import extract_key_fields, merge_key_fields, percent_issues
from .imaging import chunk_ink_ratio, render_chunk, segment_image
from .layout import (
    layout_text,
    order_parsed_blocks,
    parse_grounding_blocks,
    to_layout_blocks,
)
from .local_ocr import LocalPaddleOCR
from .merge import (
    build_document_markdown,
    merge_chunk_texts,
    strip_artifacts,
    to_markdown,
    to_plain_text,
)
from .policy import FreePolicy, PolicyViolation
from .quality import apply_review, assess_quality, compare_versions
from .schemas import (
    ChunkResult,
    EditDocument,
    ImageResult,
    JobProgress,
    JobResult,
    JobStatus,
    LayoutBlock,
    OCRJobRequest,
    utc_now,
)
from .siliconflow import (
    AuthError,
    OCRRequestError,
    PaymentRejectedError,
    SiliconFlowOCRClient,
)
from .storage import BudgetExceeded, JobBudget, JobStore, SessionStore, UsageLedger

logger = logging.getLogger(__name__)

VARIANTS = {
    "A": {"chunk": False, "review": False, "local": False},
    "B": {"chunk": True, "review": False, "local": False},
    "C": {"chunk": True, "review": True, "local": False},
    "D": {"chunk": True, "review": True, "local": True},
}

CRITICAL_CONTENT_RE = re.compile(
    r"(?:%|型号|货号|SKU|尺码|尺寸|执行标准|安全类别|面料|成分|洗涤|GB\s*\d+|¥|￥)",
    re.IGNORECASE,
)


class JobConflictError(RuntimeError):
    pass


class OCRPipeline:
    def __init__(
        self,
        settings: Settings,
        policy: FreePolicy,
        client: SiliconFlowOCRClient,
        sessions: SessionStore,
        jobs: JobStore,
        ledger: UsageLedger,
        local_ocr: LocalPaddleOCR | None = None,
    ):
        self.settings = settings
        self.policy = policy
        self.client = client
        self.sessions = sessions
        self.jobs = jobs
        self.ledger = ledger
        self.local_ocr = local_ocr or LocalPaddleOCR(settings)
        self._running: set[str] = set()
        self._run_lock = asyncio.Lock()

    async def run_job(self, job_id: str, *, resume: bool = False) -> None:
        async with self._run_lock:
            if job_id in self._running:
                raise JobConflictError("该任务正在运行。")
            self._running.add(job_id)
        try:
            await self._run_job_inner(job_id, resume=resume)
        finally:
            async with self._run_lock:
                self._running.discard(job_id)

    async def _run_job_inner(self, job_id: str, resume: bool) -> None:
        started = time.monotonic()
        request = OCRJobRequest.model_validate(self.jobs.load_request(job_id))
        variant = (request.variant or "D").upper()
        if variant not in VARIANTS:
            raise ValueError("variant 必须是 A/B/C/D")
        options = VARIANTS[variant]
        use_chunking = bool(options["chunk"])
        use_review = bool(options["review"] and request.use_review)
        use_local = bool(options["local"])
        mode = request.mode or self.settings.prompt_mode
        if mode not in {"text", "markdown"}:
            raise ValueError("mode 必须是 text 或 markdown")
        use_cache = bool((request.use_cache and self.settings.cache_enabled) or resume)

        if self.settings.require_cloud_consent and not request.consent_cloud_upload:
            await self._fail_early(
                job_id,
                request,
                "未获得云端上传授权。请勾选“我确认将图片上传至云端 OCR”后再开始。",
                status=JobStatus.blocked,
            )
            return

        previous_requests = 0
        if resume:
            try:
                previous_requests = self.jobs.load_result(job_id).api_requests
            except Exception:  # noqa: BLE001 - resuming may start from scratch
                previous_requests = 0

        budget = JobBudget(self.settings, self.ledger, job_id, initial=previous_requests)
        policy_status: dict = {}
        cloud_available = self.settings.api_key_configured
        local_available = self.local_ocr.available() if use_local else False

        warnings: list[str] = []
        errors: list[str] = []
        review_enabled = bool(cloud_available and use_review)

        if cloud_available:
            await self.policy.refresh()
            try:
                self.policy.assert_free(self.settings.primary_model)
            except PolicyViolation as exc:
                await self._fail_early(job_id, request, str(exc), status=JobStatus.blocked)
                return
            if review_enabled:
                try:
                    self.policy.assert_free(self.settings.review_model)
                except PolicyViolation as exc:
                    review_enabled = False
                    warnings.append(f"辅助复核模型不可用/未确认免费，已跳过复核：{exc}")
        else:
            if not local_available:
                await self._fail_early(
                    job_id,
                    request,
                    "未配置 SILICONFLOW_API_KEY，且本地 PP-OCR 未启用，无法识别。",
                    status=JobStatus.blocked,
                )
                return
            warnings.append("未配置云端 API Key，使用本地 PP-OCR 插件识别。")

        policy_status = self.policy.status()

        session = self.sessions.load_session(request.session_id)
        images = self._ordered_images(session, request)
        if not images:
            await self._fail_early(job_id, request, "没有可处理的图片。", status=JobStatus.failed)
            return
        if len(images) > self.settings.max_files_per_session:
            await self._fail_early(
                job_id,
                request,
                f"图片数量超过上限 {self.settings.max_files_per_session}。",
                status=JobStatus.failed,
            )
            return

        # Pre-compute chunk plans so progress totals are known before OCR.
        plans: dict[str, list] = {}
        for info in images:
            with Image.open(self.sessions.image_path(request.session_id, info.image_id)) as img:
                rgb = img.convert("RGB")
                plans[info.image_id] = segment_image(
                    rgb, self.settings, force_single_chunk=not use_chunking
                )
        total_chunks = sum(len(value) for value in plans.values())

        result = JobResult(
            job_id=job_id,
            status=JobStatus.running,
            created_at=utc_now(),
            updated_at=utc_now(),
            images=[
                ImageResult(
                    image_id=info.image_id,
                    filename=info.filename,
                    order=info.order,
                    width=info.width,
                    height=info.height,
                    text="",
                    markdown="",
                )
                for info in images
            ],
            errors=errors,
            warnings=warnings,
            policy=policy_status,
            options={
                "mode": mode,
                "variant": variant,
                "use_chunking": use_chunking,
                "use_review": review_enabled,
                "use_cache": use_cache,
                "primary_model": self.settings.primary_model,
                "review_model": self.settings.review_model if review_enabled else None,
                "local_ocr": self.local_ocr.status() if use_local else {"enabled": False},
            },
            total_chunks=total_chunks,
        )

        completed_chunks = 0
        reviewed_chunks = 0
        review_cap = self.settings.max_reviews_per_job
        try:
            for image_info in images:
                image_result = next(
                    item for item in result.images if item.image_id == image_info.image_id
                )
                image_started = time.monotonic()
                with Image.open(
                    self.sessions.image_path(request.session_id, image_info.image_id)
                ) as img:
                    rgb = img.convert("RGB")
                    chunk_plans = plans[image_info.image_id]

                    for plan in chunk_plans:
                        chunk_bytes, mime = render_chunk(rgb, plan)
                        ink_ratio = chunk_ink_ratio(rgb, plan.y0, plan.y1)
                        chunk = ChunkResult(
                            chunk_id=f"{image_info.image_id}:{plan.index}",
                            index=plan.index,
                            image_id=image_info.image_id,
                            y0=plan.y0,
                            y1=plan.y1,
                            overlap_top=plan.overlap_top,
                            overlap_bottom=plan.overlap_bottom,
                            scale=plan.scale,
                            forced_cut=plan.forced_cut,
                            risk_flags=list(plan.risk_flags),
                            ink_ratio=round(ink_ratio, 4),
                        )

                        if cloud_available:
                            try:
                                response = await self.client.ocr_chunk(
                                    model=self.settings.primary_model,
                                    image_bytes=chunk_bytes,
                                    mime=mime,
                                    mode=mode,
                                    budget=budget,
                                    allow_cache=use_cache,
                                )
                                chunk.text = strip_artifacts(response.text)
                                chunk.raw_text = response.raw_text
                                chunk.engine = self.settings.primary_model
                                chunk.confidence = response.confidence
                                chunk.usage = response.usage
                                chunk.latency_ms = response.latency_ms
                                chunk.from_cache = response.from_cache
                                chunk.api_requests += response.attempts
                                parsed_blocks = parse_grounding_blocks(response.raw_text)
                                if parsed_blocks:
                                    ordered_blocks = order_parsed_blocks(
                                        parsed_blocks,
                                        page_width=plan.crop_width,
                                        page_height=plan.crop_height,
                                    )
                                    chunk.layout_blocks = to_layout_blocks(
                                        ordered_blocks,
                                        image_width=rgb.width,
                                        image_height=rgb.height,
                                        y_offset=plan.y0,
                                        scale=plan.scale,
                                    )
                                    chunk.layout_method = "grounding_xy_cut"
                                    chunk.text = layout_text(ordered_blocks)
                                if response.truncated:
                                    chunk.risk_flags.append("output_truncated")
                                    chunk.needs_review = True
                            except (PolicyViolation, AuthError, PaymentRejectedError):
                                raise
                            except BudgetExceeded:
                                raise
                            except OCRRequestError as exc:
                                await self._local_fallback(chunk, rgb, plan, local_available, exc)
                        elif local_available:
                            await self._local_fallback(chunk, rgb, plan, True, None)
                        else:  # pragma: no cover - preflight prevents this
                            chunk.error = "无可用 OCR 引擎"
                            chunk.needs_review = True

                        quality = assess_quality(
                            chunk.text,
                            ink_ratio,
                            chunk.forced_cut,
                            chunk.risk_flags,
                        )
                        chunk.quality_score = quality.score
                        chunk.quality_flags = quality.flags
                        if quality.needs_review:
                            chunk.needs_review = True

                        reasons = self._review_reasons(
                            chunk.text,
                            quality.needs_review,
                            quality.flags,
                            chunk.risk_flags,
                        )
                        if review_enabled and reasons and reviewed_chunks < review_cap:
                            chunk.api_requests += await self._run_cloud_review(
                                chunk, chunk_bytes, mime, mode, budget, use_cache
                            )
                            reviewed_chunks += 1
                            chunk.review_reasons = reasons
                        elif review_enabled and reasons:
                            chunk.review_reasons = reasons
                            if f"复核次数达到单任务上限 {review_cap}" not in warnings:
                                warnings.append(
                                    f"复核次数达到单任务上限 {review_cap}，部分可疑分块未复核。"
                                )
                            review_enabled = False

                        if use_local and local_available and reasons:
                            await self._run_local_crosscheck(chunk, rgb, plan)

                        if not chunk.text and not chunk.error:
                            chunk.error = "模型未返回文字"
                        if chunk.error:
                            image_result.errors.append(
                                f"分块 {plan.index} ({plan.y0}-{plan.y1}px)：{chunk.error}"
                            )
                            chunk.needs_review = True
                        if chunk.conflicts:
                            chunk.uncertain = True
                            chunk.needs_review = True

                        image_result.chunks.append(chunk)
                        completed_chunks += 1
                        await self._write_snapshot(
                            result,
                            job_id,
                            stage="ocr",
                            progress=(0.05 + 0.75 * completed_chunks / max(1, total_chunks)),
                            completed=completed_chunks,
                            total=total_chunks,
                            requests=budget.used,
                            errors=errors,
                        )

                self._finalize_image(image_result, mode, warnings)
                image_result.duration_ms = int((time.monotonic() - image_started) * 1000)
                await self._write_snapshot(
                    result,
                    job_id,
                    stage="merge",
                    progress=0.85,
                    completed=completed_chunks,
                    total=total_chunks,
                    requests=budget.used,
                    errors=errors,
                )

            self._finalize_job(result, mode)
            result.status = (
                JobStatus.partial
                if any(image.errors for image in result.images)
                else JobStatus.completed
            )
            result.api_requests = budget.used
            result.budget = {
                "max_requests_per_job": self.settings.max_requests_per_job,
                "max_requests_per_day": self.settings.max_requests_per_day,
                "used": budget.used,
                "remaining": budget.remaining,
                "cache_hits": budget.cache_hits,
                "daily": await self.ledger.today(),
            }
            result.updated_at = utc_now()
            self.jobs.save_result(result)
            self._save_progress(
                job_id,
                result.status,
                "done",
                1.0,
                completed_chunks,
                total_chunks,
                budget.used,
                errors,
                result_available=True,
            )
            await asyncio.sleep(0)  # yield for tests / event loop fairness
        except (PolicyViolation, AuthError, PaymentRejectedError) as exc:
            result.errors.append(str(exc))
            result.status = JobStatus.blocked
            self._finalize_partial(result, mode, warnings)
            result.api_requests = budget.used
            result.updated_at = utc_now()
            self.jobs.save_result(result)
            self._save_progress(
                job_id,
                JobStatus.blocked,
                "blocked",
                1.0,
                completed_chunks,
                total_chunks,
                budget.used,
                result.errors,
                result_available=True,
            )
        except BudgetExceeded as exc:
            result.errors.append(str(exc))
            result.status = JobStatus.partial
            self._finalize_partial(result, mode, warnings)
            result.api_requests = budget.used
            result.updated_at = utc_now()
            self.jobs.save_result(result)
            self._save_progress(
                job_id,
                JobStatus.partial,
                "budget_stopped",
                1.0,
                completed_chunks,
                total_chunks,
                budget.used,
                result.errors,
                result_available=True,
            )
        except Exception as exc:  # noqa: BLE001 - convert to a safe job failure
            logger.exception("Job %s failed", job_id)
            result.errors.append(f"{type(exc).__name__}: {exc}")
            result.status = JobStatus.failed
            self._finalize_partial(result, mode, warnings)
            result.api_requests = budget.used
            result.updated_at = utc_now()
            self.jobs.save_result(result)
            self._save_progress(
                job_id,
                JobStatus.failed,
                "failed",
                1.0,
                completed_chunks,
                total_chunks,
                budget.used,
                result.errors,
                result_available=True,
            )
        finally:
            logger.info(
                "Job %s finished in %dms with %d requests",
                job_id,
                int((time.monotonic() - started) * 1000),
                budget.used,
            )

    def _ordered_images(self, session, request: OCRJobRequest):
        images = session.images
        by_id = {item.image_id: item for item in images}
        requested = request.image_order or request.image_ids
        if not requested:
            return sorted(images, key=lambda item: item.order)
        unique: list[str] = []
        for image_id in requested:
            if image_id not in by_id:
                raise ValueError(f"图片 {image_id} 不属于该会话。")
            if image_id not in unique:
                unique.append(image_id)
        if len(unique) != len(requested):
            raise ValueError("图片顺序中存在重复项。")
        return [by_id[image_id] for image_id in unique]

    def _review_reasons(
        self,
        text: str,
        quality_needs_review: bool,
        quality_flags: list[str],
        risk_flags: list[str],
    ) -> list[str]:
        reasons: list[str] = []
        if quality_needs_review:
            reasons.extend(f"quality:{flag}" for flag in quality_flags)
        if "output_truncated" in risk_flags:
            reasons.append("output_truncated")
        if CRITICAL_CONTENT_RE.search(text):
            reasons.append("critical_fields")
        if _looks_like_table(text):
            reasons.append("table_like")
        if (
            self.settings.review_sample_rate > 0
            and random.random() < self.settings.review_sample_rate
        ):
            reasons.append("random_sample")
        return reasons

    async def _run_cloud_review(
        self,
        chunk: ChunkResult,
        chunk_bytes: bytes,
        mime: str,
        mode: str,
        budget: JobBudget,
        use_cache: bool,
    ) -> int:
        try:
            response = await self.client.ocr_chunk(
                model=self.settings.review_model,
                image_bytes=chunk_bytes,
                mime=mime,
                mode=mode,
                budget=budget,
                allow_cache=use_cache,
            )
        except (PolicyViolation, AuthError, PaymentRejectedError, BudgetExceeded):
            raise
        except OCRRequestError as exc:
            chunk.review_reasons.append(f"review_failed:{exc}")
            return 0
        review_text = strip_artifacts(response.text)
        similarity, conflicts = compare_versions(
            chunk.text, review_text, self.settings.review_model, chunk.index
        )
        apply_review(
            chunk,
            review_text,
            self.settings.review_model,
            similarity,
            conflicts,
        )
        return response.attempts

    async def _run_local_crosscheck(self, chunk: ChunkResult, image: Image.Image, plan) -> None:
        if not self.local_ocr.available():
            return
        crop = image.crop((0, plan.y0, image.width, plan.y1))
        local = self.local_ocr.run(crop)
        if local.error or not local.text:
            chunk.review_reasons.append(f"local_unavailable:{local.error or 'empty'}")
            return
        similarity, conflicts = compare_versions(chunk.text, local.text, local.engine, chunk.index)
        chunk.local_text = local.text
        chunk.local_engine = local.engine
        chunk.consistency_score = (
            min(chunk.consistency_score, round(similarity, 4))
            if chunk.consistency_score is not None
            else round(similarity, 4)
        )
        chunk.conflicts.extend(conflicts)
        if similarity < 0.88:
            chunk.review_reasons.append(f"local_divergence:{similarity:.2f}")
            chunk.needs_review = True
            chunk.uncertain = True
        if chunk.conflicts:
            chunk.needs_review = True
            chunk.uncertain = True

    async def _local_fallback(
        self,
        chunk: ChunkResult,
        image: Image.Image,
        plan,
        local_available: bool,
        error: Exception | None,
    ) -> None:
        if not local_available:
            chunk.error = str(error) if error else "云端 OCR 失败，且本地 OCR 不可用"
            chunk.api_requests += getattr(error, "attempts", 0)
            chunk.needs_review = True
            return
        crop = image.crop((0, plan.y0, image.width, plan.y1))
        local = self.local_ocr.run(crop)
        chunk.api_requests += getattr(error, "attempts", 0)
        if local.error or not local.text:
            chunk.error = (
                f"云端失败：{error}；本地失败：{local.error or '无文字'}"
                if error
                else f"本地 OCR 失败：{local.error or '无文字'}"
            )
            chunk.needs_review = True
            return
        chunk.text = local.text
        chunk.engine = local.engine
        chunk.local_text = local.text
        chunk.local_engine = local.engine
        chunk.layout_method = "local_xy_cut"
        chunk.layout_blocks = [
            LayoutBlock(
                label="text",
                bbox=[
                    round(max(0.0, min(float(image.width), line.box[0])), 1),
                    round(max(0.0, min(float(image.height), plan.y0 + line.box[1])), 1),
                    round(max(0.0, min(float(image.width), line.box[2])), 1),
                    round(max(0.0, min(float(image.height), plan.y0 + line.box[3])), 1),
                ],
                text=line.text,
            )
            for line in local.lines
            if line.text.strip()
        ]
        chunk.review_reasons.append(
            f"local_fallback_after_cloud_error:{type(error).__name__ if error else 'no_api_key'}"
        )
        scores = [line.score for line in local.lines if line.score is not None]
        chunk.confidence = round(sum(scores) / len(scores), 4) if scores else None
        chunk.needs_review = bool(error)

    def _finalize_image(self, image: ImageResult, mode: str, warnings: list[str]) -> None:
        successful = [
            (chunk.text, chunk.y0, chunk.y1)
            for chunk in image.chunks
            if chunk.text and not (chunk.error and chunk.engine is None)
        ]
        merged = merge_chunk_texts(successful)
        image.text = to_plain_text(merged.text)
        image.overlap_removed_lines = merged.removed_line_count
        image.markdown = merged.text if mode == "markdown" else to_markdown(image.text)
        if merged.notes:
            image.warnings.extend(merged.notes)
        if merged.removed_lines:
            image.warnings.append(
                f"重叠去重移除 {len(merged.removed_lines)} 行（保留在 JSON 审计字段中）"
            )

        all_fields = []
        for chunk in image.chunks:
            if chunk.text:
                all_fields.extend(extract_key_fields(to_plain_text(chunk.text), chunk.index))
        if image.text:
            all_fields.extend(extract_key_fields(image.text))
        image.key_fields = merge_key_fields(all_fields)
        for field in image.key_fields:
            if field.confidence == "conflict":
                image.warnings.append(f"关键字段冲突：{field.name} = {field.value}")
                image.needs_manual_check = True

        for issue in percent_issues(image.text):
            image.warnings.append(f"数字校验：{issue}")
            image.needs_manual_check = True

        for chunk in image.chunks:
            if chunk.needs_review or chunk.uncertain or chunk.conflicts or chunk.error:
                image.needs_manual_check = True
            if chunk.engine and chunk.engine.startswith("local:"):
                image.warnings.append(f"分块 {chunk.index} 使用本地 OCR（{chunk.engine}）")
            if chunk.review_reasons:
                image.warnings.append(
                    f"分块 {chunk.index} 复核原因：{', '.join(chunk.review_reasons[:4])}"
                )

        if not image.text:
            image.errors.append("未得到任何文字结果。")
            image.needs_manual_check = True
        if image.errors:
            image.needs_manual_check = True
        image.api_requests = sum(chunk.api_requests for chunk in image.chunks)
        ink_values = [
            (chunk.y1 - chunk.y0, chunk.ink_ratio or 0.0)
            for chunk in image.chunks
            if chunk.y1 > chunk.y0
        ]
        if ink_values:
            total_height = sum(height for height, _ in ink_values)
            if total_height:
                image.ink_coverage = round(
                    sum(height * ratio for height, ratio in ink_values) / total_height,
                    4,
                )

    def _finalize_partial(self, result: JobResult, mode: str, warnings: list[str]) -> None:
        for image in result.images:
            if image.chunks and image.duration_ms == 0:
                self._finalize_image(image, mode, warnings)
        self._finalize_job(result, mode)

    def _finalize_job(self, result: JobResult, mode: str) -> None:
        result.text = "\n\n".join(
            image.text.strip() for image in result.images if image.text.strip()
        ).strip()
        result.markdown = build_document_markdown(
            [(image.filename, image.markdown) for image in result.images],
            already_markdown=(mode == "markdown"),
        )
        result.needs_manual_check = any(image.needs_manual_check for image in result.images)
        for image in result.images:
            for warning in image.warnings:
                if warning not in result.warnings:
                    result.warnings.append(warning)
            for error in image.errors:
                if error not in result.errors:
                    result.errors.append(error)
        result.completed_chunks = sum(len(image.chunks) for image in result.images)
        result.updated_at = utc_now()

    async def _write_snapshot(
        self,
        result: JobResult,
        job_id: str,
        *,
        stage: str,
        progress: float,
        completed: int,
        total: int,
        requests: int,
        errors: list[str],
    ) -> None:
        result.updated_at = utc_now()
        result.completed_chunks = completed
        result.total_chunks = total
        result.api_requests = requests
        result.errors = list(errors)
        self.jobs.save_result(result)
        self._save_progress(
            job_id,
            JobStatus.running,
            stage,
            min(0.99, progress),
            completed,
            total,
            requests,
            errors,
            result_available=True,
        )

    def _save_progress(
        self,
        job_id: str,
        status: JobStatus,
        stage: str,
        progress: float,
        completed: int,
        total: int,
        requests: int,
        errors: list[str],
        *,
        result_available: bool,
    ) -> None:
        self.jobs.save_progress(
            JobProgress(
                job_id=job_id,
                status=status,
                stage=stage,
                progress=round(progress, 3),
                completed_chunks=completed,
                total_chunks=total,
                api_requests=requests,
                errors=errors,
                updated_at=utc_now(),
                result_available=result_available,
            )
        )

    async def _fail_early(
        self,
        job_id: str,
        request: OCRJobRequest,
        message: str,
        *,
        status: JobStatus,
    ) -> None:
        result = JobResult(
            job_id=job_id,
            status=status,
            created_at=utc_now(),
            updated_at=utc_now(),
            errors=[message],
            policy=self.policy.status(),
            options={
                "mode": request.mode or self.settings.prompt_mode,
                "variant": request.variant or "D",
            },
        )
        self.jobs.save_result(result)
        self._save_progress(
            job_id, status, "blocked", 1.0, 0, 0, 0, [message], result_available=True
        )

    def apply_edits(self, job_id: str, documents: list[EditDocument]) -> JobResult:
        result = self.jobs.load_result(job_id)
        if result.status not in {JobStatus.completed, JobStatus.partial}:
            raise ValueError("任务尚未完成，无法编辑。")
        by_id = {image.image_id: image for image in result.images}
        for document in documents:
            image = by_id.get(document.image_id)
            if image is None:
                raise ValueError(f"图片 {document.image_id} 不在结果中。")
            image.text = document.text
            image.edited = True
            mode = (result.options or {}).get("mode", self.settings.prompt_mode)
            image.markdown = to_markdown(image.text, already_markdown=(mode == "markdown"))
            image.key_fields = merge_key_fields(extract_key_fields(image.text))
        mode = (result.options or {}).get("mode", self.settings.prompt_mode)
        self._finalize_job(result, mode)
        result.updated_at = utc_now()
        self.jobs.save_result(result)
        return result


def _looks_like_table(text: str) -> bool:
    for line in text.splitlines():
        if line.count("|") >= 2 or "\t" in line:
            return True
        columns = re.split(r"\s{3,}", line.strip())
        if len(columns) >= 3 and sum(len(part) <= 20 for part in columns) >= 3:
            return True
    return False


__all__ = ["JobConflictError", "OCRPipeline", "VARIANTS"]
