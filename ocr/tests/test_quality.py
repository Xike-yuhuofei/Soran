from __future__ import annotations

from app.quality import (
    assess_quality,
    boundary_potential_miss,
    compare_versions,
    find_missing_lines,
    find_primary_only_lines,
    table_issues,
    text_similarity,
)


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


def test_missing_line_detection_and_formatting_tolerance():
    primary = "# 标题\n**品牌**: SORAN\n型号：SR-M2001"
    review = "标题\n品牌: SORAN\n型号：SR-M2001\n面料成分：92%莫代尔 8%氨纶"
    missing = find_missing_lines(primary, review)
    assert missing == ["面料成分：92%莫代尔 8%氨纶"]
    _, conflicts = compare_versions(primary, review, "PaddleOCR-VL", 1)
    assert any(conflict.kind == "possible_missing_text" for conflict in conflicts)

    primary_only = find_primary_only_lines("标题\n独有内容仅此一处\n品牌", "标题\n品牌")
    assert primary_only == ["独有内容仅此一处"]


def test_boundary_potential_miss():
    assert (
        boundary_potential_miss(
            "第一行文字\n共享重叠行",
            "共享重叠行\n第二段文字",
            overlap_px=120,
            overlap_ink_ratio=0.05,
        )
        is None
    )
    assert boundary_potential_miss(
        "第一行文字\n第二行文字", "完全不同内容\n另一段文字", overlap_px=120, overlap_ink_ratio=0.05
    )
    assert (
        boundary_potential_miss("第一行文字", "另一段文字", overlap_px=120, overlap_ink_ratio=0.0)
        is None
    )
    assert boundary_potential_miss("", "另一段文字", overlap_px=120, overlap_ink_ratio=0.05)


def test_table_structure_issues():
    markdown = "| 尺码 | 身高 | 衣长 |\n|---|---|---|\n| M | 170/90A | 68cm |\n| L | 175/95A |"
    issues = table_issues(markdown)
    assert issues and "Markdown" in issues[0]

    html = (
        "<table><tr><td>M</td><td>170</td><td>68</td></tr><tr><td>L</td><td>175</td></tr></table>"
    )
    issues = table_issues(html)
    assert issues and "HTML" in issues[0]

    report = assess_quality(markdown, ink_ratio=0.02, forced_cut=False)
    assert "table_structure" in report.flags
    assert report.needs_review
