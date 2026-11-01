from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    partial = "partial"
    failed = "failed"
    blocked = "blocked"


class ImageInfo(BaseModel):
    image_id: str
    filename: str
    width: int
    height: int
    order: int
    sha256: str
    preview_url: str


class SessionInfo(BaseModel):
    session_id: str
    created_at: datetime
    images: list[ImageInfo]


class ChunkResult(BaseModel):
    chunk_id: str
    index: int
    image_id: str
    y0: int
    y1: int
    overlap_top: int
    overlap_bottom: int
    scale: float
    forced_cut: bool
    risk_flags: list[str] = Field(default_factory=list)
    text: str = ""
    engine: str | None = None
    raw_text: str | None = None
    confidence: float | None = None
    quality_score: float | None = None
    consistency_score: float | None = None
    quality_flags: list[str] = Field(default_factory=list)
    review_reasons: list[str] = Field(default_factory=list)
    needs_review: bool = False
    reviewed: bool = False
    review_text: str | None = None
    review_engine: str | None = None
    local_text: str | None = None
    local_engine: str | None = None
    layout_method: str | None = None
    layout_blocks: list[LayoutBlock] = Field(default_factory=list)
    original_text: str | None = None
    original_engine: str | None = None
    original_confidence: float | None = None
    original_layout_method: str | None = None
    original_layout_blocks: list[LayoutBlock] = Field(default_factory=list)
    manual_override: bool = False
    override_source: str | None = None
    conflicts: list[TextConflict] = Field(default_factory=list)
    uncertain: bool = False
    error: str | None = None
    from_cache: bool = False
    usage: dict[str, Any] | None = None
    latency_ms: int | None = None
    api_requests: int = 0
    ink_ratio: float | None = None
    overlap_ink_ratio: float | None = None


class TextConflict(BaseModel):
    kind: str
    detail: str
    primary: str
    secondary: str | None = None
    severity: str = "warning"


class LayoutBlock(BaseModel):
    label: str
    bbox: list[float]  # original-image coordinates: x0, y0, x1, y1
    text: str


class KeyField(BaseModel):
    name: str
    value: str
    chunk_index: int | None = None
    confidence: str = "unverified"  # unverified | cross_checked | conflict
    note: str | None = None


class ImageResult(BaseModel):
    image_id: str
    filename: str
    order: int
    width: int
    height: int
    text: str
    markdown: str
    chunks: list[ChunkResult] = Field(default_factory=list)
    key_fields: list[KeyField] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    needs_manual_check: bool = False
    edited: bool = False
    api_requests: int = 0
    duration_ms: int = 0
    ink_coverage: float | None = None
    overlap_removed_lines: int = 0


class JobResult(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    images: list[ImageResult] = Field(default_factory=list)
    text: str = ""
    markdown: str = ""
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    needs_manual_check: bool = False
    api_requests: int = 0
    budget: dict[str, Any] = Field(default_factory=dict)
    policy: dict[str, Any] = Field(default_factory={})
    options: dict[str, Any] = Field(default_factory={})
    total_chunks: int = 0
    completed_chunks: int = 0


class JobProgress(BaseModel):
    job_id: str
    status: JobStatus
    stage: str
    progress: float
    completed_chunks: int
    total_chunks: int
    api_requests: int
    errors: list[str] = Field(default_factory=list)
    updated_at: datetime
    result_available: bool


class OCRJobRequest(BaseModel):
    session_id: str
    image_ids: list[str] | None = None
    image_order: list[str] | None = None
    mode: str | None = None
    consent_cloud_upload: bool = False
    use_review: bool = True
    use_cache: bool = True
    variant: str | None = None  # A | B | C | D (evaluation baselines)


class EditDocument(BaseModel):
    image_id: str
    text: str


class EditResultRequest(BaseModel):
    documents: list[EditDocument]


class ApplyChunkRequest(BaseModel):
    image_id: str
    chunk_index: int
    source: str = "review"  # review | primary
