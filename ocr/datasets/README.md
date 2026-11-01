# 电商详情页 OCR 测试集

本目录用于导入真实商品详情页图片并完成人工标注。仓库不内置受版权或隐私限制的商品图，也不提供任何“预置精度成绩”。

## 目录建议

```
ocr/datasets/
  manifest.json          # 测试清单（从 manifest.example.json 复制）
  images/
    normal/*.png         # 普通详情图片
    long/*.png           # 超长详情图片
    table/*.png          # 密集参数 / 表格截图
    complex/*.png        # 复杂背景 / 艺术字体
```

## 最低建议规模

| 场景 | category | 最低建议数量 |
|---|---:|---:|
| 普通详情图片 | `normal` | 50 |
| 超长商品详情图 | `long` | 50 |
| 密集参数、表格截图 | `table` | 50 |
| 复杂背景、艺术字体 | `complex` | 50 |

这是一项目标而非已完成的数据。没有完成标注前，不得填写或宣称任何精度指标。

## 标注流程

1. 获取你有权使用的商品详情图，去除订单号、收货信息、个人水印等隐私内容。
2. 用任意文本编辑器或标注工具逐字转写图片文字，保存为 `ground_truth_text`。
3. 标注关键字段 `key_fields`，建议至少覆盖：
   - `brand` 品牌
   - `product_name` 商品名称
   - `fabric_composition` 面料成分（如 `92%莫代尔 8%氨纶`）
   - `size` 尺码 / 尺寸
   - `size_chart` 尺码表中的具体参数行
   - `sku` 型号 / 货号 / SKU
   - `wash_instruction` 洗涤说明
   - `standard` 执行标准
   - `safety_category` 安全类别
   - `price` 价格
   - `packaging` 包装 / 数量
4. 对长图，建议在 `boundary_texts` 中标注分块边界附近的关键文字片段（例如跨切分线的整行），用于计算边界漏字率。
5. 一条样本由同一人转写、另一人抽查；有争议的字段记录在 `notes`。

## 清单格式

```json
{
  "version": 1,
  "items": [
    {
      "id": "normal-001",
      "image": "images/normal/normal-001.png",
      "category": "normal",
      "ground_truth_text": "品牌：SORAN\n面料成分：92%莫代尔 8%氨纶\n...",
      "key_fields": {
        "brand": "SORAN",
        "fabric_composition": "92%莫代尔 8%氨纶",
        "sku": "SR-M2001"
      },
      "boundary_texts": ["分块边界前最后一行", "分块边界后第一行"],
      "notes": "手机截图，轻微倾斜"
    }
  ]
}
```

## 运行评测

评测会真实调用免费模型，只能在确认免费策略后手动运行；不会在 CI 中默认执行。

```bash
cd ocr
SILICONFLOW_API_KEY=... .venv/bin/python tools/evaluate.py \
  --manifest datasets/manifest.json \
  --variants B,C,D \
  --real \
  --output .data/evaluation/report.json
```

生成 `report.json` 与 `report.md`。报告只对已标注样本有效，并明确给出样本数、CER、行召回、关键字段完全正确率、重复引入率、边界漏字率、P95 延迟与单图请求次数。

## 评测对比方案

- `A`：DeepSeek-OCR 单模型，整图不切分（仅适合普通高度图片，作为基线）。
- `B`：DeepSeek-OCR + 智能分块。
- `C`：DeepSeek-OCR + 智能分块 + PaddleOCR-VL 按需复核。
- `D`：C + 本地 PP-OCR 交叉验证（需安装 `paddleocr` 并启用 `OCR_LOCAL_OCR_ENABLED=true`）。

只有当复杂方案在独立测试集上产生可验证收益时，才应默认启用额外模块。
