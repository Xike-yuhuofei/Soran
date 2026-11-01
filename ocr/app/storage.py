from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from PIL import Image

from .config import Settings
from .schemas import ImageInfo, JobProgress, JobResult, SessionInfo

_ID_RE = re.compile(r"^[a-f0-9-]{36}$")


class StorageError(ValueError):
    pass


def new_id() -> str:
    return str(uuid.uuid4())


def validate_id(value: str, label: str = "id") -> str:
    if not _ID_RE.match(value):
        raise StorageError(f"非法的 {label}。")
    return value


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


class SessionStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = settings.sessions_dir

    def create(self) -> tuple[str, Path]:
        session_id = new_id()
        path = self.root / session_id
        path.mkdir(parents=True, exist_ok=False)
        return session_id, path

    def add_image(
        self,
        session_dir: Path,
        order: int,
        filename: str,
        image: Image.Image,
        sha256: str,
        source_format: str,
    ) -> ImageInfo:
        from .imaging import save_normalized, save_thumbnail

        image_id = new_id()
        images_dir = session_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        suffix = ".jpg" if image.width * image.height > 20_000_000 else ".png"
        normalized_path = images_dir / f"{image_id}{suffix}"
        save_normalized(image, normalized_path)
        thumb_path = images_dir / f"{image_id}_thumb.jpg"
        save_thumbnail(image, thumb_path)
        return ImageInfo(
            image_id=image_id,
            filename=filename[:180] or "image",
            width=image.width,
            height=image.height,
            order=order,
            sha256=sha256,
            preview_url=f"/api/sessions/{session_dir.name}/images/{image_id}/preview",
        )

    def save_session(self, session_dir: Path, session: SessionInfo) -> None:
        atomic_write_json(session_dir / "session.json", session.model_dump())

    def load_session(self, session_id: str) -> SessionInfo:
        session_id = validate_id(session_id, "session_id")
        path = self.root / session_id / "session.json"
        if not path.exists():
            raise StorageError("会话不存在或已失效。")
        return SessionInfo.model_validate(read_json(path))

    def image_path(self, session_id: str, image_id: str) -> Path:
        session_id = validate_id(session_id, "session_id")
        image_id = validate_id(image_id, "image_id")
        session_dir = self.root / session_id
        for suffix in (".png", ".jpg"):
            path = session_dir / "images" / f"{image_id}{suffix}"
            if path.exists():
                return path
        raise StorageError("图片不存在。")

    def thumbnail_path(self, session_id: str, image_id: str) -> Path:
        session_id = validate_id(session_id, "session_id")
        image_id = validate_id(image_id, "image_id")
        path = self.root / session_id / "images" / f"{image_id}_thumb.jpg"
        if not path.exists():
            raise StorageError("缩略图不存在。")
        return path


class JobStore:
    def __init__(self, settings: Settings):
        self.root = settings.jobs_dir

    def create(self, request_payload: dict[str, Any]) -> str:
        job_id = new_id()
        path = self.root / job_id
        path.mkdir(parents=True, exist_ok=False)
        atomic_write_json(path / "request.json", request_payload)
        return job_id

    def _dir(self, job_id: str) -> Path:
        return self.root / validate_id(job_id, "job_id")

    def save_progress(self, progress: JobProgress) -> None:
        atomic_write_json(self._dir(progress.job_id) / "progress.json", progress.model_dump())

    def load_progress(self, job_id: str) -> JobProgress:
        path = self._dir(job_id) / "progress.json"
        if not path.exists():
            raise StorageError("任务不存在。")
        return JobProgress.model_validate(read_json(path))

    def save_result(self, result: JobResult) -> None:
        atomic_write_json(self._dir(result.job_id) / "result.json", result.model_dump())

    def load_result(self, job_id: str) -> JobResult:
        path = self._dir(job_id) / "result.json"
        if not path.exists():
            raise StorageError("结果尚未生成。")
        return JobResult.model_validate(read_json(path))

    def has_result(self, job_id: str) -> bool:
        return (self._dir(job_id) / "result.json").exists()

    def load_request(self, job_id: str) -> dict[str, Any]:
        path = self._dir(job_id) / "request.json"
        if not path.exists():
            raise StorageError("任务请求不存在。")
        return read_json(path)

    def delete_result(self, job_id: str) -> None:
        path = self._dir(job_id) / "result.json"
        if path.exists():
            path.unlink()


class UsageLedger:
    """Persistent request counter (UTC day). Application-level only; it does
    not replace account-level billing protection on the cloud provider.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.path = settings.data_dir / "usage.json"
        self._lock = asyncio.Lock()

    def _load(self, strict: bool = False) -> dict[str, Any]:
        if not self.path.exists():
            return {"dates": {}}
        try:
            data = read_json(self.path)
            if not isinstance(data, dict):
                raise ValueError("usage ledger is not an object")
            data.setdefault("dates", {})
            return data
        except (OSError, ValueError):
            if strict:
                raise BudgetExceeded(
                    "请求额度账本损坏，已阻止云端请求。请检查或备份后删除 usage.json。"
                ) from None
            return {"dates": {}}

    async def today(self) -> dict[str, int]:
        async with self._lock:
            data = self._load()
            key = datetime.now(UTC).date().isoformat()
            entry = data["dates"].get(key, {})
            return {
                "attempts": int(entry.get("attempts", 0)),
                "successes": int(entry.get("successes", 0)),
                "failures": int(entry.get("failures", 0)),
            }

    async def reserve_attempt(self) -> dict[str, int]:
        async with self._lock:
            data = self._load(strict=True)
            key = datetime.now(UTC).date().isoformat()
            entry = data["dates"].setdefault(key, {"attempts": 0, "successes": 0, "failures": 0})
            if entry["attempts"] >= self.settings.max_requests_per_day:
                raise BudgetExceeded(
                    f"今日云端请求次数已达上限 {self.settings.max_requests_per_day}。"
                    "为防止产生费用，已停止新的请求。"
                )
            entry["attempts"] += 1
            entry["updated_at"] = datetime.now(UTC).isoformat()
            # Trim old days.
            cutoff = (datetime.now(UTC).date() - timedelta(days=90)).isoformat()
            data["dates"] = {k: v for k, v in data["dates"].items() if k >= cutoff}
            atomic_write_json(self.path, data)
            return {
                "attempts": int(entry["attempts"]),
                "successes": int(entry.get("successes", 0)),
                "failures": int(entry.get("failures", 0)),
            }

    async def record_outcome(self, success: bool) -> None:
        async with self._lock:
            data = self._load()
            key = datetime.now(UTC).date().isoformat()
            entry = data["dates"].setdefault(key, {"attempts": 0, "successes": 0, "failures": 0})
            if success:
                entry["successes"] = int(entry.get("successes", 0)) + 1
            else:
                entry["failures"] = int(entry.get("failures", 0)) + 1
            atomic_write_json(self.path, data)


class BudgetExceeded(RuntimeError):
    pass


class JobBudget:
    """Per-job request cap, resumable because the count is stored with the job."""

    def __init__(self, settings: Settings, ledger: UsageLedger, job_id: str, initial: int = 0):
        self.settings = settings
        self.ledger = ledger
        self.job_id = job_id
        self.used = initial
        self._lock = asyncio.Lock()
        self.cache_hits = 0

    async def reserve(self) -> None:
        async with self._lock:
            if self.used >= self.settings.max_requests_per_job:
                raise BudgetExceeded(
                    f"单个任务请求次数已达上限 {self.settings.max_requests_per_job}。"
                )
            await self.ledger.reserve_attempt()
            self.used += 1

    async def outcome(self, success: bool) -> None:
        await self.ledger.record_outcome(success)

    @property
    def remaining(self) -> int:
        return max(0, self.settings.max_requests_per_job - self.used)


class ChunkCache:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = settings.cache_dir / "chunks"

    def key(
        self,
        image_bytes: bytes,
        model: str,
        prompt: str,
        mode: str,
        pipeline_version: str,
    ) -> str:
        material = b"\x00".join(
            [
                image_bytes,
                model.encode(),
                prompt.encode(),
                mode.encode(),
                pipeline_version.encode(),
            ]
        )
        return hashlib.sha256(material).hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        if not self.settings.cache_enabled:
            return None
        path = self.root / f"{key}.json"
        if not path.exists():
            return None
        try:
            payload = read_json(path)
            created = datetime.fromisoformat(payload["created_at"])
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            if datetime.now(UTC) - created > timedelta(days=self.settings.cache_ttl_days):
                return None
            return payload
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def put(self, key: str, payload: dict[str, Any]) -> None:
        if not self.settings.cache_enabled:
            return
        payload = dict(payload)
        payload["created_at"] = datetime.now(UTC).isoformat()
        atomic_write_json(self.root / f"{key}.json", payload)

    def stats(self) -> dict[str, int]:
        if not self.root.exists():
            return {"entries": 0, "bytes": 0}
        entries = list(self.root.glob("*.json"))
        return {
            "entries": len(entries),
            "bytes": sum(path.stat().st_size for path in entries),
        }
