from __future__ import annotations

from app.fields import (
    extract_key_fields,
    merge_key_fields,
    normalize_field_value,
    percent_issues,
)
from app.merge import (
    dedupe_overlap,
    merge_chunk_texts,
    strip_artifacts,
    to_markdown,
    to_plain_text,
)


def test_overlap_dedupe_removes_prefix():
    previous = "标题\n尺码表\nM 170/90A\nL 175/95A"
    current = "M 170/90A\nL 175/95A\n颜色：黑色"
    outcome = dedupe_overlap(previous, current, overlap_px=120)
    assert outcome.matched_lines == 2
    assert outcome.text == "颜色：黑色"
    assert outcome.removed_lines == ["M 170/90A", "L 175/95A"]


def test_overlap_dedupe_keeps_genuine_duplicate_without_overlap():
    previous = "温馨提示\n请以实物为准"
    current = "温馨提示\n请以实物为准\n价格：¥129"
    outcome = dedupe_overlap(previous, current, overlap_px=0)
    assert outcome.text == current
    assert outcome.matched_lines == 0


def test_merge_chunk_texts_and_audit():
    chunks = [
        ("标题\n尺码表\nM 170/90A\nL 175/95A", 0, 1000),
        ("M 170/90A\nL 175/95A\n颜色：黑色", 880, 1800),
    ]
    merged = merge_chunk_texts(chunks)
    assert "M 170/90A" in merged.text
    assert merged.text.count("M 170/90A") == 1
    assert "颜色：黑色" in merged.text
    assert merged.removed_line_count == 2
    assert merged.notes


def test_merge_skips_failed_empty_chunk():
    chunks = [
        ("第一部分", 0, 900),
        ("", 780, 1700),
        ("第二部分\n第一部分", 1600, 2400),
    ]
    merged = merge_chunk_texts(chunks)
    assert "第二部分" in merged.text
    assert merged.text.count("第一部分") == 2  # genuine repeat at a different position is kept


def test_strip_grounding_artifacts():
    raw = (
        "<|ref|>title<|/ref|><|det|>[[51, 18, 528, 42]]<|/det|>\n"
        "素然之境 SORAN\n"
        "<|ref|>text<|/ref|><|det|>[[51, 103, 565, 118]]<|/det|>\n"
        "商品名称：男士基础圆领短袖T恤"
    )
    cleaned = strip_artifacts(raw)
    assert "<|" not in cleaned
    assert "[[51" not in cleaned
    assert "素然之境 SORAN" in cleaned
    assert "商品名称" in cleaned


def test_markdown_to_plain_converts_table_and_markers():
    markdown = """# 素然之境

**面料成分**: 92%莫代尔 8%氨纶

| 尺码 | 身高/胸围 | 衣长 |
|---|---|---|
| M | 170/90A | 68cm |

<table><tr><td>S</td><td>165/85A</td></tr><tr><td>L</td><td>175/95A</td></tr></table>
"""
    plain = to_plain_text(markdown)
    assert "# 素然之境" not in plain
    assert "**" not in plain
    assert "|" not in plain
    assert "尺码\t身高/胸围\t衣长" in plain
    assert "S\t165/85A" in plain
    assert "面料成分: 92%莫代尔 8%氨纶" in plain


def test_to_markdown_preserves_existing_structure():
    text = "# 标题\n\n- 项目一\n- 项目二"
    assert to_markdown(text) == text


def test_extract_key_fields():
    text = """品牌：SORAN
商品名称：男士基础圆领短袖T恤
型号：SR-M2001
面料成分：92%莫代尔 8%氨纶
执行标准：FZ/T 73020-2019
安全类别：GB 18401-B
洗涤说明：手洗，不可漂白
价格：¥129.00
包装规格：1件/袋
尺码：M
尺码    身高/胸围
M       170/90A"""
    fields = extract_key_fields(text)
    names = {field.name for field in fields}
    assert {
        "brand",
        "product_name",
        "sku",
        "fabric_composition",
        "standard",
        "safety_category",
        "wash_instruction",
        "price",
        "packaging",
        "size",
        "size_chart",
    }.issubset(names)
    fabric = next(field for field in fields if field.name == "fabric_composition")
    assert "92%" in fabric.value and "8%" in fabric.value
    price = next(field for field in fields if field.name == "price")
    assert "129" in price.value


def test_percent_validation():
    assert percent_issues("面料成分：92%莫代尔 8%氨纶") == []
    issues = percent_issues("面料成分：92%莫代尔 5%氨纶")
    assert issues
    assert "97" in issues[0]


def test_merge_key_fields_aggregates_wash_and_normalizes_price():
    fields = extract_key_fields(
        "洗涤说明：手洗\n价格：¥129.00", chunk_index=0
    ) + extract_key_fields("悬挂晾干，避免暴晒\n价格：126", chunk_index=1)
    merged = merge_key_fields(fields)
    wash = [field for field in merged if field.name == "wash_instruction"]
    assert len(wash) == 1
    assert "手洗" in wash[0].value and "悬挂晾干" in wash[0].value
    price = [field for field in merged if field.name == "price"]
    assert len(price) == 2
    assert all(field.confidence == "conflict" for field in price)


def test_merge_key_fields_conflict():
    fields = extract_key_fields("品牌：SORAN", chunk_index=0) + extract_key_fields(
        "品牌：Soran Home", chunk_index=1
    )
    merged = merge_key_fields(fields)
    brand = [field for field in merged if field.name == "brand"]
    assert len(brand) == 2
    assert all(field.confidence == "conflict" for field in brand)
    assert normalize_field_value("SORAN") != normalize_field_value("Soran Home")
