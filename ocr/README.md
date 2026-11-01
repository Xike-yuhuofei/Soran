# Soran OCR · 电商详情页高精度文字提取

面向淘宝、天猫、京东、拼多多、抖音等商品详情图的长图 OCR 工具。重点解决“超长图整体缩放导致小字丢失、切图切断文字、重叠区重复、数字/成分/型号出错、模型编造内容”等问题。

**核心约束：云端只调用经运行时核实为免费的模型，绝不能自动产生付费请求。**

## 功能

- 多图上传、拖拽、顺序调整；PNG / JPEG / WebP、手机截图、超长详情图。
- 电商详情页专用切图：按投影空白带/文字行间切分，固定 120px 重叠，保留原图坐标；默认目标高度 1200px，可配置。
- DeepSeek-OCR 主识别（纯文字与 Markdown 两种官方提示词），分块并发、限流、超时、指数退避重试。
- PaddleOCR-VL-1.5 按需复核（默认关闭；开启后只对可疑分块、数字/百分比/型号/表格等关键内容调用）。
- 文本合并与重叠去重，去重记录可审计；TXT / Markdown / JSON 三种导出；结果可人工编辑。
- 复核文本可在 UI/API 中显式“采用复核文本”或“恢复主模型文本”，人工选择，不自动替换。
- Markdown/grounding 模式解析逐块 bbox，保存原图坐标并用递归 XY-cut 恢复复杂布局阅读顺序；本地 PP-OCR 使用文本框 XY-cut。
- 关键字段提取：品牌、品名、面料成分、尺码、型号/SKU、洗涤、执行标准、安全类别、价格、包装。
- 两级质量检查：空块/墨迹不符、垃圾字符、数字百分比冲突、重复噪声、强制切分、边界重叠区无共享文本、模型不确定标记、空白区域编造内容（墨迹比例极低却输出大段文字）；模型置信度、启发式质量分、多模型一致性分别记录，不混为一谈。
- 空白区域编造内容会保留原始结果供审计，但自动排除出合并文本，并标记人工核验；不会静默写入最终输出。
- 免费模型策略守卫：官方定价页运行时校验 + 快照过期即阻止；模型白名单；无付费兜底。
- 请求额度（单任务/单日）、并发、缓存、断点续跑；API 失败保留已完成结果。
- 可选本地 PP-OCRv5/v6 插件，只在启用后参与交叉验证或云端失败兜底。
- 本地 Web 界面，显式云端上传授权提示。

## 快速开始

```bash
cd ocr
./run.sh
```

首次运行会自动创建 `.venv` 和 `.env` 并提示填写 `SILICONFLOW_API_KEY`；再次运行即启动 http://127.0.0.1:8000 。

手动方式：

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
| `OCR_REVIEW_ENABLED` | `false` | 默认是否开启复核；UI/API 可显式开启。真实 8 样本评测未显示 CER 收益 |
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

### 识别模式选择

默认 `text`（`Free OCR.`）。15 条真实样本对比：

| 模式 | CER 均值 | 行召回 | 关键字段 | P95 延迟 | 观察 |
|---|---:|---:|---:|---:|---|
| `text` | **10.14%** | **89.35%** | 87.5% | 10.62s | 默认；复杂艺术字更稳 |
| `markdown` | 17.02% | 79.13% | 75% | 13.92s | 表格/色号网格更好，复杂图形更差 |

- 表格、参数列表、2×2 色号/卖点网格：优先选 `markdown`。本次评测中色号网格 CER 从 25% 降至 0%，多张表格降至 0%–4.9%。
- 复杂艺术字、图表营销图：保持 `text`。`markdown` 会把图形当作布局块，复杂样本 CER 反而升至 57%–94%。
- 系统不会自动切换模型或模式；模式由用户显式选择。

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

复核策略：默认关闭（真实 8 样本评测中复核未改善 CER，但显著增加延迟与人工核验标记）。开启后对质量异常（空块、墨迹不匹配、垃圾字符、数字冲突、表格列数错位、强制切分、模型标记不确定）+ 关键内容（百分比、型号、尺码、标准、面料、价格）+ 表格样文本按需调用 PaddleOCR-VL；复核结果**不会**被自动替换为主结果，冲突只标记待人工确认。复核/本地 OCR 还会报告 `possible_missing_text`（第二模型发现主模型缺失行）和 `primary_only_text`（主模型有、复核没有的行），便于追查漏识别或多识别。

## 输出

- `TXT`：NFKC 排版格式剥离后的纯文字，按阅读顺序，表格转为制表符分隔行。
- `Markdown`：保留模型输出的标题/列表/表格结构；纯文字模式按段落生成，不编造标题。
- `JSON`：图片编号、原图尺寸、分块坐标/缩放/重叠、文本、引擎、原始响应文本、布局块（label + 原图 bbox + 文本）、置信度、质量分、一致性、是否复核、复核文本、人工采用/恢复标记与原始主文本、冲突、是否需人工检查、错误、API 请求数、免费策略快照。

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

评测说明与标注格式见 [datasets/README.md](datasets/README.md)。仓库不提交真实商品图片；本地可从 `product-research/` 素材建立标注集。

### 真实样本评测（20 条，非验收规模）

使用仓库现有 SecretWorld 真实详情图，人工转写 20 条（table 7、normal 6、complex 6、long 1），禁用缓存并真实调用免费模型。B 智能分块方案结果：

| 指标 | 20 条结果 |
|---|---:|
| CER 均值 / 中位数 / P95 | 12.85% / 7.53% / 43.75% |
| 行召回均值 | 87.41% |
| 关键字段完全正确率 | 88.89%（8/9） |
| 重复引入率 | 1.79% |
| 边界漏字率 | 20%（仅 long） |
| P95 延迟 | 11.09s |
| 单图请求均值 | 1.70 |

关键结论：

- 长图 A 因整图缩小 CER 高达 601.4%，B 智能分块降至 16.19%，分块是必要模块。
- 清晰表格/价格样本 CER 可低至 0%–7.5%；新增长表样本 `984119970673-29` 为 0.48%，`984119970673-27` 为 10%（关键字段正确）。
- 空白区域编造检测：`1038464992282-13` 中模型在 `0.0016` 墨迹比的空白分块输出虚构表格，该块被排除，CER 从 66.67% 降至 0%。
- 图标占位行清理：`1045196975426-31` 的 `图标1/图标2...` 伪文本清理后，CER 从 14.72% 降至 0%。
- 重叠去重支持 Markdown 标题前缀：`功能` 与 `# 功能`、`免责声明` 与 `# 免责声明` 不再重复；`984119970673-29` CER 从 2.40% 降至 0.48%。
- 复杂艺术字仍是主要误差来源：`931047952787-13` 被模型额外编造“2017年 2018年 2019年”，CER 52.94%；`984119970673-25` 漏掉腰头刺绣 `SecretWorld/Red`，CER 43.75%。
- 关键字段 8/9 正确；`1070411333016-17` 把“尖硬物”识别成“尖锐物”，属于真实 OCR 错误。
- 8 条样本上的 A/B/C/D 对比显示 C/D 复核未改善 CER，却显著增加延迟与人工核验标记；因此 **Paddle 复核默认关闭**。
- 样本量 20，远低于建议 200；**不能**据此宣称 CER ≤1% 或关键字段 ≥99% 验收达成。

证据：[`docs/evidence/real-eval-20-2026-11-01.json`](docs/evidence/real-eval-20-2026-11-01.json) 与 [`.md`](docs/evidence/real-eval-20-2026-11-01.md)；8 条 A/B/C/D 对比见 [`docs/evidence/real-eval-2026-11-01.json`](docs/evidence/real-eval-2026-11-01.json)。完整测试结论见 [docs/TEST_REPORT.md](docs/TEST_REPORT.md)。

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
  tests/             110 个单元/集成测试
  tools/             真实冒烟、数据集导入/校验、评测
  datasets/          标注格式与测试集导入说明
  docs/              部署说明、测试报告、证据
  run.sh             一键创建环境并启动
```

## 已知限制

- 真实人工标注样本仅 20 条，远低于建议的 200 条；已给出实际指标，但无法据此宣称 CER ≤1%、关键字段 ≥99% 等验收目标。
- 复杂艺术字/刺绣文字仍可能漏识别或编造（实测额外输出“2017年 2018年 2019年”、漏掉 `SecretWorld/Red`）；系统会标记需人工核验，但启发式规则无法保证捕获所有此类错误。
- 空白区域编造内容按“墨迹比例 <0.003 且输出 ≥40 字”启发式检测并排除合并文本；不是所有编造形式都能被该规则捕获，最终仍需人工核验。
- 图标占位行（`图标`/`icon` + 编号）会从文本中清理，原始响应仍保存在 JSON 的 `raw_text`；非此模式的图标描述仍可能残留。
- 单分块内重复标签（如 `[ 要 ]/[ 不要 ]`）不会自动删除，因为无法证明原图不同位置没有真实重复；请在人工核验时处理。
- SiliconFlow 当前不返回 OCR 置信度，`confidence` 为 `null`；不要把它与启发式质量分混用。
- DeepSeek-OCR 的 `Free OCR.` 仍可能输出 Markdown 排版；系统对 TXT 做格式剥离，JSON 保留原始文本。
- Markdown 模式的 grounding 输出包含 bbox token；系统会解析并保存为原图坐标的 `layout_blocks`，用 XY-cut 重排。色号/卖点网格按“行优先”恢复，避免读成左栏全部再右栏。纯文字模式无 bbox，只能依赖模型原生顺序。
- Markdown 模式并非默认：15 条评测中整体 CER 高于 text（17.02% vs 10.14%），复杂艺术字样本明显变差；仅在表格/网格类页面建议手动切换。
- 云端模型返回纯文本，不提供逐行坐标；复杂多栏布局的阅读顺序主要依赖模型输出与分块顺序，Markdown 模式或本地 PP-OCR 才能使用几何信息重排。
- 强制切分（极密集、无空白行）会标记风险并增大重叠，但仍可能影响极端图片。
- 免费状态会变化；快照过期时系统会阻止调用，需要联网刷新并人工核实。
- 单进程运行；多 worker 会破坏请求账本/任务锁，详见部署说明。

## 隐私

点击“开始识别”前必须勾选云端上传授权。图片只在任务运行时发送到硅基流动；本地保留上传文件、缩略图、分块缓存和结果，可用 `OCR_DATA_DIR` 指定目录并定期清理。不要上传未获授权的隐私图片。

## 许可

内部项目代码；第三方模型与 API 受其各自服务条款约束。
