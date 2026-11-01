from __future__ import annotations

import json

from PIL import Image

from app.dataset import import_images, validate_manifest, validate_manifest_file


def _make_image(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (200, 300), "white").save(path)
    return path


def test_import_images_creates_manifest_and_preserves_existing(tmp_path):
    images_dir = tmp_path / "raw"
    _make_image(images_dir / "normal" / "a.png")
    _make_image(images_dir / "long" / "b.jpg")
    _make_image(images_dir / "table" / "c.webp")
    manifest = tmp_path / "manifest.json"

    summary = import_images(images_dir, manifest)
    assert summary["total"] == 3
    assert summary["missing_annotations"] == 3
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    categories = {item["category"] for item in payload["items"]}
    assert categories == {"normal", "long", "table"}

    payload["items"][0]["ground_truth_text"] = "人工转写"
    manifest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    _make_image(images_dir / "normal" / "d.png")
    summary2 = import_images(images_dir, manifest)
    assert summary2["total"] == 4
    payload2 = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload2["items"][0]["ground_truth_text"] == "人工转写"


def test_validate_manifest_detects_missing_ground_truth(tmp_path):
    _make_image(tmp_path / "a.png")
    payload = {
        "version": 1,
        "items": [
            {
                "id": "a",
                "image": "a.png",
                "category": "normal",
                "ground_truth_text": "",
                "key_fields": {},
            }
        ],
    }
    result = validate_manifest(payload, tmp_path)
    assert result["valid"] is False
    assert any("ground_truth_text" in item["message"] for item in result["errors"])
    assert result["category_counts"]["normal"] == 1

    result_ok = validate_manifest(payload, tmp_path, require_ground_truth=False)
    assert result_ok["valid"] is True


def test_validate_manifest_detects_bad_image_and_duplicate_id(tmp_path):
    payload = {
        "version": 1,
        "items": [
            {
                "id": "same",
                "image": "missing.png",
                "category": "normal",
                "ground_truth_text": "x",
            },
            {
                "id": "same",
                "image": "missing2.png",
                "category": "unknown",
                "ground_truth_text": "x",
            },
        ],
    }
    result = validate_manifest(payload, tmp_path)
    assert not result["valid"]
    messages = [item["message"] for item in result["errors"]]
    assert any("重复" in message for message in messages)
    assert any("图片不存在" in message for message in messages)
    assert any("未知 category" in message for message in messages)


def test_validate_manifest_file(tmp_path):
    _make_image(tmp_path / "a.png")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "a",
                        "image": "a.png",
                        "category": "normal",
                        "ground_truth_text": "文本",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    result = validate_manifest_file(manifest)
    assert result["valid"] is True
    assert result["warnings"]
