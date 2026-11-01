from __future__ import annotations

from app.metrics import (
    boundary_miss_rate,
    character_error_rate,
    duplicate_line_rate,
    introduced_duplicate_rate,
    key_field_accuracy,
    levenshtein_distance,
    line_recall,
    summarize,
)
from app.schemas import KeyField


def test_levenshtein_and_cer():
    assert levenshtein_distance("abc", "abd") == 1
    assert character_error_rate("面料成分 92%", "面料成分92%") == 0.0
    assert character_error_rate("ABC", "ABD") > 0


def test_line_recall():
    reference = "品牌：SORAN\n面料成分：92%莫代尔 8%氨纶"
    assert line_recall(reference, "乱序\n品牌：SORAN\n面料成分：92%莫代尔 8%氨纶") == 1.0
    assert line_recall(reference, "品牌：SORAN") == 0.5


def test_duplicate_rates():
    assert duplicate_line_rate("A\nA\nB") > 0
    assert introduced_duplicate_rate("A\nB", "A\nB") == 0.0
    assert introduced_duplicate_rate("A\nB", "A\nB\nA") > 0


def test_key_field_accuracy():
    expected = {"brand": "SORAN", "fabric_composition": "92%莫代尔 8%氨纶"}
    fields = [
        KeyField(name="brand", value="SORAN"),
        KeyField(name="fabric_composition", value="92%莫代尔 8%氨纶"),
    ]
    accuracy, details = key_field_accuracy(expected, fields)
    assert accuracy == 1.0
    assert details["correct"] == 2

    fields[1] = KeyField(name="fabric_composition", value="92%莫代尔 5%氨纶")
    accuracy, _ = key_field_accuracy(expected, fields)
    assert accuracy == 0.5


def test_boundary_miss_rate():
    assert boundary_miss_rate([], "text") is None
    assert boundary_miss_rate(["分隔线前", "分隔线后"], "分隔线前\n分隔线后") == 0.0
    assert boundary_miss_rate(["缺失"], "其他") == 1.0


def test_summarize_p95():
    summary = summarize([1, 2, 3, 4, 5])
    assert summary["count"] == 5
    assert summary["p50"] == 3
    assert summary["max"] == 5
    assert summarize([])["count"] == 0
