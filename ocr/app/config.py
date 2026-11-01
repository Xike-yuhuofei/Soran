from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime configuration.

    Secrets are held as ``SecretStr`` and are never returned by API responses.
    """

    model_config = SettingsConfigDict(
        env_prefix="OCR_",
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    siliconflow_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "OCR_SILICONFLOW_API_KEY", "SILICONFLOW_API_KEY", "SF_API_KEY"
        ),
    )
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    pricing_page_url: str = "https://www.siliconflow.cn/pricing"

    primary_model: str = "deepseek-ai/DeepSeek-OCR"
    review_model: str = "PaddlePaddle/PaddleOCR-VL-1.5"
    review_enabled: bool = False
    prompt_mode: str = "auto"  # text | markdown | auto

    chunk_target_height: int = 1200
    chunk_min_height: int = 760
    chunk_max_height: int = 1600
    chunk_overlap: int = 120
    chunk_max_width: int = 1400
    chunk_max_pixels: int = 1_500_000

    max_upload_bytes: int = 30 * 1024 * 1024
    max_image_pixels: int = 80_000_000
    max_image_width: int = 8000
    max_image_height: int = 40_000
    max_files_per_session: int = 12

    max_requests_per_job: int = 80
    max_requests_per_day: int = 200
    max_concurrent_requests: int = 2
    request_min_interval_ms: int = 200
    request_timeout_seconds: float = 120.0
    max_retries: int = 3
    max_output_tokens: int = 6000

    policy_refresh_seconds: int = 3600
    policy_max_snapshot_age_hours: int = 24

    cache_enabled: bool = True
    cache_ttl_days: int = 30
    data_dir: Path = Field(default_factory=lambda: BASE_DIR / ".data")

    local_ocr_enabled: bool = False
    local_ocr_model: str = "PP-OCRv6"

    review_sample_rate: float = 0.0
    max_reviews_per_job: int = 40

    # Hard-coded safety rails. These cannot be relaxed by request payloads.
    require_cloud_consent: bool = True
    allow_paid_models: bool = False

    @property
    def api_key_value(self) -> str | None:
        return self.siliconflow_api_key.get_secret_value() if self.siliconflow_api_key else None

    @property
    def api_key_configured(self) -> bool:
        return bool(self.api_key_value)

    @property
    def sessions_dir(self) -> Path:
        return self.data_dir / "sessions"

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def policy_snapshot_path(self) -> Path:
        return self.data_dir / "free_models_snapshot.json"

    def validate(self) -> None:
        if not self.data_dir.is_absolute():
            self.data_dir = BASE_DIR / self.data_dir
        if self.prompt_mode not in {"text", "markdown", "auto"}:
            raise ValueError("OCR_PROMPT_MODE must be 'text', 'markdown' or 'auto'")
        if not (200 <= self.chunk_min_height <= self.chunk_target_height <= self.chunk_max_height):
            raise ValueError("chunk heights must satisfy min <= target <= max")
        if self.chunk_overlap < 0 or self.chunk_overlap >= self.chunk_min_height:
            raise ValueError("OCR_CHUNK_OVERLAP must be >= 0 and smaller than min chunk height")
        if self.max_image_height <= 0 or self.max_image_width <= 0:
            raise ValueError("image dimension limits must be positive")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate()
    return settings
