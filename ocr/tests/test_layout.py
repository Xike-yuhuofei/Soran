from __future__ import annotations

from app.layout import (
    layout_text,
    order_parsed_blocks,
    parse_grounding_blocks,
    to_layout_blocks,
)

SAMPLE_GROUNDING = """<|ref|>title<|/ref|><|det|>[[40, 20, 300, 60]]<|/det|>
左栏标题

<|ref|>text<|/ref|><|det|>[[40, 90, 300, 120]]<|/det|>
左栏正文

<|ref|>title<|/ref|><|det|>[[400, 20, 700, 60]]<|/det|>
右栏标题

<|ref|>text<|/ref|><|det|>[[400, 90, 700, 120]]<|/det|>
右栏正文
"""


CAPTION_GRID_GROUNDING = """<|ref|>title<|/ref|><|det|>[[37, 168, 636, 228]]<|/det|>
挑个顺眼的色号。

<|ref|>image<|/ref|><|det|>[[48, 320, 501, 526]]<|/det|>


<|ref|>image_caption<|/ref|><|det|>[[228, 564, 320, 594]]<|/det|>
<center>燕麦</center>

<|ref|>image<|/ref|><|det|>[[505, 320, 950, 526]]<|/det|>


<|ref|>image_caption<|/ref|><|det|>[[684, 564, 777, 594]]<|/det|>
<center>咖啡</center>

<|ref|>image<|/ref|><|det|>[[48, 647, 501, 855]]<|/det|>


<|ref|>image_caption<|/ref|><|det|>[[228, 895, 320, 924]]<|/det|>
<center>烟灰</center>

<|ref|>image<|/ref|><|det|>[[505, 647, 950, 855]]<|/det|>


<|ref|>image_caption<|/ref|><|det|>[[684, 895, 777, 924]]<|/det|>
<center>灰绿</center>
"""


def test_caption_grid_reads_row_major():
    blocks = parse_grounding_blocks(CAPTION_GRID_GROUNDING)
    ordered = order_parsed_blocks(blocks, page_width=1000, page_height=1000)
    assert [block.text for block in ordered] == [
        "挑个顺眼的色号。",
        "燕麦",
        "咖啡",
        "烟灰",
        "灰绿",
    ]


def test_parse_grounding_blocks():
    blocks = parse_grounding_blocks(SAMPLE_GROUNDING)
    assert len(blocks) == 4
    assert blocks[0].label == "title"
    assert blocks[0].bbox == (40.0, 20.0, 300.0, 60.0)
    assert blocks[0].text == "左栏标题"
    assert blocks[2].text == "右栏标题"


def test_grounding_blocks_ordered_by_columns():
    blocks = parse_grounding_blocks(SAMPLE_GROUNDING)
    ordered = order_parsed_blocks(blocks, page_width=750, page_height=200)
    assert [block.text for block in ordered] == [
        "左栏标题",
        "左栏正文",
        "右栏标题",
        "右栏正文",
    ]


def test_layout_blocks_map_to_original_coordinates():
    blocks = parse_grounding_blocks(SAMPLE_GROUNDING)
    ordered = order_parsed_blocks(blocks, page_width=750, page_height=200)
    mapped = to_layout_blocks(
        ordered,
        image_width=750,
        image_height=2000,
        y_offset=1000,
        scale=0.5,
    )
    assert mapped[0].bbox == [80.0, 1040.0, 600.0, 1120.0]
    assert mapped[0].text == "左栏标题"


def test_layout_text_joins_blocks():
    blocks = parse_grounding_blocks(SAMPLE_GROUNDING)
    ordered = order_parsed_blocks(blocks, page_width=750, page_height=200)
    assert layout_text(ordered).splitlines() == [
        "左栏标题",
        "左栏正文",
        "右栏标题",
        "右栏正文",
    ]


def test_no_grounding_returns_empty():
    assert parse_grounding_blocks("普通 OCR 文本") == []
