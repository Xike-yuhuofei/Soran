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


def order_parsed_blocks(
    blocks: list[ParsedLayoutBlock], page_width: int, page_height: int
) -> list[ParsedLayoutBlock]:
    """Restore reading order from block geometry using recursive XY-cut."""

    if not blocks:
        return []
    proxy = [
        LocalLine(text=str(index), box=block.bbox, score=None) for index, block in enumerate(blocks)
    ]
    ordered = order_lines_xy_cut(proxy, page_width=page_width, page_height=page_height)
    return [blocks[int(line.text)] for line in ordered]


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
