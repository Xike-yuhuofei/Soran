from __future__ import annotations

import asyncio
import logging
import re
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import Settings, get_settings
from .imaging import ImageValidationError, validate_image_bytes
from .local_ocr import LocalPaddleOCR
from .pipeline import JobConflictError, OCRPipeline
from .policy import FreePolicy, PolicyViolation
from .schemas import (
    ApplyChunkRequest,
    EditResultRequest,
    JobProgress,
    JobResult,
    JobStatus,
    OCRJobRequest,
    SessionInfo,
    utc_now,
)
from .siliconflow import AuthError, PaymentRejectedError, SiliconFlowOCRClient
from .storage import (
    BudgetExceeded,
    ChunkCache,
    JobStore,
    SessionStore,
    StorageError,
    UsageLedger,
)

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"


def _safe_filename(name: str) -> str:
    base = Path(name).name
    base = re.sub(r"[\x00-\x1f\x7f]", "", base)
    return base[:180] or "image"


def create_app(
    settings: Settings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    settings.validate()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "sessions").mkdir(exist_ok=True)
    (settings.data_dir / "jobs").mkdir(exist_ok=True)
    (settings.data_dir / "cache" / "chunks").mkdir(parents=True, exist_ok=True)

    policy = FreePolicy(settings, transport=transport)
    cache = ChunkCache(settings)
    sessions = SessionStore(settings)
    jobs = JobStore(settings)
    ledger = UsageLedger(settings)
    local_ocr = LocalPaddleOCR(settings)
    client = SiliconFlowOCRClient(settings, policy, cache, transport=transport)
    pipeline = OCRPipeline(settings, policy, client, sessions, jobs, ledger, local_ocr)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        refresh_task = asyncio.create_task(policy.refresh())
        try:
            yield
        finally:
            if not refresh_task.done():
                refresh_task.cancel()

    app = FastAPI(
        title="Soran OCR",
        version=__version__,
        description="电商详情页长图 OCR · 免费模型白名单 · 分块合并与质量复核",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.policy = policy
    app.state.cache = cache
    app.state.sessions = sessions
    app.state.jobs = jobs
    app.state.ledger = ledger
    app.state.pipeline = pipeline
    app.state.client = client
    app.state.local_ocr = local_ocr

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(StorageError)
    async def storage_error(_: Request, exc: StorageError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ImageValidationError)
    async def image_error(_: Request, exc: ImageValidationError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(PolicyViolation)
    async def policy_error(_: Request, exc: PolicyViolation):
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(AuthError)
    async def auth_error(_: Request, exc: AuthError):
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(PaymentRejectedError)
    async def payment_error(_: Request, exc: PaymentRejectedError):
        return JSONResponse(status_code=402, content={"detail": str(exc)})

    @app.exception_handler(BudgetExceeded)
    async def budget_error(_: Request, exc: BudgetExceeded):
        return JSONResponse(status_code=429, content={"detail": str(exc)})

    @app.exception_handler(JobConflictError)
    async def conflict_error(_: Request, exc: JobConflictError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": __version__,
            "api_key_configured": settings.api_key_configured,
            "primary_model": settings.primary_model,
            "review_model": settings.review_model,
            "review_enabled": settings.review_enabled,
            "local_ocr": local_ocr.status(),
            "cache": cache.stats(),
            "daily_usage": await ledger.today(),
            "free_policy": policy.status(),
        }

    @app.get("/api/config")
    async def public_config() -> dict[str, Any]:
        return {
            "version": __version__,
            "primary_model": settings.primary_model,
            "review_model": settings.review_model,
            "review_enabled": settings.review_enabled,
            "prompt_mode": settings.prompt_mode,
            "max_files": settings.max_files_per_session,
            "max_upload_mb": settings.max_upload_bytes // (1024 * 1024),
            "max_requests_per_job": settings.max_requests_per_job,
            "max_requests_per_day": settings.max_requests_per_day,
            "require_cloud_consent": settings.require_cloud_consent,
            "api_key_configured": settings.api_key_configured,
            "chunk": {
                "target_height": settings.chunk_target_height,
                "overlap": settings.chunk_overlap,
                "max_width": settings.chunk_max_width,
            },
        }

    @app.get("/api/policy")
    async def policy_status(refresh: bool = Query(default=False)) -> dict[str, Any]:
        if refresh:
            await policy.refresh(force=True)
        data = policy.status()
        data["api_key_configured"] = settings.api_key_configured
        data["primary_model"] = settings.primary_model
        data["review_model"] = settings.review_model
        return data

    @app.post("/api/sessions", response_model=SessionInfo)
    async def create_session(files: list[UploadFile] = File(...)) -> SessionInfo:
        if not files:
            raise HTTPException(status_code=400, detail="请至少上传一张图片。")
        if len(files) > settings.max_files_per_session:
            raise HTTPException(
                status_code=400,
                detail=f"一次最多上传 {settings.max_files_per_session} 张图片。",
            )
        session_id, session_dir = sessions.create()
        images = []
        try:
            for index, upload in enumerate(files):
                raw = await upload.read()
                loaded = validate_image_bytes(raw, settings)
                info = sessions.add_image(
                    session_dir,
                    order=index,
                    filename=_safe_filename(upload.filename or f"image-{index + 1}"),
                    image=loaded.image,
                    sha256=loaded.sha256,
                    source_format=loaded.source_format,
                )
                images.append(info)
            session = SessionInfo(
                session_id=session_id,
                created_at=utc_now(),
                images=images,
            )
            sessions.save_session(session_dir, session)
            return session
        except Exception:
            shutil.rmtree(session_dir, ignore_errors=True)
            raise

    @app.get("/api/sessions/{session_id}", response_model=SessionInfo)
    async def get_session(session_id: str) -> SessionInfo:
        return sessions.load_session(session_id)

    @app.post("/api/sessions/{session_id}/images", response_model=SessionInfo)
    async def append_images(
        session_id: str,
        files: list[UploadFile] = File(...),
    ) -> SessionInfo:
        session = sessions.load_session(session_id)
        if len(session.images) + len(files) > settings.max_files_per_session:
            raise HTTPException(
                status_code=400,
                detail=f"每个会话最多 {settings.max_files_per_session} 张图片。",
            )
        session_dir = settings.sessions_dir / session_id
        added = []
        added_paths: list[Path] = []
        try:
            for upload in files:
                raw = await upload.read()
                loaded = validate_image_bytes(raw, settings)
                info = sessions.add_image(
                    session_dir,
                    order=len(session.images) + len(added),
                    filename=_safe_filename(upload.filename or "image"),
                    image=loaded.image,
                    sha256=loaded.sha256,
                    source_format=loaded.source_format,
                )
                added.append(info)
                for suffix in (".png", ".jpg"):
                    candidate = session_dir / "images" / f"{info.image_id}{suffix}"
                    if candidate.exists():
                        added_paths.append(candidate)
                added_paths.append(session_dir / "images" / f"{info.image_id}_thumb.jpg")
            session.images.extend(added)
            session.created_at = utc_now()
            sessions.save_session(session_dir, session)
            return session
        except Exception:
            for path in added_paths:
                path.unlink(missing_ok=True)
            raise

    @app.get("/api/sessions/{session_id}/images/{image_id}/preview")
    async def preview(
        session_id: str,
        image_id: str,
        full: bool = Query(default=False),
    ):
        path = (
            sessions.image_path(session_id, image_id)
            if full
            else sessions.thumbnail_path(session_id, image_id)
        )
        media = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
        return FileResponse(
            path, media_type=media, headers={"Cache-Control": "private, max-age=3600"}
        )

    @app.post("/api/ocr/jobs")
    async def create_job(
        payload: OCRJobRequest,
        background: BackgroundTasks,
    ) -> dict[str, Any]:
        if settings.require_cloud_consent and not payload.consent_cloud_upload:
            raise HTTPException(
                status_code=400,
                detail="必须先明确确认图片将上传到云端 OCR 服务。",
            )
        session = sessions.load_session(payload.session_id)
        requested_ids = payload.image_order or payload.image_ids
        if requested_ids:
            known = {image.image_id for image in session.images}
            missing = [image_id for image_id in requested_ids if image_id not in known]
            if missing:
                raise HTTPException(status_code=400, detail=f"未知图片：{missing[0]}")
        if payload.mode and payload.mode not in {"text", "markdown", "auto"}:
            raise HTTPException(status_code=400, detail="mode 必须是 text、markdown 或 auto。")
        if payload.variant and payload.variant.upper() not in {"A", "B", "C", "D"}:
            raise HTTPException(status_code=400, detail="variant 必须是 A/B/C/D。")

        job_id = jobs.create(payload.model_dump())
        jobs.save_progress(
            JobProgress(
                job_id=job_id,
                status=JobStatus.queued,
                stage="queued",
                progress=0.0,
                completed_chunks=0,
                total_chunks=0,
                api_requests=0,
                errors=[],
                updated_at=utc_now(),
                result_available=False,
            )
        )
        background.add_task(pipeline.run_job, job_id)
        return {
            "job_id": job_id,
            "status_url": f"/api/ocr/jobs/{job_id}",
            "result_url": f"/api/ocr/jobs/{job_id}/result",
        }

    @app.get("/api/ocr/jobs/{job_id}", response_model=JobProgress)
    async def get_progress(job_id: str) -> JobProgress:
        return jobs.load_progress(job_id)

    @app.post("/api/ocr/jobs/{job_id}/resume")
    async def resume_job(
        job_id: str,
        background: BackgroundTasks,
    ) -> dict[str, Any]:
        progress = jobs.load_progress(job_id)
        if progress.status == JobStatus.running:
            raise HTTPException(status_code=409, detail="任务正在运行。")
        if progress.status == JobStatus.completed:
            raise HTTPException(status_code=400, detail="任务已完成，无需继续。")
        jobs.save_progress(
            JobProgress(
                job_id=job_id,
                status=JobStatus.queued,
                stage="queued",
                progress=0.0,
                completed_chunks=progress.completed_chunks,
                total_chunks=progress.total_chunks,
                api_requests=progress.api_requests,
                errors=progress.errors,
                updated_at=utc_now(),
                result_available=progress.result_available,
            )
        )
        background.add_task(pipeline.run_job, job_id, resume=True)
        return {"job_id": job_id, "status_url": f"/api/ocr/jobs/{job_id}"}

    @app.get("/api/ocr/jobs/{job_id}/result", response_model=JobResult)
    async def get_result(job_id: str) -> JobResult:
        try:
            return jobs.load_result(job_id)
        except StorageError:
            raise HTTPException(status_code=404, detail="结果尚未生成。") from None

    @app.put("/api/ocr/jobs/{job_id}/result", response_model=JobResult)
    async def edit_result(job_id: str, payload: EditResultRequest) -> JobResult:
        try:
            return pipeline.apply_edits(job_id, payload.documents)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ocr/jobs/{job_id}/chunks/apply", response_model=JobResult)
    async def apply_chunk(job_id: str, payload: ApplyChunkRequest) -> JobResult:
        try:
            return pipeline.apply_chunk_text(
                job_id,
                image_id=payload.image_id,
                chunk_index=payload.chunk_index,
                source=payload.source,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/ocr/jobs/{job_id}/export")
    async def export(job_id: str, format: str = Query(default="txt")) -> Response:
        result = jobs.load_result(job_id)
        fmt = format.lower()
        short = job_id[:8]
        if fmt == "txt":
            return Response(
                content=result.text,
                media_type="text/plain; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="soran-ocr-{short}.txt"'},
            )
        if fmt == "md":
            return Response(
                content=result.markdown,
                media_type="text/markdown; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="soran-ocr-{short}.md"'},
            )
        if fmt == "json":
            return Response(
                content=result.model_dump_json(indent=2),
                media_type="application/json; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="soran-ocr-{short}.json"'},
            )
        raise HTTPException(status_code=400, detail="format 必须是 txt、md 或 json。")

    @app.get("/")
    async def index():
        return FileResponse(STATIC_DIR / "index.html", media_type="text/html; charset=utf-8")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


app = create_app()
