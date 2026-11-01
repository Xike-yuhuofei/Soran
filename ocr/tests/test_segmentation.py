from __future__ import annotations

import numpy as np
from conftest import make_ecommerce_image
from PIL import Image

from app.imaging import (
    _find_blank_bands,
    _row_ink_counts,
    chunk_ink_ratio,
    render_chunk,
    segment_image,
)


def test_long_image_splits_at_blank_rows(settings):
    image = make_ecommerce_image(height=3000)
    plans = segment_image(image, settings)
    assert len(plans) >= 2
    assert plans[0].y0 == 0
    assert plans[-1].y1 == image.height
    for plan in plans:
        assert plan.y1 > plan.y0
        assert plan.crop_width <= settings.chunk_max_width
        assert plan.crop_height * plan.crop_width <= settings.chunk_max_pixels + 2

    counts, scale = _row_ink_counts(image)
    for plan in plans[:-1]:
        row = min(len(counts) - 1, int(plan.y1 / scale))
        assert counts[row] <= max(1, int(image.width * 0.002)), (
            "cut must not pass through a text row"
        )


def test_overlap_is_preserved(settings):
    image = make_ecommerce_image(height=3000)
    plans = segment_image(image, settings)
    for left, right in zip(plans, plans[1:], strict=False):
        assert left.overlap_bottom > 0
        assert right.overlap_top == left.overlap_bottom
        assert right.y0 == left.y1 - left.overlap_bottom
        assert left.overlap_bottom == settings.chunk_overlap


def test_single_chunk_for_short_image(settings):
    image = Image.new("RGB", (400, 500), "white")
    plans = segment_image(image, settings)
    assert len(plans) == 1
    assert plans[0].y0 == 0 and plans[0].y1 == 500


def test_forced_cut_on_dense_image_is_flagged(settings):
    rng = np.random.default_rng(42)
    noise = rng.integers(0, 255, size=(5000, 600, 3), dtype=np.uint8)
    image = Image.fromarray(noise, mode="RGB")
    plans = segment_image(image, settings)
    assert len(plans) >= 2
    assert any(plan.forced_cut for plan in plans)
    assert plans[-1].y1 == 5000


def test_render_chunk_resizes_and_reports_scale(settings):
    image = Image.new("RGB", (3000, 1500), "white")
    plans = segment_image(image, settings, force_single_chunk=True)
    plan = plans[0]
    assert plan.scale < 1.0
    payload, mime = render_chunk(image, plan)
    assert mime == "image/jpeg"
    assert len(payload) > 0
    reopened = Image.open(__import__("io").BytesIO(payload))
    assert reopened.width == plan.crop_width
    assert reopened.height == plan.crop_height


def test_chunk_ink_ratio(settings):
    blank = Image.new("RGB", (400, 300), "white")
    assert chunk_ink_ratio(blank, 0, 300) < 0.01
    text = make_ecommerce_image(height=800)
    ratio = chunk_ink_ratio(text, 0, 800)
    assert ratio > 0.01


def test_extreme_long_image_segments_without_failure(settings):
    image = make_ecommerce_image(height=30000)
    plans = segment_image(image, settings)
    assert len(plans) >= 20
    assert plans[0].y0 == 0
    assert plans[-1].y1 == 30000
    assert all(plan.y1 > plan.y0 for plan in plans)
    assert all(
        plan.crop_width * plan.crop_height <= settings.chunk_max_pixels + 2 for plan in plans
    )


def test_long_image_thumbnail_is_height_capped(tmp_path):
    from app.imaging import save_thumbnail

    image = Image.new("RGB", (750, 30000), "white")
    path = tmp_path / "thumb.jpg"
    save_thumbnail(image, path)
    with Image.open(path) as thumb:
        assert thumb.width <= 560
        assert thumb.height <= 1400


def test_blank_bands_cover_whitespace():
    counts = np.array([5, 5, 0, 0, 0, 5, 5, 0], dtype=np.int32)
    bands = _find_blank_bands(counts, 1.0, 8, 100)
    assert (2, 5) in bands
    assert (7, 8) in bands
