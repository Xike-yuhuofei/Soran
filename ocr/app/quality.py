from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from .fields import numeric_tokens, percent_issues, percent_tokens
from .merge import normalize_for_compare, strip_artifacts, to_plain_text
from .schemas import ChunkResult, TextConflict

UNCERTAIN_MARKERS = ("⟦UNCERTAIN⟧", "[不确定]", "【不确定】", "无法识别", "无法辨认")
_COMMON_CHAR_RE = re.compile(
    r"[\u4e00-\u9fff\u3400-\u4dbfA-Za-z0-9"
    r"\u3000-\u303f\uff00-\uffef"
    r".,:;!?%‰¥￥()（）【】\[\]{}<>《》\"'`~^*_+=/\\|@#&$\s-]"
)


@dataclass
class QualityReport:
    score: float
    needs_review: bool
    flags: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, float | int | str] = field(default_factory=dict)


def _repeated_line_ratio(text: str) -> float:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 3:
        return 0.0
    counts: dict[str, int] = {}
    for line in lines:
        if len(line) <= 1:
            continue
        counts[line] = counts.get(line, 0) + 1
    repeated = sum(count for count in counts.values() if count >= 3)
    return repeated / len(lines) if lines else 0.0


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)).casefold()


def find_missing_lines(
    primary: str, secondary: str, min_compact_chars: int = 6, limit: int = 6
) -> list[str]:
    """Return non-trivial secondary lines absent from the primary text."""

    primary_compact = _compact(to_plain_text(primary))
    missing: list[str] = []
    for line in to_plain_text(secondary).splitlines():
        stripped = line.strip()
        compact = _compact(stripped)
        if len(compact) < min_compact_chars:
            continue
        if compact not in primary_compact:
            missing.append(stripped)
            if len(missing) >= limit:
                break
    return missing


def find_primary_only_lines(
    primary: str, secondary: str, min_compact_chars: int = 8, limit: int = 6
) -> list[str]:
    secondary_compact = _compact(to_plain_text(secondary))
    only: list[str] = []
    for line in to_plain_text(primary).splitlines():
        stripped = line.strip()
        compact = _compact(stripped)
        if len(compact) < min_compact_chars:
            continue
        if compact not in secondary_compact:
            only.append(stripped)
            if len(only) >= limit:
                break
    return only


_HTML_TABLE_RE = re.compile(r"<table[^>]*>(.*?)</table>", re.IGNORECASE | re.DOTALL)
_HTML_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_HTML_CELL_RE = re.compile(r"<(?:td|th)[^>]*>", re.IGNORECASE)
_MD_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?[-=]{3,}")


def table_issues(text: str) -> list[str]:
    issues: list[str] = []
    for table in _HTML_TABLE_RE.findall(text):
        counts = [len(_HTML_CELL_RE.findall(row)) for row in _HTML_ROW_RE.findall(table)]
        counts = [count for count in counts if count > 0]
        if counts and min(counts) != max(counts):
            issues.append(f"HTML 表格行列数不一致：{counts}")
    rows: list[int] = []

    def flush() -> None:
        nonlocal rows
        if rows and min(rows) != max(rows):
            issues.append(f"Markdown 表格列数不一致：{rows}")
        rows = []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.count("|") >= 2:
            if _MD_SEPARATOR_RE.match(stripped):
                continue
            rows.append(len([cell for cell in stripped.strip("|").split("|")]))
        else:
            flush()
    flush()
    return issues


def assess_quality(
    text: str,
    ink_ratio: float,
    forced_cut: bool,
    risk_flags: list[str] | None = None,
) -> QualityReport:
    """Heuristic quality score. This is intentionally separate from model
    confidence (if supplied) and from multi-model consistency.
    """

    text = strip_artifacts(text)
    risk_flags = risk_flags or []
    chars = len(re.sub(r"\s+", "", text))
    flags: list[str] = []
    reasons: list[str] = []
    score = 1.0
    uncommon = 0

    def add(flag: str, reason: str, penalty: float) -> None:
        nonlocal score
        if flag not in flags:
            flags.append(flag)
            reasons.append(reason)
            score -= penalty

    if chars == 0 and ink_ratio > 0.01:
        add("empty_with_ink", "检测到文字/图形墨迹但模型未输出任何文字", 0.55)
    elif ink_ratio > 0.03 and chars < 8:
        add("very_short_for_ink", "墨迹密度较高但输出文字过少，可能漏识别", 0.35)
    elif ink_ratio > 0.06 and chars < 25:
        add("short_for_ink", "文字量与画面墨迹密度不匹配", 0.20)

    if chars >= 10:
        uncommon = sum(1 for char in text if not _COMMON_CHAR_RE.match(char))
        uncommon_ratio = uncommon / max(1, chars)
        if uncommon_ratio > 0.35:
            add("garbage_ratio", f"非常见字符占比 {uncommon_ratio:.0%}，疑似背景图案被识别", 0.30)

    repeat_ratio = _repeated_line_ratio(text)
    if repeat_ratio > 0.5:
        add("repeated_noise", f"重复行占比 {repeat_ratio:.0%}", 0.20)

    if any(marker in text for marker in UNCERTAIN_MARKERS):
        add("model_uncertain", "模型标记了无法辨认字符", 0.25)

    issues = percent_issues(text)
    if issues:
        add("numeric_inconsistency", "；".join(issues[:3]), 0.25)

    layout_issues = table_issues(text)
    if layout_issues:
        add("table_structure", "；".join(layout_issues[:3]), 0.20)

    if forced_cut:
        add("forced_cut", "该分块因缺少空白行而强制切分，边界可能受影响", 0.25)
    if "narrow_blank_boundary" in risk_flags:
        add("narrow_boundary", "分块边界空白带较窄", 0.05)

    score = max(0.0, min(1.0, score))
    high_flags = {
        "empty_with_ink",
        "very_short_for_ink",
        "garbage_ratio",
        "numeric_inconsistency",
        "model_uncertain",
        "forced_cut",
        "table_structure",
    }
    needs_review = bool(high_flags.intersection(flags)) or score < 0.60
    return QualityReport(
        score=round(score, 3),
        needs_review=needs_review,
        flags=flags,
        reasons=reasons,
        metrics={
            "chars": chars,
            "ink_ratio": round(ink_ratio, 4),
            "uncommon_ratio": round(uncommon / max(1, chars), 4) if chars else 0.0,
            "repeated_line_ratio": round(repeat_ratio, 4),
        },
    )


def text_similarity(primary: str, secondary: str) -> float:
    left = normalize_for_compare(to_plain_text(primary))
    right = normalize_for_compare(to_plain_text(secondary))
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right, autojunk=False).ratio()


def compare_versions(
    primary: str,
    secondary: str,
    secondary_engine: str,
    chunk_index: int,
) -> tuple[float, list[TextConflict]]:
    """Compare primary and review output without choosing the "nicer" text."""

    conflicts: list[TextConflict] = []
    similarity = text_similarity(primary, secondary)
    if similarity < 0.88:
        conflicts.append(
            TextConflict(
                kind="text_divergence",
                detail=f"主模型与复核模型文本相似度 {similarity:.2f}（分块 {chunk_index}）",
                primary=primary[:1500],
                secondary=secondary[:1500],
                severity="high" if similarity < 0.65 else "warning",
            )
        )

    primary_percent = percent_tokens(primary)
    secondary_percent = percent_tokens(secondary)
    if primary_percent != secondary_percent:
        conflicts.append(
            TextConflict(
                kind="percent_mismatch",
                detail=(
                    f"百分比不一致：主模型 {sorted(primary_percent) or '无'}；"
                    f"{secondary_engine} {sorted(secondary_percent) or '无'}"
                ),
                primary=primary[:500],
                secondary=secondary[:500],
                severity="high",
            )
        )

    primary_numbers = numeric_tokens(primary)
    secondary_numbers = numeric_tokens(secondary)
    if primary_numbers != secondary_numbers:
        only_primary = sorted(primary_numbers - secondary_numbers)[:8]
        only_secondary = sorted(secondary_numbers - primary_numbers)[:8]
        if only_primary or only_secondary:
            conflicts.append(
                TextConflict(
                    kind="numeric_mismatch",
                    detail=(
                        f"数字不一致：仅主模型 {only_primary or '无'}；"
                        f"仅{secondary_engine} {only_secondary or '无'}"
                    ),
                    primary=primary[:500],
                    secondary=secondary[:500],
                    severity="high",
                )
            )

    missing = find_missing_lines(primary, secondary)
    if missing:
        conflicts.append(
            TextConflict(
                kind="possible_missing_text",
                detail=f"{secondary_engine} 发现主模型可能缺失 {len(missing)} 行",
                primary=primary[:800],
                secondary="\n".join(missing),
                severity="warning",
            )
        )
    if similarity < 0.95:
        primary_only = find_primary_only_lines(primary, secondary)
        if primary_only:
            conflicts.append(
                TextConflict(
                    kind="primary_only_text",
                    detail=(
                        f"主模型有 {len(primary_only)} 行未在{secondary_engine}中出现，"
                        "可能是主模型多识别或复核漏识别"
                    ),
                    primary="\n".join(primary_only),
                    secondary=secondary[:800],
                    severity="warning",
                )
            )
    return similarity, conflicts


def apply_review(
    chunk: ChunkResult,
    review_text: str,
    review_engine: str,
    similarity: float,
    conflicts: list[TextConflict],
) -> None:
    chunk.reviewed = True
    chunk.review_text = review_text
    chunk.review_engine = review_engine
    chunk.consistency_score = round(similarity, 4)
    chunk.conflicts.extend(conflicts)
    if conflicts:
        chunk.needs_review = True
        chunk.uncertain = True


def quality_flags_to_text(report: QualityReport) -> str:
    return "；".join(report.reasons)
