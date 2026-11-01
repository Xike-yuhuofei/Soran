from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PIL import Image

from .config import Settings

logger = logging.getLogger(__name__)


@dataclass
class LocalLine:
    text: str
    box: tuple[float, float, float, float]
    score: float | None = None


@dataclass
class LocalOCRResult:
    lines: list[LocalLine] = field(default_factory=list)
    engine: str = "local"
    error: str | None = None

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines if line.text.strip())


class LocalPaddleOCR:
    """Optional PP-OCR plugin.

    The cloud pipeline works without it. Import failures are reported as an
    unavailable component, never as a fatal error.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._engine: Any | None = None
        self._import_error: str | None = None

    def available(self) -> bool:
        if not self.settings.local_ocr_enabled:
            return False
        if self._engine is not None:
            return True
        try:
            from paddleocr import PaddleOCR  # type: ignore

            kwargs: dict[str, Any] = {"lang": "ch", "use_textline_orientation": True}
            # PaddleOCR 3.x uses ocr_version; older versions ignore it.
            if self.settings.local_ocr_model:
                kwargs["ocr_version"] = self.settings.local_ocr_model
            self._engine = PaddleOCR(**kwargs)
            return True
        except Exception as exc:  # noqa: BLE001 - optional dependency boundary
            self._import_error = f"{type(exc).__name__}: {exc}"
            logger.info("Local PP-OCR unavailable: %s", self._import_error)
            return False

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.settings.local_ocr_enabled,
            "available": self._engine is not None,
            "model": self.settings.local_ocr_model,
            "error": self._import_error,
        }

    def run(self, image: Image.Image) -> LocalOCRResult:
        if not self.available() or self._engine is None:
            return LocalOCRResult(
                engine=f"local:{self.settings.local_ocr_model}",
                error=self._import_error or "local OCR disabled",
            )
        try:
            raw = self._engine.ocr(np.asarray(image.convert("RGB")))
            lines = _parse_paddle_result(raw)
            lines = order_lines_xy_cut(lines, image.width, image.height)
            return LocalOCRResult(lines=lines, engine=f"local:{self.settings.local_ocr_model}")
        except Exception as exc:  # noqa: BLE001
            return LocalOCRResult(
                engine=f"local:{self.settings.local_ocr_model}",
                error=f"{type(exc).__name__}: {exc}",
            )


def _as_box(value: Any) -> tuple[float, float, float, float] | None:
    try:
        points = np.asarray(value, dtype=float)
        if points.ndim == 2 and points.shape[0] >= 2:
            xs = points[:, 0]
            ys = points[:, 1]
            return float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())
        if points.ndim == 1 and points.size >= 4:
            x0, y0, x1, y1 = points[:4]
            return float(x0), float(y0), float(x1), float(y1)
    except (TypeError, ValueError):
        return None
    return None


def _parse_paddle_result(raw: Any) -> list[LocalLine]:
    lines: list[LocalLine] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if "rec_texts" in node:
                boxes = node.get("rec_boxes") or node.get("dt_polys") or []
                scores = node.get("rec_scores") or []
                for index, text in enumerate(node.get("rec_texts") or []):
                    box = _as_box(boxes[index]) if index < len(boxes) else None
                    score = float(scores[index]) if index < len(scores) else None
                    if text and box:
                        lines.append(LocalLine(str(text), box, score))
                return
            for value in node.values():
                visit(value)
        elif isinstance(node, (list, tuple)):
            if len(node) == 2:
                box = _as_box(node[0])
                payload = node[1]
                if box and isinstance(payload, (list, tuple)) and len(payload) >= 1:
                    text = payload[0]
                    score = payload[1] if len(payload) > 1 else None
                    if isinstance(text, str):
                        lines.append(
                            LocalLine(text, box, float(score) if score is not None else None)
                        )
                        return
            for value in node:
                visit(value)

    visit(raw)
    return lines


def order_lines_xy_cut(
    lines: list[LocalLine],
    page_width: int,
    page_height: int,
    depth: int = 0,
) -> list[LocalLine]:
    """Restore reading order with a recursive XY-cut.

    Vertical gutters are preferred (multi-column pages), then horizontal
    separations, then row clustering. This only applies to engines that return
    boxes (local PP-OCR). Cloud models return text without coordinates.
    """

    if len(lines) <= 1 or depth > 8:
        return sorted(lines, key=lambda line: (line.box[1], line.box[0]))

    boxes = [(line.box[0], line.box[1], line.box[2], line.box[3]) for line in lines]
    x0 = min(box[0] for box in boxes)
    x1 = max(box[2] for box in boxes)
    y0 = min(box[1] for box in boxes)
    y1 = max(box[3] for box in boxes)
    min_gap = max(12.0, page_width * 0.04)

    # Candidate vertical cutlines.
    sorted_x = sorted(set([x0, x1] + [box[0] for box in boxes] + [box[2] for box in boxes]))
    for left, right in zip(sorted_x, sorted_x[1:], strict=False):
        gap = right - left
        if gap < min_gap:
            continue
        crossing = [line for line in lines if line.box[0] < left and line.box[2] > right]
        if not crossing:
            left_lines = [line for line in lines if line.box[2] <= left]
            right_lines = [line for line in lines if line.box[0] >= right]
            if left_lines and right_lines and len(left_lines) + len(right_lines) == len(lines):
                return order_lines_xy_cut(left_lines, page_width, page_height, depth + 1) + (
                    order_lines_xy_cut(right_lines, page_width, page_height, depth + 1)
                )

    sorted_y = sorted(set([y0, y1] + [box[1] for box in boxes] + [box[3] for box in boxes]))
    for top, bottom in zip(sorted_y, sorted_y[1:], strict=False):
        gap = bottom - top
        if gap < max(8.0, page_height * 0.01):
            continue
        crossing = [line for line in lines if line.box[1] < top and line.box[3] > bottom]
        if not crossing:
            upper = [line for line in lines if line.box[3] <= top]
            lower = [line for line in lines if line.box[1] >= bottom]
            if upper and lower and len(upper) + len(lower) == len(lines):
                return order_lines_xy_cut(upper, page_width, page_height, depth + 1) + (
                    order_lines_xy_cut(lower, page_width, page_height, depth + 1)
                )

    rows: list[list[LocalLine]] = []
    for line in sorted(lines, key=lambda item: (item.box[1], item.box[0])):
        placed = False
        for row in rows:
            row_y0 = min(item.box[1] for item in row)
            row_y1 = max(item.box[3] for item in row)
            overlap = max(0.0, min(row_y1, line.box[3]) - max(row_y0, line.box[1]))
            height = max(1.0, min(row_y1 - row_y0, line.box[3] - line.box[1]))
            if overlap / height > 0.5:
                row.append(line)
                placed = True
                break
        if not placed:
            rows.append([line])
    return [line for row in rows for line in sorted(row, key=lambda item: item.box[0])]
