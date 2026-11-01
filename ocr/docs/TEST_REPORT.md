# 测试与验收报告

日期：2026-11-01  
环境：macOS，Python 3.13.2，FastAPI 0.162.0，httpx 0.28.1，Pillow 12.3.0，NumPy 2.5.4

交付状态：

- GitHub PR：[#8](https://github.com/Xike-yuhuofei/Soran/pull/8) 已 squash-merge 至 `main`（merge commit `39a8bca`）。
- PR CI：Python 3.11 与 3.13 两个矩阵均通过（Ruff、Bandit、构建、79 测试、覆盖率门槛）。
- `main` 合并后 OCR CI 再次通过。
- 未绕过分支保护、未强制合并；仓库 `main` 当时未启用分支保护，PR 为普通 squash merge。

## 1. 自动化测试

```bash
cd ocr
.venv/bin/ruff check .
.venv/bin/pytest
.venv/bin/pytest --cov=app --cov-report=term-missing
```

结果：

- `ruff check`：通过，0 错误。
- `pytest`：**91 passed，0 failed，1 warning**（FastAPI TestClient 的第三方弃用提示）。
- 覆盖率：**85.32%**（语句覆盖；`coverage` 明细见终端输出）。
- 默认测试使用 `httpx.MockTransport`，**不访问云端、不消耗额度**。

覆盖的关键行为：

| 类别 | 测试内容 |
|---|---|
| 免费策略 | 官方定价页解析、免费/付费/未注册模型、快照过期阻止、刷新失败保留新鲜快照 |
| 长图切分 | 空白行切分、120px 重叠与坐标、短图单块、密集图强制切分标记、分块缩放、墨迹比、长图缩略图高度限制 |
| 布局 | grounding bbox 解析、原图坐标映射、双栏 XY-cut 顺序、纯文本回退 |
| 合并去重 | 相邻前缀/后缀去重、物理无重叠不误删、中间分块失败时对最近成功分块去重、拼接块字符级重叠兜底、审计记录 |
| 文本还原 | grounding token 清理、Markdown→纯文本、HTML/管道表格→TSV、结构化 Markdown 保留 |
| 关键字段 | 品牌/品名/成分/尺码/型号/洗涤/标准/安全类别/价格/包装提取、百分比校验、多行字段合并、冲突标记 |
| 质量与复核 | 空块/墨迹不符、垃圾字符、重复噪声、模型不确定、数字/百分比冲突、相似度与冲突分离 |
| 云端客户端 | 成功请求体、base64 图片、429 重试、5xx 重试、超时重试、401/402 不重试、空响应拒绝、截断标记、缓存命中、策略阻止先于网络请求、无 Key 先于网络请求 |
| 额度 | 单任务/单日上限、缓存命中不计请求、账本持久化 |
| 流水线 | 完整任务、复核冲突保留主结果、部分失败保留已完成、策略阻止、授权阻止、无 Key 阻止、断点续跑、A/B/C/D 变体、编辑后导出、密钥不出现在结果 |
| API | 上传、会话、任务、轮询、结果、TXT/MD/JSON 导出、编辑、健康检查、策略、非法上传、超宽图片、文件数量、路径/ID 校验 |
| 本地 OCR | PaddleOCR v3/旧版结果解析、XY-cut 多栏/多行排序、禁用状态、PP-OCRv6 不支持时回退 |
| 数据集 | 图片扫描导入、追加保留已有标注、清单校验（缺失标注/坏图/重复 ID/未知类别/类别数量提醒） |
| 指标 | Levenshtein/CER、行召回、关键字段完全正确率、重复引入率、边界漏字率、P95 |

## 2. 真实 API 验证（免费模型）

### 2.1 模型与免费状态

通过 `GET https://api.siliconflow.cn/v1/models` 确认以下模型 ID 当前可用：

- `deepseek-ai/DeepSeek-OCR`
- `PaddlePaddle/PaddleOCR-VL-1.5`

通过官方定价页 `https://www.siliconflow.cn/pricing` 的运行时解析确认：

- `deepseek-ai/DeepSeek-OCR`：`price=0`、`inputPrice=0`、`pricing[].price=0`、`status=normal`，标签“限免”。
- `PaddlePaddle/PaddleOCR-VL-1.5`：页面“免费”，模型对象 `price=0`。

**注意：** “限免”不等于永久免费。系统把该状态固化为带时间戳的快照，超过 24 小时会阻止调用，必须重新联网校验。

### 2.2 原始模型调用（合成详情页）

| 调用 | 耗时 | 完成 tokens | 结果 |
|---|---:|---:|---|
| DeepSeek-OCR + `Free OCR.` | 1.75 s | 250 | 文字与字段全部读出；模型自行使用了部分 Markdown 排版，TXT 导出时剥离 |
| DeepSeek-OCR + `Convert the document to markdown.` | 4.01 s | 566 | 返回 grounding bbox token；系统清理标记，保留表格 HTML/文本 |
| PaddleOCR-VL-1.5 + 逐字转写提示词 | 40.14 s | 234 | 纯文本顺序正确；作为按需复核，不逐块全量调用 |

API 不返回 OCR 置信度（无 logprob），因此 JSON 中 `confidence` 为 `null`，UI 明确显示“未知”。

### 2.3 端到端合成冒烟

合成图：750×2000，包含标题、品牌、型号、面料成分、执行标准、安全类别、洗涤、尺码表、价格、提示。

- 状态：`completed`
- 分块：2 个（`0–1200px`、`1080–2000px`，重叠 120px）
- 实际云端请求：3 次（DeepSeek-OCR ×2 + PaddleOCR-VL 复核 ×1）
- 缓存命中：0（首次运行）
- 端到端耗时：5.465 s
- 重叠去重：移除 2 行，审计记录保留
- 需人工核验：`false`
- 关键字段：品牌、成分 `92%莫代尔 8%氨纶`、型号 `SR-M2001`、标准 `FZ/T 73020-2019`、安全类别 `GB 18401-B`、价格 `¥129.00` 全部提取
- 指标（**仅合成样本，不是验收精度**）：

| 指标 | 结果 |
|---|---:|
| CER | 0.00% |
| 行召回 | 100% |
| 关键字段完全正确率 | 100%（6/6） |
| 重复引入率 | 0.00% |

证据文件：[`docs/evidence/synthetic-smoke-2026-11-01.json`](evidence/synthetic-smoke-2026-11-01.json)。

该样本的 0% CER 只能证明工程链路与提示词/合并逻辑在清晰合成图上工作，不能代表真实淘宝/天猫/京东/拼多多/抖音详情页的普遍精度，也不能替代 200 张真实标注测试集。

### 2.4 Grounding 布局解析验证

真实调用 DeepSeek-OCR 的 Markdown/grounding 提示词，对同一合成图返回 1532 字符 grounding 响应：

- 解析出 **19 个布局块**（`title` / `text` / `table`），每个块保留标签、文本与 bbox。
- bbox 映射回原图坐标后，递归 XY-cut 输出顺序为标题 → 商品字段 → 面料/标准/洗涤 → 尺码表 → 颜色/包装/价格 → 提示。
- 布局块写入 JSON 的 `layout_blocks`，UI 分块审计中可展开查看。
- 实际耗时约 2.958 s，消费 1180 tokens，模型为已核实免费。

证据：[`docs/evidence/layout-smoke-2026-11-01.json`](evidence/layout-smoke-2026-11-01.json)。该验证证明 grounding bbox 链路可用，但合成图只有单栏；双栏 XY-cut 由单测覆盖。

### 2.5 浏览器界面验证

在本地启动 `uvicorn` 后，使用浏览器实际完成：

1. 打开首页，确认上传区、识别设置、免费策略已核实、密钥已配置、模型免费状态标签均正常，无阻塞性控制台错误。
2. 通过页面文件输入上传 750×2000 长图，页面显示 `1 / 12`、缩略图、尺寸与“长图”标记。
3. 勾选云端上传授权，关闭辅助复核（避免额外等待），点击“开始识别”。
4. 进度轮询到完成，结果区显示“已完成”、图片标签、251 字符正文、关键字段表（品牌/成分/型号/标准/安全类别/价格等）与分块审计。
5. 编辑正文并点击“保存编辑”，页面提示“编辑已保存”，后端 `PUT` 返回成功。
6. 页面提供“复制当前文本”、TXT / Markdown / JSON 下载按钮。

该次 UI 验证真实调用了 2 次 DeepSeek-OCR（2 个分块，关闭复核），全部为已核实免费模型，未产生付费模型请求。

## 3. 验收目标对照

| 验收目标 | 状态 |
|---|---|
| 上传普通图片 / 长图 | 已实现并通过 API 测试 |
| 调用 DeepSeek-OCR | 已实现并真实调用成功 |
| 长图自动切分与合并 | 已实现，合成样本 2 块合并成功 |
| 不因切图重复/遗漏文字 | 重叠去重有审计；真实 200 图边界漏字率尚待数据集验证 |
| PaddleOCR-VL 辅助复核 | 已实现并真实调用成功 |
| 复杂布局阅读顺序 | Markdown/grounding 解析 19 个真实 bbox 块并 XY-cut 重排；双栏顺序由单测覆盖 |
| 测试集导入/人工标注机制 | `tools/import_dataset.py` 扫描生成清单，`tools/validate_dataset.py` 校验缺标注/坏图/重复 ID；无编造数据 |
| 完整文字查看、编辑、导出 | 已实现并通过 API 测试 |
| 禁止意外付费请求 | 白名单 + 定价页校验 + 快照过期阻止 + 额度 + 无付费兜底；真实调用仅免费模型 |
| 完整测试报告与实际精度指标 | 本报告为工程测试；真实商品数据精度**未验证**，因仓库无标注数据 |
| 可复现部署说明 | 见 `docs/DEPLOYMENT.md` |
| GitHub Actions 适配 | 已新增 OCR CI；PR #8 与 `main` 推送均通过（Python 3.11 / 3.13） |
| PR 自动合并 | PR #8 在所有必要 CI 通过后自动 squash-merge 至 `main`，未绕过任何保护规则 |

## 4. 未验证/已知问题

1. **无真实标注集**：没有 50×4 类真实商品详情图及人工转写，无法计算并宣称“CER ≤1%”“关键字段 ≥99%”“长图边界无漏字”。已提供导入/标注/评测工具与清单格式。
2. **模型置信度缺失**：接口未返回，`confidence=null`。质量分与多模型一致性是独立指标，不能替代真实置信度。
3. **PaddleOCR-VL 延迟波动**：单次复核实测可达约 40 s，远高于 DeepSeek-OCR；已通过“按需复核 + 单任务复核上限 + 120 s 超时”控制。
4. **复杂多栏阅读顺序**：Markdown/grounding 模式可解析 bbox 并 XY-cut 重排；纯文字模式没有逐行坐标，只能依赖模型原生顺序。默认仍是纯文字模式，需要复杂布局时应选择 Markdown 模式或启用本地 PP-OCR。
5. **极密集图片**：无可用空白行时只能选择最少墨迹行并标记 `forced_cut`，无法数学保证绝不穿过字形；系统会加大重叠并提示人工核验。
6. **免费状态变化**：官方定价页字段/模型状态变化会导致阻止调用；这是有意设计（fail closed）。
7. **账单核实**：本次真实调用全部指向官方页面标记为免费的模型；未调用任何付费模型。但账户是否产生任何费用仍需以硅基流动控制台账单为准，应用无法代替云平台计费系统。
8. **单进程限制**：`uvicorn --workers >1` 会破坏额度账本与任务锁，部署文档已明确要求单 worker。

## 5. 复现命令

```bash
cd ocr
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/ruff check .
.venv/bin/pytest --cov=app --cov-report=term-missing

# 真实免费模型冒烟（手动，消耗免费额度）
SILICONFLOW_API_KEY=... .venv/bin/python tools/smoke_test.py --real

# 真实标注集评测（先按 datasets/README.md 标注）
SILICONFLOW_API_KEY=... .venv/bin/python tools/evaluate.py \
  --manifest datasets/manifest.json --variants B,C,D --real
```
