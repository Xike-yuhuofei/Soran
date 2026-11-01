# 部署与费用保护说明

## 1. 运行环境

- Python 3.11+（已在 Python 3.13.2 / macOS 验证）
- 依赖：FastAPI、uvicorn、httpx、Pillow、numpy、pydantic-settings
- 建议单机 2 GB 以上内存、10 GB 以上可用磁盘（长图与缓存会占用磁盘）
- 仅监听回环地址，默认 `127.0.0.1:8000`

```bash
cd ocr
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -e .
cp .env.example .env
chmod 600 .env
```

`.env` 至少包含：

```bash
SILICONFLOW_API_KEY=sk-...
OCR_DATA_DIR=./.data
```

启动：

```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**必须使用单 worker。** 请求账本与任务运行锁是进程内的；使用 `--workers 2` 会破坏额度与并发保护。若需要多实例，必须先把账本/锁迁移到外部数据库或分布式锁，并重新做安全评审。

## 2. 免费调用保护（强制）

### 2.1 应用层

1. 每次任务前抓取官方定价页 `https://www.siliconflow.cn/pricing`，按模型对象检查：
   - `price=0`
   - `inputPrice=0`
   - `pricing[].price` 全为 0
   - `status=normal`
   - `onlyByChargeBalance=false`
   - 未标记 deprecated
2. 校验结果写快照；快照超过 24 小时（可配置）即失效。
3. 刷新失败且快照过期 → 所有云端调用被阻止。
4. 模型不在注册表 → 拒绝。
5. 402 立即停止；不会切换任何付费模型。
6. 单任务/单日请求上限、并发上限、最小间隔、缓存。

### 2.2 云账户层（应用无法替代）

应用层保护**不能替代**硅基流动账户级计费保护。部署时必须同时完成：

1. 在硅基流动控制台关闭自动充值/自动续费。
2. 账户余额保持尽可能低，或使用独立测试账户。
3. 开启余额提醒/消费告警，并每天核对账单。
4. 定期查看官方定价页与模型页面；本系统的快照校验只能覆盖定价页可解析字段，不能覆盖平台规则变化。
5. 不要在生产使用共享主账号 Key；为 OCR 单独创建 Key，必要时定期轮换。
6. 不要把 Key 写入代码、镜像、前端、日志或 Git。仅使用环境变量/`.env`。

**结论性提醒：** 本系统不会主动调用非免费模型，也不能保证云平台定价永久不变。若必须“绝对零费用”，还需在云账户侧做计费隔离/限额，并定期人工核实。

## 3. 反向代理与网络

建议用 Nginx/Caddy 仅暴露给受信网络，并加认证：

```nginx
server {
  listen 127.0.0.1:8080;
  client_max_body_size 40m;
  proxy_read_timeout 300s;
  proxy_send_timeout 300s;
  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
  }
}
```

注意：

- 上传接口按单文件 30 MB（`OCR_MAX_UPLOAD_BYTES`）限制；代理需同步调整。
- 长图任务可能持续数十秒到数分钟；代理超时应大于 `OCR_REQUEST_TIMEOUT_SECONDS`。
- 不要直接暴露到公网：系统没有用户认证，任何访问者都可以上传图片并消耗请求额度。
- 若面向多人使用，应在外层增加认证、配额与审计，并修改“单进程账本”的假设。

## 4. 数据与隐私

- 上传图片、缩略图、分块缓存、任务结果保存在 `OCR_DATA_DIR`（默认 `ocr/.data`）。
- 云端上传只在用户勾选授权并提交识别任务后发生。
- `.data`、`.env`、缓存、评测报告均已被 `.gitignore` 忽略。
- 生产环境建议：
  - 单独磁盘目录，权限 `700`
  - 定期清理 `sessions/` 与 `jobs/` 旧数据
  - 不把 `.data` 放进云盘同步或备份到不受控位置
  - 对隐私图片使用本地 PP-OCR 模式（`OCR_LOCAL_OCR_ENABLED=true` 且不配置云端 Key），或不使用本工具

## 5. 缓存与额度

- 缓存键 = 分块图像字节 + 模型 ID + 提示词 + 模式 + 流水线版本。
- 相同图片/相同设置再次识别会命中缓存，不产生云端请求。
- 清空缓存：停止服务后删除 `OCR_DATA_DIR/cache/chunks`；会影响后续请求次数。
- 每日账本文件：`OCR_DATA_DIR/usage.json`，按 UTC 日期统计尝试次数/成功/失败。
- 修改额度后需重启服务。

## 6. 本地 PP-OCR（可选）

```bash
.venv/bin/pip install -e ".[local]"
```

```bash
OCR_LOCAL_OCR_ENABLED=true
OCR_LOCAL_OCR_MODEL=PP-OCRv5
```

- 本地模型首次运行可能需要下载模型文件，请在受控网络完成。
- 本地 OCR 只在可疑分块交叉验证或云端失败时兜底；不会改变云端白名单。
- 未安装/加载失败时自动跳过，不影响主流程。

## 7. 升级与回归

```bash
.venv/bin/ruff check .
.venv/bin/pytest -q
```

- CI 使用 Mock，不调用云端。
- 升级模型或提示词后，先跑 `tools/smoke_test.py --real`（手动，免费模型）确认可用。
- 精度变化必须用独立标注集跑 `tools/evaluate.py`，不能凭单张样例判断。

## 8. 故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 403 “免费策略快照缺失或已过期” | 无法联网刷新官方定价页 | 联网后点击“刷新校验”或 `GET /api/policy?refresh=true`；核对官方价格 |
| 403 “无法确认模型免费” | 定价页字段变化/模型下架/涨价 | 人工核实官方页面；不要绕过策略 |
| 401 鉴权失败 | Key 错误/失效 | 检查 `.env` 的 `SILICONFLOW_API_KEY` |
| 402 | 云平台计费拒绝 | 立即停止；不要充值后继续无评审调用 |
| 429 | 平台限流或应用日额度 | 查看 `usage.json`；降低并发/等待 |
| 任务 partial | 部分分块失败 | 查看 JSON 的 `chunk.error`；修复后点“继续未完成任务”，缓存会避免重复请求 |
| 长图强制切分 | 图片极密集无空白行 | 查看 `forced_cut` 与警告；对该图人工核验 |
| 本地 PP-OCR 不可用 | 未安装/模型下载失败 | 查看 `/api/health` 的 `local_ocr.error`；不影响云端主流程 |
