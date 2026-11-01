from __future__ import annotations

from PIL import Image

from app.local_ocr import LocalLine, LocalPaddleOCR, _parse_paddle_result, order_lines_xy_cut


def test_parse_paddle_v3_dict():
    raw = {
        "rec_texts": ["标题", "左栏", "右栏"],
        "rec_boxes": [[10, 10, 100, 40], [10, 100, 200, 140], [300, 100, 500, 140]],
        "rec_scores": [0.99, 0.95, 0.93],
    }
    lines = _parse_paddle_result(raw)
    assert len(lines) == 3
    assert lines[0].text == "标题"
    assert lines[0].score == 0.99


def test_parse_paddle_legacy_list():
    raw = [
        [
            [[[10, 10], [100, 10], [100, 40], [10, 40]], ("左栏", 0.9)],
            [[[300, 100], [500, 100], [500, 140], [300, 140]], ("右栏", 0.8)],
        ]
    ]
    lines = _parse_paddle_result(raw)
    assert [line.text for line in lines] == ["左栏", "右栏"]


def test_xy_cut_orders_columns_left_to_right():
    lines = [
        LocalLine("右栏一", (320, 10, 500, 40)),
        LocalLine("左栏一", (10, 10, 200, 40)),
        LocalLine("右栏二", (320, 80, 500, 110)),
        LocalLine("左栏二", (10, 80, 200, 110)),
    ]
    ordered = order_lines_xy_cut(lines, page_width=520, page_height=150)
    assert [line.text for line in ordered] == ["左栏一", "左栏二", "右栏一", "右栏二"]


def test_xy_cut_orders_rows_top_to_bottom():
    lines = [
        LocalLine("第二行", (10, 80, 200, 110)),
        LocalLine("第一行", (10, 10, 200, 40)),
    ]
    ordered = order_lines_xy_cut(lines, page_width=400, page_height=150)
    assert [line.text for line in ordered] == ["第一行", "第二行"]


def test_local_disabled_by_default(settings):
    local = LocalPaddleOCR(settings)
    assert local.available() is False
    result = local.run(Image.new("RGB", (100, 100), "white"))
    assert result.error


def test_local_model_falls_back_when_v6_unsupported(settings, monkeypatch):
    import sys
    import types

    calls = []

    class FakePaddleOCR:
        def __init__(self, **kwargs):
            calls.append(kwargs)
            if kwargs.get("ocr_version") == "PP-OCRv6":
                raise ValueError("PP-OCRv6 is not supported by this build")

    module = types.ModuleType("paddleocr")
    module.PaddleOCR = FakePaddleOCR
    monkeypatch.setitem(sys.modules, "paddleocr", module)
    settings.local_ocr_enabled = True
    settings.local_ocr_model = "PP-OCRv6"

    local = LocalPaddleOCR(settings)
    assert local.available() is True
    status = local.status()
    assert status["actual_model"] == "PP-OCRv5"
    assert status["model"] == "PP-OCRv6"
    assert status["error"]
