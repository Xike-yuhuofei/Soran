from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.dataset import validate_manifest_file  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="校验测试集清单：图片存在、可解码、ID 唯一、标注完整、各类别数量。"
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--allow-unannotated",
        action="store_true",
        help="允许 ground_truth_text 为空（仅检查导入结构）",
    )
    parser.add_argument("--no-decode", action="store_true", help="跳过图片解码检查")
    args = parser.parse_args()
    result = validate_manifest_file(
        args.manifest,
        require_ground_truth=not args.allow_unannotated,
        check_decodable=not args.no_decode,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["valid"]:
        print("清单校验失败：请先修复 errors。没有完成人工标注前不得运行精度评测。")
        return 1
    if result["warnings"]:
        print("注意：类别数量低于建议值；指标只对当前样本有效。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
