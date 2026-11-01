from __future__ import annotations

from app.fusion import (
    decide_layout_fusion,
    looks_like_table,
    needs_layout_fusion,
    table_row_count,
)
from app.layout import ParsedLayoutBlock


def _caption(label: str, bbox: tuple[float, float, float, float], text: str) -> ParsedLayoutBlock:
    return ParsedLayoutBlock(label=label, bbox=bbox, text=text)


def test_needs_layout_fusion_for_malformed_table():
    assert needs_layout_fusion("尺寸\t腰围\t臀围\t体重\nM\t64\t85\t80", []) == "table_like"


def test_needs_layout_fusion_for_short_caption_lines():
    text = "挑个顺眼的色号。\n燕麦\n烟灰\n咖啡\n灰绿"
    assert needs_layout_fusion(text, ["short_for_ink"]) == "short_caption_like"


def test_needs_layout_fusion_ignores_normal_paragraph():
    assert needs_layout_fusion("洗涤后请平铺晾干，避免变形。", []) is None


def test_table_row_count_reads_tsv_and_html():
    assert table_row_count("尺寸\t腰围\nM\t64") == 2
    html = "<table><tr><td>尺寸</td><td>腰围</td></tr><tr><td>M</td><td>64</td></tr></table>"
    assert table_row_count(html) == 2
    assert looks_like_table("尺寸\t腰围\nM\t64") is True


def test_decide_prefers_consistent_secondary_table_when_primary_is_malformed():
    primary = "尺寸\t腰围\t臀围\t体重\nM\t64\t85\t80\nL\t70\t90\t100\t120"
    secondary = (
        "<table><tr><td>尺寸</td><td>腰围</td><td>臀围</td><td>体重</td></tr>"
        "<tr><td>M</td><td>64</td><td>85</td><td>80</td></tr>"
        "<tr><td>L</td><td>70</td><td>90</td><td>100</td></tr></table>"
    )
    decision = decide_layout_fusion(
        primary_text=primary,
        secondary_text=secondary,
        secondary_blocks=[],
        page_width=1000,
    )
    assert decision.use_secondary is True
    assert decision.reason == "secondary_table_consistent"


def test_decide_keeps_primary_when_secondary_table_drops_rows():
    primary = "尺寸\t腰围\nM\t64\nL\t70\nXL\t76"
    secondary = "<table><tr><td>尺寸</td><td>腰围</td></tr><tr><td>M</td><td>64</td></tr></table>"
    decision = decide_layout_fusion(
        primary_text=primary,
        secondary_text=secondary,
        secondary_blocks=[],
        page_width=1000,
    )
    assert decision.use_secondary is False
    assert decision.reason == "secondary_missing_table_rows"


def test_decide_keeps_primary_when_secondary_is_much_shorter():
    primary = "面料成分\n面料：95%棉 5%氨纶\n里料：100%棉\n洗护说明\n不要用尖硬物摩擦"
    secondary = "<table><tr><td>面料</td><td>95%棉</td></tr></table>"
    decision = decide_layout_fusion(
        primary_text=primary,
        secondary_text=secondary,
        secondary_blocks=[],
        page_width=1000,
    )
    assert decision.use_secondary is False
    assert decision.reason == "secondary_too_short"


def test_decide_prefers_row_major_caption_grid():
    blocks = [
        _caption("title", (30.0, 40.0, 500.0, 90.0), "挑个顺眼的色号。"),
        _caption("image_caption", (200.0, 300.0, 300.0, 330.0), "燕麦"),
        _caption("image_caption", (650.0, 300.0, 750.0, 330.0), "咖啡"),
        _caption("image_caption", (200.0, 600.0, 300.0, 630.0), "烟灰"),
        _caption("image_caption", (650.0, 600.0, 750.0, 630.0), "灰绿"),
    ]
    primary = "挑个顺眼的色号。\n燕麦\n烟灰\n咖啡\n灰绿"
    secondary = "挑个顺眼的色号。\n燕麦\n咖啡\n烟灰\n灰绿"
    decision = decide_layout_fusion(
        primary_text=primary,
        secondary_text=secondary,
        secondary_blocks=blocks,
        page_width=1000,
    )
    assert decision.use_secondary is True
    assert decision.reason == "secondary_caption_grid_row_major"
