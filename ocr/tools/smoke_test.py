from __future__ import annotations

import argparse
import asyncio
import io
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.policy import FreePolicy  # noqa: E402
from app.siliconflow import SiliconFlowOCRClient  # noqa: E402
from app.storage import ChunkCache, JobBudget, UsageLedger  # noqa: E402

FONT_CANDIDATES = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def make_sample() -> bytes:
    font_path = next((path for path in FONT_CANDIDATES if Path(path).exists()), None)
    title = ImageFont.truetype(font_path, 40) if font_path else ImageFont.load_default()
    body = ImageFont.truetype(font_path, 24) if font_path else ImageFont.load_default()
    image = Image.new("RGB", (750, 1800), "white")
    draw = ImageDraw.Draw(image)
    lines = [
        (30, "素然之境 SORAN", title),
        (95, "男士莫代尔圆领短袖", title),
        (180, "商品名称：男士基础圆领短袖T恤", body),
        (230, "品牌：SORAN", body),
        (280, "型号：SR-M2001", body),
        (380, "面料成分：92%莫代尔 8%氨纶", body),
        (430, "执行标准：FZ/T 73020-2019", body),
        (480, "安全类别：GB 18401-B", body),
        (580, "洗涤说明：手洗，不可漂白，低温熨烫", body),
        (630, "悬挂晾干，避免暴晒", body),
        (730, "尺码表", title),
        (800, "尺码    身高/胸围      衣长", body),
        (850, "M       170/90A        68cm", body),
        (900, "L       175/95A        70cm", body),
        (950, "XL      180/100A       72cm", body),
        (1050, "颜色：黑色 / 白色 / 灰蓝", body),
        (1100, "包装规格：1件/袋", body),
        (1200, "价格：¥129.00", title),
        (1300, "温馨提示", title),
        (1360, "商品颜色因拍摄光线不同可能存在轻微色差，", body),
        (1410, "请以实物为准。", body),
    ]
    for y, text, font in lines:
        draw.text((30, y), text, fill=(24, 24, 28), font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="真实调用硅基流动免费 OCR 模型的冒烟测试（会产生免费模型请求，不消耗费用）。"
    )
    parser.add_argument("--real", action="store_true", help="确认真实调用云端免费模型")
    parser.add_argument("--image", type=Path, help="可选测试图片；缺省生成合成样例")
    parser.add_argument("--out-dir", type=Path, default=Path(".data") / "smoke")
    parser.add_argument("--no-markdown", action="store_true", help="跳过 Markdown 提示词测试")
    args = parser.parse_args()
    if not args.real:
        print("为避免误触发云端请求，必须显式传入 --real。")
        print("示例：SILICONFLOW_API_KEY=... python tools/smoke_test.py --real")
        return 2

    settings = get_settings()
    if not settings.api_key_configured:
        print("缺少 SILICONFLOW_API_KEY（或 OCR_SILICONFLOW_API_KEY）。")
        return 2
    policy = FreePolicy(settings)
    status = await policy.refresh(force=True)
    print("免费策略：", json.dumps(status["models"], ensure_ascii=False))
    for model in (settings.primary_model, settings.review_model):
        policy.assert_free(model)

    client = SiliconFlowOCRClient(settings, policy, ChunkCache(settings))
    budget = JobBudget(settings, UsageLedger(settings), f"smoke-{datetime.now():%Y%m%d%H%M%S}")
    models = await client.list_models()
    for model in (settings.primary_model, settings.review_model):
        if model not in models:
            print(f"模型不可用：{model}")
            return 1

    image_bytes = args.image.read_bytes() if args.image else make_sample()
    mime = "image/png" if args.image and args.image.suffix.lower() == ".png" else "image/jpeg"
    if args.image and args.image.suffix.lower() not in {".png"}:
        parsed = Image.open(io.BytesIO(image_bytes))
        buffer = io.BytesIO()
        parsed.convert("RGB").save(buffer, format="JPEG", quality=92)
        image_bytes = buffer.getvalue()
        mime = "image/jpeg"

    args.out_dir.mkdir(parents=True, exist_ok=True)
    runs = [(settings.primary_model, "text", "primary-text")]
    if not args.no_markdown:
        runs.append((settings.primary_model, "markdown", "primary-markdown"))
    runs.append((settings.review_model, "text", "review"))

    failures = 0
    for model, mode, label in runs:
        started = time.monotonic()
        try:
            response = await client.ocr_chunk(
                model=model,
                image_bytes=image_bytes,
                mime=mime,
                mode=mode,
                budget=budget,
                allow_cache=False,
            )
            path = args.out_dir / f"{label}.txt"
            path.write_text(response.text, encoding="utf-8")
            elapsed = time.monotonic() - started
            print(
                f"[OK] {label}: model={model} mode={mode} chars={len(response.text)} "
                f"attempts={response.attempts} latency={response.latency_ms}ms wall={elapsed:.1f}s "
                f"usage={response.usage} -> {path}"
            )
            if not response.text.strip():
                failures += 1
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"[FAIL] {label}: {type(exc).__name__}: {exc}")
    print(f"完成：{len(runs) - failures}/{len(runs)} 成功，应用层请求计数={budget.used}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
