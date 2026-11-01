from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from PIL import Image

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
DATASET_CATEGORIES = {"normal", "long", "table", "complex"}
CATEGORY_TARGETS = {"normal": 50, "long": 50, "table": 50, "complex": 50}


def discover_images(root: Path, recursive: bool = True) -> list[Path]:
    pattern = "**/*" if recursive else "*"
    return sorted(
        path
        for path in root.glob(pattern)
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def infer_category(path: Path) -> str:
    for parent in path.parents:
        if parent.name in DATASET_CATEGORIES:
            return parent.name
    return "normal"


def _unique_id(base: str, used: set[str]) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", base).strip("-") or "item"
    candidate = cleaned
    index = 1
    while candidate in used:
        index += 1
        candidate = f"{cleaned}-{index}"
    used.add(candidate)
    return candidate


def _relative_image(path: Path, manifest_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(manifest_dir.resolve()))
    except ValueError:
        return str(path.resolve())


def import_images(
    images_dir: Path,
    manifest_path: Path,
    *,
    recursive: bool = True,
) -> dict[str, Any]:
    manifest_dir = manifest_path.parent
    manifest_dir.mkdir(parents=True, exist_ok=True)
    if manifest_path.exists():
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            payload = {"version": 1, "items": payload}
    else:
        payload = {"version": 1, "items": []}

    items = payload.setdefault("items", [])
    existing_paths = {str(item.get("image", "")) for item in items}
    used_ids = {str(item.get("id", "")) for item in items}
    added = 0
    for path in discover_images(images_dir, recursive=recursive):
        relative = _relative_image(path, manifest_dir)
        if relative in existing_paths:
            continue
        category = infer_category(path)
        item_id = _unique_id(f"{category}-{path.stem}", used_ids)
        items.append(
            {
                "id": item_id,
                "image": relative,
                "category": category,
                "ground_truth_text": "",
                "key_fields": {},
                "boundary_texts": [],
                "notes": "TODO: 人工逐字转写后再运行评测",
            }
        )
        existing_paths.add(relative)
        added += 1

    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "manifest": str(manifest_path),
        "added": added,
        "total": len(items),
        "missing_annotations": sum(
            1 for item in items if not str(item.get("ground_truth_text", "")).strip()
        ),
    }


def _resolve_image(manifest_dir: Path, image_value: str) -> Path:
    path = Path(image_value)
    return path if path.is_absolute() else manifest_dir / path


def validate_manifest(
    payload: dict[str, Any],
    manifest_dir: Path,
    *,
    require_ground_truth: bool = True,
    check_decodable: bool = True,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return {
            "valid": False,
            "items": 0,
            "category_counts": {},
            "errors": [{"item_id": "", "message": "manifest 必须包含 items 数组"}],
            "warnings": [],
        }

    counts = {category: 0 for category in DATASET_CATEGORIES}
    ids: set[str] = set()
    for index, item in enumerate(items):
        item_id = str(item.get("id") or f"item-{index}")
        if item_id in ids:
            issues.append({"item_id": item_id, "message": "重复的 id"})
        ids.add(item_id)
        image_value = str(item.get("image", "")).strip()
        if not image_value:
            issues.append({"item_id": item_id, "message": "缺少 image 路径"})
        else:
            path = _resolve_image(manifest_dir, image_value)
            if not path.exists():
                issues.append({"item_id": item_id, "message": f"图片不存在：{path}"})
            elif check_decodable:
                try:
                    with Image.open(path) as image:
                        image.load()
                except Exception as exc:  # noqa: BLE001
                    issues.append(
                        {"item_id": item_id, "message": f"图片无法解码：{type(exc).__name__}"}
                    )
        category = str(item.get("category", "uncategorized"))
        if category in counts:
            counts[category] += 1
        else:
            issues.append({"item_id": item_id, "message": f"未知 category：{category}"})
        if require_ground_truth and not str(item.get("ground_truth_text", "")).strip():
            issues.append({"item_id": item_id, "message": "尚未人工转写 ground_truth_text"})
        key_fields = item.get("key_fields", {})
        if not isinstance(key_fields, dict):
            issues.append({"item_id": item_id, "message": "key_fields 必须是对象"})
        boundary_texts = item.get("boundary_texts", [])
        if not isinstance(boundary_texts, list):
            issues.append({"item_id": item_id, "message": "boundary_texts 必须是数组"})

    warnings = [
        {
            "item_id": "",
            "message": f"{category} 当前 {counts[category]} 条，低于建议的 {target} 条",
        }
        for category, target in CATEGORY_TARGETS.items()
        if counts[category] < target
    ]
    errors = [issue for issue in issues if "低于建议" not in issue["message"]]
    return {
        "valid": not errors,
        "items": len(items),
        "category_counts": counts,
        "errors": errors,
        "warnings": warnings,
    }


def validate_manifest_file(path: Path, **kwargs: Any) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return validate_manifest(payload, path.parent, **kwargs)
