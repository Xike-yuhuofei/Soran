from __future__ import annotations

import re
from dataclasses import dataclass

from .local_ocr import LocalLine, order_lines_xy_cut
from .merge import strip_artifacts
from .schemas import LayoutBlock

GROUNDING_BLOCK_RE = re.compile(
    r"<\|ref\|>(?P<label>[^<]*?)<\|/ref\|>"
    r"<\|det\|>\[\[\s*(?P<x0>\d+)\s*,\s*(?P<y0>\d+)\s*,\s*(?P<x1>\d+)\s*,\s*(?P<y1>\d+)\s*\]\]"
    r"<\|/det\|>",
    re.IGNORECASE | re.DOTALL,
)


@dataclass
class ParsedLayoutBlock:
    label: str
    bbox: tuple[float, float, float, float]
    text: str


_CAPTION_LABELS = {"image_caption", "caption", "figure_caption", "table_caption"}
_TITLE_LABELS = {"title", "header", "section_title"}


def _caption_grid_order(
    captions: list[ParsedLayoutBlock], page_width: int
) -> list[ParsedLayoutBlock] | None:
    """Order an image/card caption grid row by row instead of column by column.

    XY-cut prefers vertical gutters, which reads a 2x2 caption grid as
    left-column-then-right-column. Captions under images are normally read
    row by row, so detect aligned caption rows and return row-major order.
    """

    if len(captions) < 4:
        return None
    if any(len(re.sub(r"\s+", "", block.text)) > 32 for block in captions):
        return None

    rows: list[list[ParsedLayoutBlock]] = []
    for block in sorted(captions, key=lambda item: (item.bbox[1], item.bbox[0])):
        placed = False
        for row in rows:
            row_y0 = min(item.bbox[1] for item in row)
            row_y1 = max(item.bbox[3] for item in row)
            overlap = max(0.0, min(row_y1, block.bbox[3]) - max(row_y0, block.bbox[1]))
            height = max(1.0, min(row_y1 - row_y0, block.bbox[3] - block.bbox[1]))
            if overlap / height > 0.5:
                row.append(block)
                placed = True
                break
        if not placed:
            rows.append([block])

    if len(rows) < 2 or any(len(row) < 2 for row in rows):
        return None

    column_centers: list[list[float]] = []
    for row in rows:
        column_centers.append(sorted((block.bbox[0] + block.bbox[2]) / 2.0 for block in row))
    if any(len(centers) < 2 for centers in column_centers):
        return None
    tolerance = max(8.0, page_width * 0.03)
    first = column_centers[0]
    if any(len(centers) != len(first) for centers in column_centers):
        return None
    if any(
        abs(center - reference) > tolerance
        for centers in column_centers[1:]
        for center, reference in zip(centers, first, strict=True)
    ):
        return None

    return [
        block
        for row in sorted(rows, key=lambda item: min(block.bbox[1] for block in item))
        for block in sorted(row, key=lambda item: item.bbox[0])
    ]


def caption_grid_blocks(
    blocks: list[ParsedLayoutBlock], page_width: int
) -> list[ParsedLayoutBlock] | None:
    """Return captions in row-major order when a grid is detected."""

    captions = [block for block in blocks if block.label in _CAPTION_LABELS]
    return _caption_grid_order(captions, page_width)


def parse_grounding_blocks(raw: str) -> list[ParsedLayoutBlock]:
    """Parse DeepSeek-OCR grounding output into labelled blocks with boxes."""

    matches = list(GROUNDING_BLOCK_RE.finditer(raw))
    blocks: list[ParsedLayoutBlock] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        text = strip_artifacts(raw[start:end]).strip()
        if not text:
            continue
        bbox = (
            float(match.group("x0")),
            float(match.group("y0")),
            float(match.group("x1")),
            float(match.group("y1")),
        )
        blocks.append(
            ParsedLayoutBlock(
                label=(match.group("label") or "text").strip().lower() or "text",
                bbox=bbox,
                text=text,
            )
        )
    return blocks


def _xy_cut_blocks(
    blocks: list[ParsedLayoutBlock], page_width: int, page_height: int
) -> list[ParsedLayoutBlock]:
    proxy = [
        LocalLine(text=str(index), box=block.bbox, score=None) for index, block in enumerate(blocks)
    ]
    ordered = order_lines_xy_cut(proxy, page_width=page_width, page_height=page_height)
    return [blocks[int(line.text)] for line in ordered]


def order_parsed_blocks(
    blocks: list[ParsedLayoutBlock], page_width: int, page_height: int
) -> list[ParsedLayoutBlock]:
    """Restore reading order from block geometry using recursive XY-cut."""

    if not blocks:
        return []
    if all(block.label in _CAPTION_LABELS | _TITLE_LABELS for block in blocks):
        captions = [block for block in blocks if block.label in _CAPTION_LABELS]
        grid = _caption_grid_order(captions, page_width)
        if grid:
            titles = sorted(
                (block for block in blocks if block.label in _TITLE_LABELS),
                key=lambda item: (item.bbox[1], item.bbox[0]),
            )
            if titles and max(block.bbox[3] for block in titles) > min(
                block.bbox[1] for block in captions
            ):
                return _xy_cut_blocks(blocks, page_width, page_height)
            return titles + grid
    return _xy_cut_blocks(blocks, page_width, page_height)


def to_layout_blocks(
    blocks: list[ParsedLayoutBlock],
    *,
    image_width: int,
    image_height: int,
    y_offset: int,
    scale: float,
) -> list[LayoutBlock]:
    """Map chunk-local grounding boxes back to original image coordinates."""

    scale = scale or 1.0
    result: list[LayoutBlock] = []
    for block in blocks:
        x0, y0, x1, y1 = block.bbox
        mapped = [
            max(0.0, min(float(image_width), x0 / scale)),
            max(0.0, min(float(image_height), y_offset + y0 / scale)),
            max(0.0, min(float(image_width), x1 / scale)),
            max(0.0, min(float(image_height), y_offset + y1 / scale)),
        ]
        result.append(
            LayoutBlock(
                label=block.label,
                bbox=[round(value, 1) for value in mapped],
                text=block.text,
            )
        )
    return result


def layout_text(blocks: list[ParsedLayoutBlock]) -> str:
    return "\n".join(block.text.strip() for block in blocks if block.text.strip()).strip()
