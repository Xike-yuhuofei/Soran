from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.dataset import import_images, validate_manifest_file  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="扫描真实图片并生成/追加测试集清单；不会编造标注或精度结果。"
    )
    parser.add_argument("--images-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--no-recursive", action="store_true")
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="跳过导入后的清单校验（默认会提示未标注项）",
    )
    args = parser.parse_args()
    if not args.images_dir.is_dir():
        print(f"图片目录不存在：{args.images_dir}")
        return 2
    summary = import_images(
        args.images_dir,
        args.manifest,
        recursive=not args.no_recursive,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not args.no_validate:
        validation = validate_manifest_file(args.manifest, require_ground_truth=False)
        print("校验：", json.dumps(validation, ensure_ascii=False, indent=2))
        if not validation["valid"]:
            return 1
    print(
        "下一步：逐条填写 ground_truth_text / key_fields / boundary_texts，再运行 tools/evaluate.py。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
