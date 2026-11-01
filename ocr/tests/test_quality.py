from __future__ import annotations

from app.quality import assess_quality, compare_versions, text_similarity


def test_empty_with_ink_needs_review():
    report = assess_quality("", ink_ratio=0.08, forced_cut=False)
    assert report.needs_review
    assert "empty_with_ink" in report.flags
    assert report.score < 0.6


def test_clean_text_scores_high():
    text = "面料成分：92%莫代尔 8%氨纶\n尺码：M 170/90A"
    report = assess_quality(text, ink_ratio=0.03, forced_cut=False)
    assert report.score >= 0.9
    assert not report.needs_review


def test_numeric_inconsistency_flagged():
    report = assess_quality("面料成分：92%莫代尔 5%氨纶", ink_ratio=0.03, forced_cut=False)
    assert "numeric_inconsistency" in report.flags
    assert report.needs_review


def test_uncertain_marker_and_forced_cut():
    report = assess_quality("洗涤说明：⟦UNCERTAIN⟧", ink_ratio=0.02, forced_cut=True)
    assert "model_uncertain" in report.flags
    assert "forced_cut" in report.flags
    assert report.needs_review


def test_garbage_ratio():
    report = assess_quality("◆◆◆▚▚▚██◈◈◈◈", ink_ratio=0.02, forced_cut=False)
    assert "garbage_ratio" in report.flags


def test_similarity_and_conflicts_are_separate_metrics():
    primary = "面料成分：92%莫代尔 8%氨纶\n型号：SR-M2001"
    secondary = "面料成分：92%莫代尔 8%氨纶\n型号：SR-M2002"
    similarity, conflicts = compare_versions(primary, secondary, "PaddleOCR-VL", 1)
    assert 0.0 <= similarity <= 1.0
    kinds = {conflict.kind for conflict in conflicts}
    assert "numeric_mismatch" in kinds
    assert "percent_mismatch" not in kinds


def test_percent_mismatch_conflict():
    primary = "面料成分：92%莫代尔 8%氨纶"
    secondary = "面料成分：95%莫代尔 5%氨纶"
    _, conflicts = compare_versions(primary, secondary, "PaddleOCR-VL", 2)
    kinds = {conflict.kind for conflict in conflicts}
    assert "percent_mismatch" in kinds
    assert conflicts[0].severity in {"high", "warning"}


def test_text_similarity_identical():
    assert text_similarity("A B", "A  B") == 1.0
