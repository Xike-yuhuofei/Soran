from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

GROUNDING_PREFIX_RE = re.compile(
    r"<\|ref\|>.*?<\|/ref\|><\|det\|>.*?<\|/det\|>\s*", re.IGNORECASE | re.DOTALL
)
DET_BLOCK_RE = re.compile(r"<\|det\|>.*?<\|/det\|>\s*", re.IGNORECASE | re.DOTALL)
ARTIFACT_PATTERNS = [
    r"<image>",
    r"<\|/?(?:ref|det|grounding|/grounding)\|>",
    r"<\|endoftext\|>",
]
_ARTIFACT_RE = re.compile("|".join(ARTIFACT_PATTERNS), re.IGNORECASE)
_MULTISPACE_RE = re.compile(r"[ \t\u00a0\u3000]+")
_ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff]")
_HTML_TABLE_RE = re.compile(r"<table[^>]*>(.*?)</table>", re.IGNORECASE | re.DOTALL)
_HTML_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_HTML_CELL_RE = re.compile(r"<(?:td|th)[^>]*>(.*?)</(?:td|th)>", re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MD_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?[-=]{3,}")
_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+", re.MULTILINE)
_MD_EMPHASIS_RE = re.compile(r"(?<!\*)\*\*([^*\n]+)\*\*(?!\*)|__([^_\n]+)__")
_MD_HR_RE = re.compile(r"^\s*(?:---|\*\*\*|___)\s*$", re.MULTILINE)


def strip_artifacts(text: str) -> str:
    text = GROUNDING_PREFIX_RE.sub("", text)
    text = DET_BLOCK_RE.sub("", text)
    text = _ARTIFACT_RE.sub("", text)
    text = _ZERO_WIDTH_RE.sub("", text)
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _html_tables_to_tsv(text: str) -> str:
    def render_table(match: re.Match[str]) -> str:
        rows = []
        for row in _HTML_ROW_RE.findall(match.group(1)):
            cells = [
                html.unescape(_HTML_TAG_RE.sub("", cell)).strip()
                for cell in _HTML_CELL_RE.findall(row)
            ]
            if cells:
                rows.append("\t".join(cells))
        return "\n".join(rows)

    return _HTML_TABLE_RE.sub(render_table, text)


def to_plain_text(text: str) -> str:
    """Convert model Markdown/grounding output to plain text for TXT export.

    Formatting markers are removed, while the recognized characters and line
    order are preserved. HTML tables become tab-separated rows.
    """

    text = strip_artifacts(text)
    text = _html_tables_to_tsv(text)
    text = _MD_HR_RE.sub("", text)
    lines: list[str] = []
    for line in text.splitlines():
        if _MD_TABLE_SEPARATOR_RE.match(line):
            continue
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 3:
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            lines.append("\t".join(cells))
            continue
        stripped = _MD_HEADING_RE.sub("", stripped)
        stripped = _MD_EMPHASIS_RE.sub(lambda m: m.group(1) or m.group(2) or "", stripped)
        stripped = _HTML_TAG_RE.sub("", stripped)
        lines.append(html.unescape(stripped).rstrip())
    plain = "\n".join(lines)
    plain = re.sub(r"\n{3,}", "\n\n", plain)
    return plain.strip()


def normalize_for_compare(line: str) -> str:
    line = unicodedata.normalize("NFKC", line)
    line = _MULTISPACE_RE.sub(" ", line).strip().casefold()
    return line


def _line_similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if len(a) < 2 or len(b) < 2:
        return 0.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


@dataclass
class DedupeOutcome:
    text: str
    removed_lines: list[str] = field(default_factory=list)
    matched_lines: int = 0
    score: float = 0.0
    note: str | None = None


def _character_overlap(previous: str, current: str, overlap_px: int) -> tuple[str, str, int] | None:
    """Fallback for blocks where multiple original lines were concatenated.

    Line-level matching can miss an overlap such as
    ``颜色...\n包装规格...`` vs ``颜色...包装规格...``. This compares
    whitespace-stripped suffix/prefix and removes the duplicated prefix from
    the current chunk, bounded by the physical overlap height.
    """

    prev_norm = re.sub(r"\s+", "", previous)
    curr_norm = re.sub(r"\s+", "", current)
    max_chars = max(24, min(200, overlap_px))
    upper = min(len(prev_norm), len(curr_norm), max_chars)
    for size in range(upper, 11, -1):
        if prev_norm[-size:] != curr_norm[:size]:
            continue
        consumed = 0
        cut = 0
        while cut < len(current) and consumed < size:
            if not current[cut].isspace():
                consumed += 1
            cut += 1
        removed = current[:cut].strip()
        remaining = current[cut:].lstrip()
        if remaining or removed:
            return remaining, removed, size
    return None


def dedupe_overlap(
    previous: str,
    current: str,
    overlap_px: int,
    max_lines: int = 12,
    threshold: float = 0.86,
) -> DedupeOutcome:
    """Remove duplicated OCR text caused by physical chunk overlap.

    Only the suffix/prefix of adjacent chunks is considered. Matches are
    bounded by how many text lines can physically fit in the overlap. Removed
    lines are returned for auditability, so false-positive removals are
    traceable rather than silently lost.
    """

    if overlap_px <= 0 or not previous.strip() or not current.strip():
        return DedupeOutcome(text=current)

    prev_lines = previous.splitlines()
    curr_lines = current.splitlines()
    prev_nonempty = [line for line in prev_lines if line.strip()]
    curr_nonempty_idx = [i for i, line in enumerate(curr_lines) if line.strip()]
    if not prev_nonempty or not curr_nonempty_idx:
        return DedupeOutcome(text=current)

    physical_limit = max(1, min(max_lines, int(overlap_px / 30) + 1))
    upper = min(
        physical_limit,
        len(prev_nonempty),
        len(curr_nonempty_idx),
    )
    best_k = 0
    best_score = 0.0
    for k in range(1, upper + 1):
        prev_tail = [normalize_for_compare(line) for line in prev_nonempty[-k:]]
        curr_head = [normalize_for_compare(curr_lines[i]) for i in curr_nonempty_idx[:k]]
        if not any(prev_tail) or not any(curr_head):
            continue
        scores = [_line_similarity(a, b) for a, b in zip(prev_tail, curr_head, strict=False)]
        avg = sum(scores) / len(scores)
        block_chars = sum(len(line) for line in curr_head)
        if avg >= threshold and block_chars >= 4:
            best_k = k
            best_score = avg

    if best_k == 0:
        char_match = _character_overlap(previous, current, overlap_px)
        if char_match:
            remaining, removed, size = char_match
            return DedupeOutcome(
                text=remaining,
                removed_lines=[removed],
                matched_lines=1,
                score=1.0,
                note=f"character_overlap:{size}",
            )
        return DedupeOutcome(text=current)

    cutoff_index = curr_nonempty_idx[best_k - 1]
    remaining = curr_lines[cutoff_index + 1 :]
    while remaining and not remaining[0].strip():
        remaining.pop(0)
    removed = [curr_lines[i] for i in curr_nonempty_idx[:best_k]]
    note = None
    if best_score < 1.0:
        note = f"fuzzy_overlap_match:{best_score:.2f}"
    return DedupeOutcome(
        text="\n".join(remaining).strip(),
        removed_lines=removed,
        matched_lines=best_k,
        score=best_score,
        note=note,
    )


@dataclass
class MergeOutcome:
    text: str
    removed_line_count: int = 0
    removed_lines: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def merge_chunk_texts(
    chunks: list[tuple[str, int, int]],
) -> MergeOutcome:
    """Merge chunks in reading order.

    ``chunks`` is a list of ``(text, y0, y1)`` in top-to-bottom order. When a
    middle chunk failed and produced no text, overlap is measured against the
    last non-empty chunk so duplicates are still removed.
    """

    output_parts: list[str] = []
    removed: list[str] = []
    notes: list[str] = []
    last_written: tuple[str, int, int] | None = None

    for raw_text, y0, y1 in chunks:
        text = strip_artifacts(raw_text)
        if not text:
            continue
        if last_written is not None:
            last_text, _, last_y1 = last_written
            overlap_px = last_y1 - y0
            outcome = dedupe_overlap(last_text, text, overlap_px)
            if outcome.matched_lines:
                removed.extend(outcome.removed_lines)
                notes.append(
                    f"chunks {y0}-{y1}: removed {outcome.matched_lines} overlap line(s)"
                    + (f" ({outcome.note})" if outcome.note else "")
                )
            text = outcome.text
            if not text:
                continue
        output_parts.append(text)
        last_written = (text, y0, y1)

    merged = "\n\n".join(part.strip() for part in output_parts if part.strip()).strip()
    merged = re.sub(r"\n{3,}", "\n\n", merged)
    return MergeOutcome(
        text=merged,
        removed_line_count=len(removed),
        removed_lines=removed,
        notes=notes,
    )


_MARKDOWN_HINT_RE = re.compile(r"(^#{1,6} )|(^\|)|(^- )|(^\d+\. )", re.MULTILINE)


def to_markdown(text: str, already_markdown: bool = False) -> str:
    """Preserve structure without inventing content.

    Markdown-mode model output is passed through. Plain-text mode is rendered
    as paragraphs: existing line breaks and list markers are kept, and blank
    lines delimit paragraphs. No headings or tables are fabricated.
    """

    text = strip_artifacts(text)
    if not text:
        return ""
    if already_markdown or _MARKDOWN_HINT_RE.search(text):
        return text

    paragraphs: list[str] = []
    block: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            if block:
                paragraphs.append("\n".join(block).strip())
                block = []
            continue
        block.append(line.rstrip())
    if block:
        paragraphs.append("\n".join(block).strip())
    return "\n\n".join(paragraphs)


def build_document_markdown(
    documents: list[tuple[str, str]],
    already_markdown: bool = False,
) -> str:
    """Combine per-image text. Headings are added only for multi-image input."""

    if len(documents) == 1:
        return to_markdown(documents[0][1], already_markdown)
    sections = []
    for index, (filename, text) in enumerate(documents, start=1):
        body = to_markdown(text, already_markdown)
        sections.append(f"## 图片 {index} · {filename}\n\n{body}".strip())
    return "\n\n".join(sections).strip()
