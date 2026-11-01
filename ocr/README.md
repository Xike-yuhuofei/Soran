# Soran OCR · 电商详情页高精度文字提取

面向淘宝、天猫、京东、拼多多、抖音等商品详情图的长图 OCR 工具。重点解决“超长图整体缩放导致小字丢失、切图切断文字、重叠区重复、数字/成分/型号出错、模型编造内容”等问题。

**核心约束：云端只调用经运行时核实为免费的模型，绝不能自动产生付费请求。**

## 功能

- 多图上传、拖拽、顺序调整；PNG / JPEG / WebP、手机截图、超长详情图。
- 电商详情页专用切图：按投影空白带/文字行间切分，固定 120px 重叠，保留原图坐标；默认目标高度 1200px，可配置。
- DeepSeek-OCR 主识别（纯文字与 Markdown 两种官方提示词），分块并发、限流、超时、指数退避重试。
- PaddleOCR-VL-1.5 按需复核：仅对可疑分块、数字/百分比/型号/表格等关键内容调用。
- 文本合并与重叠去重，去重记录可审计；TXT / Markdown / JSON 三种导出；结果可人工编辑。
- Markdown/grounding 模式解析逐块 bbox，保存原图坐标并用递归 XY-cut 恢复复杂布局阅读顺序；本地 PP-OCR 使用文本框 XY-cut。
- 关键字段提取：品牌、品名、面料成分、尺码、型号/SKU、洗涤、执行标准、安全类别、价格、包装。
- 两级质量检查：空块/墨迹不符、垃圾字符、数字百分比冲突、重复噪声、强制切分、模型不确定标记；模型置信度、启发式质量分、多模型一致性分别记录，不混为一谈。
- 免费模型策略守卫：官方定价页运行时校验 + 快照过期即阻止；模型白名单；无付费兜底。
- 请求额度（单任务/单日）、并发、缓存、断点续跑；API 失败保留已完成结果。
- 可选本地 PP-OCRv5/v6 插件，只在启用后参与交叉验证或云端失败兜底。
- 本地 Web 界面，显式云端上传授权提示。

## 快速开始

```bash
cd ocr
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -e ".[dev]"
cp .env.example .env
# 编辑 .env，填入 SILICONFLOW_API_KEY
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 http://127.0.0.1:8000 。上传图片 → 勾选云端上传授权 → 开始识别。

> `SILICONFLOW_API_KEY` 只从环境变量或 `ocr/.env` 读取；不会返回给前端，也不会写入结果 JSON。`.env` 已被 Git 忽略。

### 使用 pip（不使用 uv）

```bash
cd ocr
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 免费调用保障

本系统在每次任务开始前抓取硅基流动官方定价页，确认模型价格为 0 且状态正常；校验结果写入快照。快照超过 `OCR_POLICY_MAX_SNAPSHOT_AGE_HOURS`（默认 24 小时）或无法刷新时，**阻止所有云端调用**，并提示人工核实。

已核实（2026-11-01，官方定价页）：

| 用途 | 模型 ID | 官方状态 | 证据 |
|---|---|---|---|
| 主识别 | `deepseek-ai/DeepSeek-OCR` | 价格 0，标签“限免” | `price=0`、`inputPrice=0`、`pricing[].price=0` |
| 辅助复核 | `PaddlePaddle/PaddleOCR-VL-1.5` | 免费 | 页面“免费”、模型对象 `price=0` |

保护措施：

1. 模型白名单注册表，未知模型直接拒绝。
2. 不实现“主模型失败自动切换付费模型”的逻辑。
3. 单任务 `OCR_MAX_REQUESTS_PER_JOB`、单日 `OCR_MAX_REQUESTS_PER_DAY` 请求上限。
4. 并发信号量与最小请求间隔。
5. 内容哈希缓存，同一分块重复任务不再次请求。
6. 402（计费拒绝）立即停止，不重试。
7. UI 显示免费策略快照时间；过期时开始识别会被阻止并提示刷新。

**重要：应用层额度不能替代硅基流动账户级计费保护。** 部署时还应在云平台关闭自动充值/自动续费、设置低余额提醒，并定期核对账单。详见 [DEPLOYMENT.md](docs/DEPLOYMENT.md)。

## 配置

复制 `.env.example`。最常用配置：

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `SILICONFLOW_API_KEY` | — | 必填；也支持 `OCR_SILICONFLOW_API_KEY` |
| `OCR_PRIMARY_MODEL` | `deepseek-ai/DeepSeek-OCR` | 必须在白名单内且核实免费 |
| `OCR_REVIEW_MODEL` | `PaddlePaddle/PaddleOCR-VL-1.5` | 同上 |
| `OCR_REVIEW_ENABLED` | `true` | 是否允许按需复核 |
| `OCR_PROMPT_MODE` | `text` | `text`（Free OCR）或 `markdown`（文档转 Markdown） |
| `OCR_CHUNK_TARGET_HEIGHT` | `1200` | 目标分块高度，建议 1000–1500 |
| `OCR_CHUNK_OVERLAP` | `120` | 相邻分块重叠 |
| `OCR_CHUNK_MAX_WIDTH` | `1400` | 分块最大宽度（超出等比缩小） |
| `OCR_CHUNK_MAX_PIXELS` | `1500000` | 分块最大像素数，防止视觉 token 过大 |
| `OCR_MAX_REQUESTS_PER_JOB` | `80` | 单任务请求上限（含重试） |
| `OCR_MAX_REQUESTS_PER_DAY` | `200` | 单日请求上限 |
| `OCR_MAX_CONCURRENT_REQUESTS` | `2` | 并发上限 |
| `OCR_MAX_REVIEWS_PER_JOB` | `40` | 单任务最多复核分块数 |
| `OCR_CACHE_ENABLED` | `true` | 分块结果缓存 |
| `OCR_POLICY_MAX_SNAPSHOT_AGE_HOURS` | `24` | 免费快照最大年龄，过期阻止调用 |
| `OCR_LOCAL_OCR_ENABLED` | `false` | 可选本地 PP-OCR |

## 长图切分

- 先做方向校正、尺寸/像素数安全校验，超过上限直接拒绝，不无限解码。
- 在缩略灰度图上做局部对比度墨迹检测，抑制表格长横线/竖线后计算行投影。
- 在 `[min, max]` 高度范围内优先选择宽空白带中心切分；找不到则扩大搜索；仍找不到才选择墨迹最少行，并标记 `forced_cut`、加大重叠。
- 每个分块记录 `y0/y1`、上下重叠、缩放比例、是否强制切分；JSON 可追溯。
- 分块按原始图片从上到下顺序合并；分块内部保留模型原生阅读顺序。
- Markdown/grounding 模式的响应包含 `<|det|>[[x0,y0,x1,y1]]<|/det|>` 块坐标；系统解析标签、文本和 bbox，映射回原图坐标，并用递归 XY-cut 恢复多栏/复杂布局顺序。TXT/Markdown 仍可从这些布局块重建。
- 本地 PP-OCR 返回文本框时同样使用 XY-cut 恢复多栏/分栏阅读顺序；纯文字提示词模式没有 bbox，需依赖模型原生顺序。

## 合并去重

仅对相邻（或中间分块失败时最近成功）分块的文本尾部/头部做行级对齐；匹配行数受物理重叠高度约束。删除的行保存在 JSON 的审计信息中（`warnings` 记录 + `overlap_removed_lines`），避免“静默丢字”。物理上不相邻的重复文案不会被删除。

## 质量与复核

| 指标 | 来源 | 说明 |
|---|---|---|
| `confidence` | API（若返回） | SiliconFlow 当前 OCR 响应未返回 logprob，因此为 `null`，UI 显示“未知” |
| `quality_score` | 启发式 | 墨迹/文字量、垃圾字符、重复行、百分比、切分风险；0–1 |
| `consistency_score` | 多模型 | 主模型与复核模型文本相似度；冲突另存 `conflicts` |

复核策略：质量异常（空块、墨迹不匹配、垃圾字符、数字冲突、强制切分、模型标记不确定）+ 关键内容（百分比、型号、尺码、标准、面料、价格）+ 表格样文本，按需调用 PaddleOCR-VL；默认不逐张全量复核。复核结果**不会**被自动替换为主结果，冲突只标记待人工确认。

## 输出

- `TXT`：NFKC 排版格式剥离后的纯文字，按阅读顺序，表格转为制表符分隔行。
- `Markdown`：保留模型输出的标题/列表/表格结构；纯文字模式按段落生成，不编造标题。
- `JSON`：图片编号、原图尺寸、分块坐标/缩放/重叠、文本、引擎、原始响应文本、布局块（label + 原图 bbox + 文本）、置信度、质量分、一致性、是否复核、复核文本、冲突、是否需人工检查、错误、API 请求数、免费策略快照。

## 测试

```bash
cd ocr
.venv/bin/ruff check .
.venv/bin/pytest -q
.venv/bin/pytest --cov=app --cov-report=term-missing
```

- 单元/集成测试默认使用 Mock 传输，不访问云端。
- 真实 API 冒烟（手动执行，使用已核实免费模型）：

```bash
SILICONFLOW_API_KEY=... .venv/bin/python tools/smoke_test.py --real
```

- 数据集评测（需先导入并人工标注）：

```bash
# 1) 扫描真实图片，生成待标注清单（不会编造标注）
.venv/bin/python tools/import_dataset.py \
  --images-dir datasets/images --manifest datasets/manifest.json

# 2) 人工填写 ground_truth_text / key_fields / boundary_texts 后校验
.venv/bin/python tools/validate_dataset.py --manifest datasets/manifest.json

# 3) 运行评测
SILICONFLOW_API_KEY=... .venv/bin/python tools/evaluate.py \
  --manifest datasets/manifest.json --variants B,C,D --real
```

评测说明与标注格式见 [datasets/README.md](datasets/README.md)。仓库没有真实商品标注数据，因此**没有可对外宣称的验收精度**；合成图片冒烟结果只用于验证工程链路，见 [docs/TEST_REPORT.md](docs/TEST_REPORT.md)。

## 可选本地 PP-OCR

```bash
.venv/bin/pip install -e ".[local]"
```

```bash
OCR_LOCAL_OCR_ENABLED=true
OCR_LOCAL_OCR_MODEL=PP-OCRv6   # 不支持时自动回退 PP-OCRv5 / 已安装默认版本
```

本地 OCR 用于交叉验证或云端失败兜底，不改变“云端免费白名单”策略。PaddleOCR 3.x 当前默认使用 PP-OCRv6；插件会尝试请求的版本，失败时自动回退并记录实际模型。

## 目录

```
ocr/
  app/
    main.py          FastAPI 路由与静态页面
    policy.py        免费模型白名单与官方定价页校验
    siliconflow.py   云端客户端、重试、限流、缓存
    imaging.py       图片校验、长图切分、分块渲染
    layout.py        grounding bbox 解析、原图坐标映射、XY-cut 阅读顺序
    merge.py         重叠去重、纯文本/Markdown 转换
    dataset.py       测试集导入、清单校验、类别统计
    fields.py        关键字段提取与数字校验
    quality.py       质量分、模型一致性、冲突
    pipeline.py      分块识别编排、复核、断点续跑
    local_ocr.py     可选 PP-OCRv6/v5 插件 + XY-cut
    storage.py       会话、任务、额度账本、缓存
    metrics.py       CER/行召回/关键字段/重复率
    static/          本地 Web 界面
  tests/             91 个单元/集成测试
  tools/             真实冒烟、数据集导入/校验、评测
  datasets/          标注格式与测试集导入说明
  docs/              部署说明、测试报告、证据
```

## 已知限制

- 没有真实标注测试集，无法给出 CER、关键字段 ≥99% 等验收结论；必须先导入并人工标注。
- SiliconFlow 当前不返回 OCR 置信度，`confidence` 为 `null`；不要把它与启发式质量分混用。
- DeepSeek-OCR 的 `Free OCR.` 仍可能输出 Markdown 排版；系统对 TXT 做格式剥离，JSON 保留原始文本。
- Markdown 模式的 grounding 输出包含 bbox token；系统会解析并保存为原图坐标的 `layout_blocks`，用 XY-cut 重排。纯文字模式无 bbox，只能依赖模型原生顺序。
- 云端模型返回纯文本，不提供逐行坐标；复杂多栏布局的阅读顺序主要依赖模型输出与分块顺序，Markdown 模式或本地 PP-OCR 才能使用几何信息重排。
- 强制切分（极密集、无空白行）会标记风险并增大重叠，但仍可能影响极端图片。
- 免费状态会变化；快照过期时系统会阻止调用，需要联网刷新并人工核实。
- 单进程运行；多 worker 会破坏请求账本/任务锁，详见部署说明。

## 隐私

点击“开始识别”前必须勾选云端上传授权。图片只在任务运行时发送到硅基流动；本地保留上传文件、缩略图、分块缓存和结果，可用 `OCR_DATA_DIR` 指定目录并定期清理。不要上传未获授权的隐私图片。

## 许可

内部项目代码；第三方模型与 API 受其各自服务条款约束。
