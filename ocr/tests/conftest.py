from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.config import Settings
from app.policy import FreePolicy

FONT_CANDIDATES = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    config = Settings(
        data_dir=tmp_path / "data",
        siliconflow_api_key="test-key-not-real",
        request_min_interval_ms=0,
        max_retries=2,
        review_enabled=True,
        cache_enabled=True,
        max_files_per_session=5,
        chunk_target_height=1000,
        chunk_min_height=600,
        chunk_max_height=1300,
        chunk_overlap=120,
        chunk_max_width=1200,
        chunk_max_pixels=1_200_000,
        max_image_width=5000,
        max_image_height=12000,
        max_image_pixels=30_000_000,
        max_upload_bytes=10 * 1024 * 1024,
        max_requests_per_day=20,
        max_requests_per_job=20,
    )
    config.validate()
    config.data_dir.mkdir(parents=True, exist_ok=True)
    return config


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def make_ecommerce_image(height: int = 2000, width: int = 750) -> Image.Image:
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title = _font(40)
    body = _font(24)
    entries = [
        (40, 40, "素然之境 SORAN", title),
        (40, 110, "男士莫代尔圆领短袖", title),
        (40, 190, "商品名称：男士基础圆领短袖T恤", body),
        (40, 240, "品牌：SORAN", body),
        (40, 290, "型号：SR-M2001", body),
        (40, 390, "面料成分：92%莫代尔 8%氨纶", body),
        (40, 440, "执行标准：FZ/T 73020-2019", body),
        (40, 490, "安全类别：GB 18401-B", body),
        (40, 590, "洗涤说明：手洗，不可漂白，低温熨烫", body),
        (40, 640, "悬挂晾干，避免暴晒", body),
        (40, 740, "尺码表", title),
        (40, 810, "尺码    身高/胸围      衣长", body),
        (40, 860, "M       170/90A        68cm", body),
        (40, 910, "L       175/95A        70cm", body),
        (40, 960, "XL      180/100A       72cm", body),
        (40, 1060, "颜色：黑色 / 白色 / 灰蓝", body),
        (40, 1110, "包装规格：1件/袋", body),
        (40, 1210, "价格：¥129.00", title),
        (40, 1310, "温馨提示", title),
        (40, 1370, "商品颜色因拍摄光线不同可能存在轻微色差，", body),
        (40, 1420, "请以实物为准。", body),
        (40, 1520, "洗涤后请平铺晾干，避免变形。", body),
    ]
    for x, y, text, font in entries:
        if y < height - 20:
            draw.text((x, y), text, fill=(24, 24, 28), font=font)
    return image


def image_bytes(image: Image.Image, fmt: str = "PNG") -> bytes:
    import io

    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def make_free_snapshot(
    path: Path, *, free: bool = True, checked_at: datetime | None = None
) -> None:
    checked = checked_at or datetime.now(UTC)
    payload = {
        "checked_at": checked.isoformat(),
        "source": "https://www.siliconflow.cn/pricing",
        "models": {
            "deepseek-ai/DeepSeek-OCR": {
                "model_id": "deepseek-ai/DeepSeek-OCR",
                "free": free,
                "reason": "test_snapshot",
            },
            "PaddlePaddle/PaddleOCR-VL-1.5": {
                "model_id": "PaddlePaddle/PaddleOCR-VL-1.5",
                "free": free,
                "reason": "test_snapshot",
            },
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def free_policy(settings: Settings) -> FreePolicy:
    make_free_snapshot(settings.policy_snapshot_path)
    return FreePolicy(settings)


@pytest.fixture
def pricing_html() -> str:
    return PRICING_FIXTURE


PRICING_FIXTURE = """<html><script>self.__next_f.push([1,"0a:{\\"modelId\\":\\"1\\",\\"modelName\\":\\"deepseek-ai/DeepSeek-OCR\\",\\"status\\":\\"normal\\",\\"onlyByChargeBalance\\":false,\\"price\\":\\"0\\",\\"inputPrice\\":\\"0\\",\\"deprecatedTime\\":{},\\"pricing\\":[{\\"price\\":\\"0\\",\\"specification\\":\\"prompt\\"},{\\"price\\":\\"0\\",\\"specification\\":\\"completion\\"}],\\"operationLabel\\":\\"限免\\"}"])</script>
<script>self.__next_f.push([1,"0b:{\\"modelId\\":\\"2\\",\\"modelName\\":\\"PaddlePaddle/PaddleOCR-VL-1.5\\",\\"status\\":\\"normal\\",\\"onlyByChargeBalance\\":false,\\"price\\":\\"0\\",\\"inputPrice\\":\\"0\\",\\"deprecatedTime\\":{},\\"pricing\\":[{\\"price\\":\\"0\\",\\"specification\\":\\"prompt\\"},{\\"price\\":\\"0\\",\\"specification\\":\\"completion\\"}],\\"operationLabel\\":\\"免费\\"}"])</script>
<script>self.__next_f.push([1,"0c:{\\"modelId\\":\\"3\\",\\"modelName\\":\\"vendor/paid-model\\",\\"status\\":\\"normal\\",\\"onlyByChargeBalance\\":false,\\"price\\":\\"1.00\\",\\"inputPrice\\":\\"1.00\\",\\"deprecatedTime\\":{},\\"pricing\\":[{\\"price\\":\\"1.00\\",\\"specification\\":\\"prompt\\"}],\\"operationLabel\\":\\"\\"}"])</script>
</html>
"""
