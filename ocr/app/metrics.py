from __future__ import annotations

import re
import unicodedata
from typing import Any

from .schemas import KeyField


def _normalize(text: str, strip_whitespace: bool = True) -> str:
    text = unicodedata.normalize("NFKC", text).replace("\r\n", "\n")
    if strip_whitespace:
        text = re.sub(r"\s+", "", text)
    return text


def levenshtein_distance(left: str, right: str) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for i, char_left in enumerate(left, start=1):
        current = [i]
        for j, char_right in enumerate(right, start=1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            substitute = previous[j - 1] + (char_left != char_right)
            current.append(min(insert, delete, substitute))
        previous = current
    return previous[-1]


def character_error_rate(reference: str, hypothesis: str) -> float:
    ref = _normalize(reference)
    hyp = _normalize(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return levenshtein_distance(ref, hyp) / len(ref)


def line_recall(reference: str, hypothesis: str) -> float:
    """Approximate text-region recall using annotated reference lines.

    Ground-truth boxes are not present in most OCR outputs, so this measures
    what fraction of reference non-empty lines can be found in the output.
    """

    reference_lines = [_normalize(line) for line in reference.splitlines() if _normalize(line)]
    if not reference_lines:
        return 1.0
    haystack = _normalize(hypothesis)
    found = sum(1 for line in reference_lines if line in haystack)
    return found / len(reference_lines)


def duplicate_line_rate(text: str) -> float:
    lines = [_normalize(line) for line in text.splitlines() if _normalize(line)]
    if not lines:
        return 0.0
    unique = len(set(lines))
    return max(0.0, (len(lines) - unique) / len(lines))


def introduced_duplicate_rate(reference: str, hypothesis: str) -> float:
    base = duplicate_line_rate(reference)
    output = duplicate_line_rate(hypothesis)
    return max(0.0, output - base)


def key_field_accuracy(
    expected: dict[str, str],
    fields: list[KeyField] | list[dict[str, Any]],
) -> tuple[float, dict[str, Any]]:
    if not expected:
        return 1.0, {"total": 0, "correct": 0, "details": []}

    actual: dict[str, list[str]] = {}
    for field in fields:
        name = field.name if isinstance(field, KeyField) else field.get("name", "")
        value = field.value if isinstance(field, KeyField) else field.get("value", "")
        actual.setdefault(name, []).append(_normalize(str(value), strip_whitespace=True))

    correct = 0
    details = []
    for name, value in expected.items():
        target = _normalize(value, strip_whitespace=True)
        candidates = actual.get(name, [])
        matched = any(target == candidate for candidate in candidates)
        details.append(
            {
                "field": name,
                "expected": value,
                "actual": fields_value(fields, name),
                "correct": matched,
            }
        )
        correct += int(matched)
    total = len(expected)
    return correct / total, {"total": total, "correct": correct, "details": details}


def fields_value(fields: list[KeyField] | list[dict[str, Any]], name: str) -> list[str]:
    values = []
    for field in fields:
        if isinstance(field, KeyField):
            if field.name == name:
                values.append(field.value)
        elif field.get("name") == name:
            values.append(str(field.get("value", "")))
    return values


def boundary_miss_rate(boundary_texts: list[str], hypothesis: str) -> float | None:
    """Check annotated boundary snippets survive chunking.

    If the manifest provides no boundary snippets, the metric is None rather
    than silently reported as zero.
    """

    if not boundary_texts:
        return None
    normalized = _normalize(hypothesis)
    missing = sum(1 for text in boundary_texts if _normalize(text) not in normalized)
    return missing / len(boundary_texts)


def summarize(values: list[float | int | None]) -> dict[str, Any]:
    present = [value for value in values if value is not None]
    if not present:
        return {"count": 0, "mean": None, "p50": None, "p95": None, "max": None}
    sorted_values = sorted(float(value) for value in present)

    def percentile(p: float) -> float:
        index = min(len(sorted_values) - 1, max(0, round((len(sorted_values) - 1) * p)))
        return sorted_values[index]

    return {
        "count": len(present),
        "mean": sum(sorted_values) / len(sorted_values),
        "p50": percentile(0.5),
        "p95": percentile(0.95),
        "max": sorted_values[-1],
    }
