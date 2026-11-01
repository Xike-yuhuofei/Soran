from __future__ import annotations

import re
import unicodedata

from .schemas import KeyField

_SEP = r"(?:\s*[:：]\s*|[ \u3000]{2,}|\t\s*)"
_LABEL_PATTERNS: dict[str, re.Pattern[str]] = {
    "brand": re.compile(rf"(?:品牌|Brand){_SEP}(.+)$", re.IGNORECASE),
    "product_name": re.compile(
        rf"(?:品名|商品名称|产品名称|商品名|名称){_SEP}(.+)$", re.IGNORECASE
    ),
    "size": re.compile(rf"(?:尺码|尺寸|号型|身高|适合身高){_SEP}(.+)$", re.IGNORECASE),
    "sku": re.compile(rf"(?:型号|货号|款号|SKU|产品型号|产品货号){_SEP}(.+)$", re.IGNORECASE),
    "standard": re.compile(rf"(?:执行标准|产品标准号|标准号){_SEP}(.+)$", re.IGNORECASE),
    "safety_category": re.compile(
        rf"(?:安全类别|安全技术类别|安全技术规范){_SEP}(.+)$", re.IGNORECASE
    ),
    "price": re.compile(
        rf"(?:价格|售价|到手价|券后价|活动价){_SEP}(?:¥|￥)?\s*"
        r"(\d+(?:\.\d+)?(?:\s*[-~～]\s*\d+(?:\.\d+)?)?)",
        re.IGNORECASE,
    ),
    "packaging": re.compile(rf"(?:包装规格|净含量|包装|数量){_SEP}(.+)$", re.IGNORECASE),
}

_FABRIC_WORDS = (
    "棉|莫代尔|氨纶|涤纶|锦纶|羊毛|羊绒|腈纶|粘纤|粘胶|真丝|蚕丝|麻|纤维|"
    "聚酯|尼龙|丙纶|醋酸|天丝|莱赛尔|弹性纤维"
)
_FABRIC_RE = re.compile(rf"(?:{_FABRIC_WORDS})")
_PERCENT_RE = re.compile(r"\d+(?:\.\d+)?%")
_STANDARD_RE = re.compile(
    r"((?:GB/T|GB|FZ/T|QB/T|ISO|EN)\s*\d+(?:\.\d+)?(?:[-\s]\d{4})?(?:\s*-\s*[A-Z])?)",
    re.IGNORECASE,
)
_SAFETY_RE = re.compile(r"(GB\s*18401[-\s]?[ABC]?|GB\s*31701[-\s]?[ABC]?)", re.IGNORECASE)
_PRICE_RE = re.compile(r"(?:¥|￥)\s*(\d+(?:\.\d+)?(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*元")
_WASH_RE = re.compile(r"(?:洗涤|水洗|手洗|机洗|不可漂白|不可熨烫|干洗|低温|悬挂晾干|反面洗涤)")
_WASH_CARE_RE = re.compile(
    r"(?:洗涤|水洗|手洗|机洗|漂白|熨烫|干洗|晾干|晾晒|暴晒|曝晒|低温|高温|干燥|"
    r"摩擦|拉拽|拉扯|拧干|浸泡|脱水|消毒|轻柔|缓和|悬挂|反面|单独)"
)
_WASH_NEGATIVE_RE = re.compile(r"^(?:不要|不可|请勿|勿|切勿|禁止)")
_SIZE_ROW_RE = re.compile(
    r"^(?:XS|S|M|L|XL|XXL|XXXL|XXXXL|\d+XL|均码|\d{2,3})\s+"
    r".*(?:\d{2,3}\s*/\s*\d{2,3}|\d+(?:\.\d+)?\s*cm|"
    r"\d+(?:\.\d+)?\s*[~～-]\s*\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_PERCENT_SUM_RE = re.compile(r"\d+(?:\.\d+)?%")
_SIZE_HEADER_TOKENS = (
    "腰围",
    "臀围",
    "体重",
    "衣长",
    "裤长",
    "胸围",
    "肩宽",
    "袖长",
    "身高",
)

MULTI_VALUE_FIELDS = {"wash_instruction", "size_chart", "fabric_composition"}

MAX_VALUE_LEN = 200


def _clean_value(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    value = re.sub(r"[ \t\u00a0\u3000]+", " ", value).strip(" ：:，,；;")
    return value[:MAX_VALUE_LEN]


def _is_size_header(value: str) -> bool:
    return sum(1 for token in _SIZE_HEADER_TOKENS if token in value) >= 2


def _fabric_value(line: str) -> str | None:
    normalized = unicodedata.normalize("NFKC", line)
    if "%" not in normalized or not _FABRIC_RE.search(normalized):
        return None
    cleaned = re.sub(
        r"(?:面料|成分|材质|纤维含量|composition)\s*[:：]?",
        "",
        normalized,
        flags=re.I,
    )
    return _clean_value(cleaned) or None


def extract_key_fields(text: str, chunk_index: int | None = None) -> list[KeyField]:
    fields: list[KeyField] = []
    seen: set[tuple[str, str]] = set()

    def add(name: str, value: str | None) -> None:
        value = _clean_value(value or "")
        if not value:
            return
        key = (name, value)
        if key in seen:
            return
        seen.add(key)
        fields.append(KeyField(name=name, value=value, chunk_index=chunk_index))

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for name, pattern in _LABEL_PATTERNS.items():
            match = pattern.search(line)
            if match:
                value = match.group(1)
                if name == "size" and _is_size_header(value):
                    continue
                if name == "price" and not value.strip().startswith(("¥", "￥")):
                    value = f"¥{value.strip()}"
                add(name, value)

        fabric = _fabric_value(line)
        if fabric:
            add("fabric_composition", fabric)

        if _WASH_RE.search(line) or (_WASH_NEGATIVE_RE.match(line) and _WASH_CARE_RE.search(line)):
            add("wash_instruction", line)

        if _SIZE_ROW_RE.match(line):
            add("size_chart", line)

        has_safety_label = bool(_LABEL_PATTERNS["safety_category"].search(line))
        for match in _STANDARD_RE.finditer(line):
            if has_safety_label or re.match(r"GB\s*(?:18401|31701)", match.group(1), re.IGNORECASE):
                continue
            add("standard", match.group(1))
        for match in _SAFETY_RE.finditer(line):
            add("safety_category", match.group(1))
        for match in _PRICE_RE.finditer(line):
            value = next(group for group in match.groups() if group)
            add("price", f"¥{value}")
    return fields


def merge_key_fields(fields: list[KeyField]) -> list[KeyField]:
    grouped: dict[str, list[KeyField]] = {}
    for item in fields:
        grouped.setdefault(item.name, []).append(item)

    merged: list[KeyField] = []
    for name, items in grouped.items():
        values = {normalize_field_value(item.value, name) for item in items}
        if name in MULTI_VALUE_FIELDS:
            unique_values: list[str] = []
            for item in items:
                if item.value not in unique_values:
                    unique_values.append(item.value)
            merged.append(
                KeyField(
                    name=name,
                    value="；".join(unique_values),
                    chunk_index=items[0].chunk_index,
                    confidence="cross_checked" if len(unique_values) > 1 else "unverified",
                    note=f"合并 {len(unique_values)} 条多行/多部位内容",
                )
            )
            continue
        if len(values) == 1:
            first = items[0]
            merged.append(
                KeyField(
                    name=name,
                    value=first.value,
                    chunk_index=first.chunk_index,
                    confidence="cross_checked" if len(items) > 1 else "unverified",
                    note=(
                        f"在 {len(items)} 个分块中一致" if len(items) > 1 else "未经过独立模型复核"
                    ),
                )
            )
        else:
            raw_values = sorted({item.value for item in items})
            for item in items:
                merged.append(
                    KeyField(
                        name=name,
                        value=item.value,
                        chunk_index=item.chunk_index,
                        confidence="conflict",
                        note="多处分块取值不一致：" + " | ".join(raw_values),
                    )
                )
    return merged


def normalize_field_value(value: str, name: str | None = None) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[ \t\u00a0\u3000]+", "", value)
    value = value.strip("：:，,；;")
    if name == "price":
        value = value.lstrip("¥￥")
        if re.fullmatch(r"\d+(?:\.\d+)?", value):
            value = f"{float(value):.2f}"
    elif name in {"standard", "safety_category", "sku"}:
        value = value.upper()
    elif name == "size_chart":
        value = re.sub(r"[ \t]+", "", value)
    return value


def percent_issues(text: str) -> list[str]:
    """Detect inconsistent percentage groups, especially fabric composition."""

    issues: list[str] = []
    for raw_line in text.splitlines():
        line = unicodedata.normalize("NFKC", raw_line)
        if not line.strip():
            continue
        percents = [float(m.group(0).rstrip("%")) for m in _PERCENT_RE.finditer(line)]
        if not percents:
            continue
        if len(percents) >= 2 and _FABRIC_RE.search(line):
            total = sum(percents)
            # Multi-part garments legitimately sum to 200%, 300% ... A single
            # composition that sums to 97% (or 103%) is the real error.
            nearest_hundred = round(total / 100.0) * 100.0
            if abs(total - nearest_hundred) > 0.6:
                issues.append(f"成分百分比合计为 {total:.0f}%：{line.strip()[:120]}")
        for value in percents:
            if value > 100:
                issues.append(f"百分比超过 100%：{line.strip()[:120]}")
                break
    return issues


def numeric_tokens(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?(?:%|‰)?", unicodedata.normalize("NFKC", text)))


def percent_tokens(text: str) -> set[str]:
    return set(_PERCENT_SUM_RE.findall(unicodedata.normalize("NFKC", text)))


def critical_lines(text: str) -> list[str]:
    """Lines likely to contain compliance-critical product facts."""

    critical = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if (
            _FABRIC_RE.search(stripped)
            or _WASH_RE.search(stripped)
            or _STANDARD_RE.search(stripped)
            or _SAFETY_RE.search(stripped)
            or _PERCENT_RE.search(stripped)
            or re.search(r"(?:型号|货号|SKU|尺码|品牌|价格|售价)", stripped)
        ):
            critical.append(stripped[:300])
    return critical
