from __future__ import annotations

import hashlib
import io
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

from .config import Settings

ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}
ANALYSIS_WIDTH = 600


class ImageValidationError(ValueError):
    pass


@dataclass
class LoadedImage:
    image: Image.Image
    width: int
    height: int
    sha256: str
    source_format: str

    @property
    def pixels(self) -> int:
        return self.width * self.height


@dataclass
class ChunkPlan:
    index: int
    y0: int
    y1: int
    overlap_top: int
    overlap_bottom: int
    scale: float
    crop_width: int
    crop_height: int
    forced_cut: bool = False
    risk_flags: list[str] = field(default_factory=list)

    @property
    def height(self) -> int:
        return self.y1 - self.y0


def _flatten_to_rgb(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"}:
        background = Image.new("RGB", image.size, (255, 255, 255))
        alpha = image.convert("RGBA").split()[-1]
        background.paste(image.convert("RGB"), mask=alpha)
        return background
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def validate_image_bytes(data: bytes, settings: Settings) -> LoadedImage:
    if not data:
        raise ImageValidationError("图片为空。")
    if len(data) > settings.max_upload_bytes:
        raise ImageValidationError(
            f"单张图片超过 {settings.max_upload_bytes // (1024 * 1024)} MB 限制。"
        )
    try:
        with Image.open(io.BytesIO(data)) as probe:
            fmt = (probe.format or "").upper()
            if fmt not in ALLOWED_FORMATS:
                raise ImageValidationError(f"不支持的图片格式：{fmt or '未知'}。")
            if fmt == "WEBP" and getattr(probe, "n_frames", 1) > 1:
                probe.seek(0)
            width, height = probe.size
            if width > settings.max_image_width:
                raise ImageValidationError(
                    f"图片宽度 {width}px 超过上限 {settings.max_image_width}px。"
                )
            if height > settings.max_image_height:
                raise ImageValidationError(
                    f"图片高度 {height}px 超过上限 {settings.max_image_height}px。"
                )
            if width * height > settings.max_image_pixels:
                raise ImageValidationError(
                    f"图片像素数 {width * height} 超过上限 {settings.max_image_pixels}。"
                )
            probe.load()
            normalized = ImageOps.exif_transpose(probe)
    except ImageValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageValidationError(f"图片解码失败：{exc}") from exc

    normalized = _flatten_to_rgb(normalized)
    width, height = normalized.size
    if width * height > settings.max_image_pixels:
        raise ImageValidationError("图片方向校正后像素数超过上限。")

    return LoadedImage(
        image=normalized,
        width=width,
        height=height,
        sha256=hashlib.sha256(data).hexdigest(),
        source_format=fmt,
    )


def save_normalized(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        image.save(path, format="JPEG", quality=95, subsampling=0)
    else:
        image.save(path, format="PNG", compress_level=6)


def save_thumbnail(
    image: Image.Image, path: Path, max_width: int = 560, max_height: int = 1400
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    preview = image
    if image.height / max(1, image.width) > 2.2:
        # Show the top of a very long image instead of generating a huge
        # thumbnail that browsers cannot decode comfortably.
        preview = image.crop((0, 0, image.width, min(image.height, int(image.width * 1.2))))
    scale = min(1.0, max_width / preview.width, max_height / preview.height)
    thumb = preview.resize(
        (max(1, int(preview.width * scale)), max(1, int(preview.height * scale))),
        Image.Resampling.LANCZOS,
    )
    thumb.save(path, format="JPEG", quality=82)


def _border_suppressed_mask(gray: np.ndarray) -> np.ndarray:
    """Return a foreground mask with long table rules suppressed.

    Row projection is used only to find safe cuts. Suppressing long horizontal
    and vertical rules prevents borders from making every row look "inked",
    which would otherwise force cuts through text.
    """

    blurred = np.asarray(
        Image.fromarray(gray).filter(ImageFilter.GaussianBlur(radius=2.5)),
        dtype=np.int16,
    )
    gray_i = gray.astype(np.int16)
    diff = np.abs(gray_i - blurred)
    mask = diff > 16

    height, width = mask.shape
    if height < 3 or width < 3:
        return mask

    # Long, almost-solid horizontal rules (table borders / dividers).
    row_density = mask.mean(axis=1)
    for y in range(1, height - 1):
        if row_density[y] > 0.82 and row_density[y - 1] > 0.82 and row_density[y + 1] > 0.82:
            mask[y] = False

    # Thin, almost-solid vertical rules.
    col_density = mask.mean(axis=0)
    bad_cols = np.where(col_density > 0.78)[0]
    for x in bad_cols:
        left = max(0, x - 2)
        right = min(width, x + 3)
        if (col_density[left:right] > 0.70).all() and (right - left) <= 6:
            mask[:, x] = False

    return mask


def _row_ink_counts(image: Image.Image) -> tuple[np.ndarray, float]:
    scale = min(1.0, ANALYSIS_WIDTH / image.width)
    analysis_height = max(1, int(image.height * scale))
    small = image.convert("L").resize(
        (max(1, int(image.width * scale)), analysis_height),
        Image.Resampling.BILINEAR,
    )
    gray = np.asarray(small, dtype=np.uint8)
    mask = _border_suppressed_mask(gray)
    counts = mask.sum(axis=1).astype(np.int32)
    return counts, scale


def _find_blank_bands(
    counts: np.ndarray,
    scale: float,
    original_height: int,
    width: int,
) -> list[tuple[int, int]]:
    threshold = max(1, int(width * 0.002))
    bands: list[tuple[int, int]] = []
    start: int | None = None
    for y, value in enumerate(counts):
        if int(value) <= threshold:
            if start is None:
                start = y
        else:
            if start is not None:
                y0 = max(0, int(start / scale))
                y1 = min(original_height, int(y / scale))
                bands.append((y0, y1))
                start = None
    if start is not None:
        bands.append((max(0, int(start / scale)), original_height))
    return [(a, b) for a, b in bands if b > a]


def _choose_cut(
    start: int,
    height: int,
    counts: np.ndarray,
    scale: float,
    bands: list[tuple[int, int]],
    settings: Settings,
) -> tuple[int, bool, str | None]:
    target = start + settings.chunk_target_height
    low = start + settings.chunk_min_height
    high = min(height, start + settings.chunk_max_height)

    candidates: list[tuple[float, int, int]] = []
    for band_start, band_end in bands:
        if band_end <= low or band_start >= high:
            continue
        cut = max(band_start, min(band_end - 1, target))
        gap = band_end - band_start
        score = abs(cut - target) - min(gap, 80) * 1.6
        candidates.append((score, cut, gap))
    if candidates:
        _, cut, gap = min(candidates, key=lambda item: item[0])
        if gap < 4:
            return cut, False, "narrow_blank_boundary"
        return cut, False, None

    # Expand the search once before resorting to a non-blank row.
    hard_high = min(height, start + int(settings.chunk_max_height * 1.5))
    expanded = [
        (band_start, band_end)
        for band_start, band_end in bands
        if band_end > low and band_start < hard_high
    ]
    if expanded:
        band_start, band_end = min(
            expanded,
            key=lambda band: abs((band[0] + band[1]) // 2 - target),
        )
        cut = max(band_start, min(band_end - 1, target))
        return cut, False, "expanded_search_boundary"

    # No blank row exists in a usable range (very dense table/graphic).
    # Choose the least-inked row, keep a large overlap downstream, and flag it.
    lo_idx = max(0, int(low * scale))
    hi_idx = min(len(counts), int(hard_high * scale))
    if hi_idx <= lo_idx:
        return min(height, target), True, "no_blank_row"
    window = counts[lo_idx:hi_idx]
    row = lo_idx + int(np.argmin(window))
    cut = min(height, int(row / scale))
    return cut, True, "no_blank_row"


def segment_image(
    image: Image.Image,
    settings: Settings,
    force_single_chunk: bool = False,
) -> list[ChunkPlan]:
    width, height = image.size

    def scale_for(crop_width: int, crop_height: int) -> tuple[float, int, int]:
        scale = min(
            1.0,
            settings.chunk_max_width / crop_width,
            math.sqrt(settings.chunk_max_pixels / (crop_width * crop_height)),
        )
        return (
            scale,
            max(1, int(round(crop_width * scale))),
            max(1, int(round(crop_height * scale))),
        )

    if force_single_chunk or height <= settings.chunk_target_height:
        scale, cw, ch = scale_for(width, height)
        return [
            ChunkPlan(
                index=0,
                y0=0,
                y1=height,
                overlap_top=0,
                overlap_bottom=0,
                scale=scale,
                crop_width=cw,
                crop_height=ch,
                risk_flags=["single_chunk_for_large_image"]
                if height > settings.chunk_max_height
                else [],
            )
        ]

    counts, scale = _row_ink_counts(image)
    bands = _find_blank_bands(counts, scale, height, width)

    chunks: list[ChunkPlan] = []
    start = 0
    hard_limit = settings.chunk_max_height * 3
    while start < height:
        cut, forced, risk = _choose_cut(start, height, counts, scale, bands, settings)

        remaining = height - cut
        # Avoid a tiny final fragment when the current chunk can absorb it.
        if remaining > 0 and remaining < settings.chunk_min_height:
            if cut - start + remaining <= hard_limit:
                cut = height
            else:
                cut = min(height, start + settings.chunk_max_height)

        if cut <= start:
            cut = min(height, start + settings.chunk_min_height)
        cut = min(cut, height)

        scale_value, crop_width, crop_height = scale_for(width, cut - start)
        flags = [risk] if risk else []
        if forced:
            flags.append("cut_may_intersect_dense_content")
        if cut - start < settings.chunk_min_height:
            flags.append("short_chunk")
        chunks.append(
            ChunkPlan(
                index=len(chunks),
                y0=start,
                y1=cut,
                overlap_top=0,
                overlap_bottom=0,
                scale=scale_value,
                crop_width=crop_width,
                crop_height=crop_height,
                forced_cut=forced,
                risk_flags=flags,
            )
        )
        if cut >= height:
            break

        overlap = settings.chunk_overlap
        if forced:
            overlap = min(max(overlap, 240), cut - start - 1)
        next_start = max(0, cut - overlap)
        if next_start <= start:
            next_start = cut
        start = next_start

    for i in range(len(chunks)):
        top = chunks[i - 1].y1 - chunks[i].y0 if i > 0 else 0
        bottom = chunks[i + 1].y0 if i + 1 < len(chunks) else 0
        bottom = chunks[i].y1 - bottom if i + 1 < len(chunks) else 0
        chunks[i].overlap_top = max(0, top)
        chunks[i].overlap_bottom = max(0, bottom)
    return chunks


def render_chunk(
    image: Image.Image,
    chunk: ChunkPlan,
    jpeg_quality: int = 92,
) -> tuple[bytes, str]:
    crop = image.crop((0, chunk.y0, image.width, chunk.y1))
    if (crop.width, crop.height) != (chunk.crop_width, chunk.crop_height):
        crop = crop.resize((chunk.crop_width, chunk.crop_height), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    crop.save(buffer, format="JPEG", quality=jpeg_quality, subsampling=0, optimize=True)
    return buffer.getvalue(), "image/jpeg"


def chunk_ink_ratio(image: Image.Image, y0: int, y1: int) -> float:
    if y1 <= y0:
        return 0.0
    crop = image.crop((0, y0, image.width, y1)).convert("L")
    scale = min(1.0, ANALYSIS_WIDTH / crop.width)
    small = crop.resize(
        (max(1, int(crop.width * scale)), max(1, int(crop.height * scale))),
        Image.Resampling.BILINEAR,
    )
    mask = _border_suppressed_mask(np.asarray(small, dtype=np.uint8))
    return float(mask.mean())
