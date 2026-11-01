from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .layout import ParsedLayoutBlock, caption_grid_blocks
from .merge import to_plain_text
from .quality import find_primary_only_lines, table_issues

_TABLE_CELL_RE = re.compile(r"\t|[ \u3000]{2,}")


def looks_like_table(text: str) -> bool:
    for line in text.splitlines():
        if line.count("|") >= 2 or "\t" in line:
            return True
        columns = re.split(r"\s{3,}", line.strip())
        if len(columns) >= 3 and sum(len(part) <= 20 for part in columns) >= 3:
            return True
    return False


def _compact_length(text: str) -> int:
    return len(re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)))


def _short_lines(text: str, max_chars: int = 8) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 4:
        return []
    if any(_compact_length(line) > max_chars for line in lines):
        return []
    return lines


def _short_line_count(text: str, max_chars: int = 8) -> int:
    return len(
        [line for line in text.splitlines() if line.strip() and _compact_length(line) <= max_chars]
    )


def table_row_count(text: str) -> int:
    """Count plain-text rows that carry at least two table-like cells."""

    count = 0
    for line in to_plain_text(text).splitlines():
        cells = [cell for cell in _TABLE_CELL_RE.split(line.strip()) if cell.strip()]
        if len(cells) >= 2:
            count += 1
    return count


def needs_layout_fusion(text: str, flags: list[str]) -> str | None:
    """Return a fusion reason only for chunks that may need spatial structure."""

    plain = to_plain_text(text)
    if looks_like_table(plain) or "table_structure" in flags or "table_header_conflict" in flags:
        return "table_like"
    if ("short_for_ink" in flags or "very_short_for_ink" in flags) and _short_lines(plain):
        return "short_caption_like"
    return None


@dataclass(frozen=True)
class LayoutDecision:
    use_secondary: bool
    reason: str


def decide_layout_fusion(
    *,
    primary_text: str,
    secondary_text: str,
    secondary_blocks: list[ParsedLayoutBlock],
    page_width: int,
    primary_flags: list[str] | None = None,
) -> LayoutDecision:
    """Choose the grounding-layout result only for verifiable structure gains.

    This never selects the "more fluent" text. It only switches when the
    secondary result has an internally consistent table, preserves row counts,
    or restores row-major order for a detected caption grid.
    """

    primary_flags = primary_flags or []
    primary_plain = to_plain_text(primary_text)
    secondary_plain = to_plain_text(secondary_text)
    if not secondary_plain.strip():
        return LayoutDecision(False, "secondary_empty")

    secondary_table = looks_like_table(secondary_plain)
    primary_table = looks_like_table(primary_plain)
    secondary_rows = table_row_count(secondary_plain)
    primary_rows = table_row_count(primary_plain)

    if secondary_table:
        if secondary_rows and primary_rows and secondary_rows < max(2, primary_rows - 1):
            return LayoutDecision(False, "secondary_missing_table_rows")
        if _compact_length(secondary_plain) < 0.6 * max(1, _compact_length(primary_plain)):
            return LayoutDecision(False, "secondary_too_short")
        secondary_issues = table_issues(secondary_text)
        primary_issues = table_issues(primary_text)
        if not secondary_issues and (
            primary_table or primary_issues or "table_structure" in primary_flags
        ):
            structural_defect = primary_issues or any(
                flag in primary_flags for flag in ("table_structure", "table_header_conflict")
            )
            if not structural_defect:
                dropped = find_primary_only_lines(
                    primary_text, secondary_text, min_compact_chars=4, limit=6
                )
                if dropped:
                    return LayoutDecision(False, "secondary_drops_primary_lines")
            return LayoutDecision(True, "secondary_table_consistent")

    grid = caption_grid_blocks(secondary_blocks, page_width)
    if grid and len(grid) >= 4 and _short_line_count(primary_plain) >= 4 and not primary_table:
        return LayoutDecision(True, "secondary_caption_grid_row_major")

    if secondary_table and not primary_table and not table_issues(secondary_text):
        return LayoutDecision(True, "secondary_table_recovered")
    return LayoutDecision(False, "primary_preferred")
