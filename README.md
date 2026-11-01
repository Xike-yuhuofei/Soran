# Soran · 素然之境

## 品牌 Slogan（已冻结）

> **让好品质，触手可及**

2026-11-01 正式冻结。完整记录见 [品牌冻结决策](brand/decisions.md)。

素然之境（Soran）—— 多品类精选品牌，会员制精选电商模式。

## 项目说明

- 品牌定位：多品类精选选品，覆盖全年龄段人群
- 首发品类：内衣（女性纯棉、男士莫代尔）
- 供应链：支持多品类供应商与商品管理

## 目录结构

- `textbook/` — 贴身衣物专业学习教材（纯离线 HTML，双击即用）
- `ocr/` — 电商详情页长图 OCR 系统（FastAPI + 本地 Web 界面，免费模型白名单）

## 电商详情页 OCR

`ocr/` 是一套独立可运行的电商详情图 OCR 工具：支持普通图 / 超长图 / 多图排序，自动按空白带切分并去重合并，调用已核实免费的 DeepSeek-OCR 与 PaddleOCR-VL-1.5，按需复核，输出 TXT / Markdown / JSON，并支持人工编辑与断点续跑。

```bash
cd ocr
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -e ".[dev]"
cp .env.example .env   # 填入 SILICONFLOW_API_KEY
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 http://127.0.0.1:8000 。完整说明见 [`ocr/README.md`](ocr/README.md)，部署与费用保护见 [`ocr/docs/DEPLOYMENT.md`](ocr/docs/DEPLOYMENT.md)，测试报告见 [`ocr/docs/TEST_REPORT.md`](ocr/docs/TEST_REPORT.md)。

云端调用强制约束：只调用运行时核实为免费的模型；官方定价页快照过期或无法确认免费时阻止调用；不自动切换付费模型；应用层额度不能替代云账户计费保护。

## 本地使用教材

1. 打开 `textbook/index.html`（双击即可，支持 Mac / Windows 主流浏览器；也可用任意静态服务器托管）。
2. 正文、图表与自测无需网络：全部图形为内联 SVG，无外部字体 / CDN 依赖；登录后的云端同步需要联网，离线操作会留在本机并在恢复联网后补传。
3. 未登录时，学习进度、自测答题、清单勾选与评分自动保存在浏览器 localStorage 中（按浏览器与设备隔离，清除浏览器数据会重置进度）。
4. 登录后，上述学习进度与划线、下划线和笔记一并同步到 Supabase，并按账号隔离（数据库 RLS 强制）；离线仍可正常答题，恢复联网后自动补传，换设备或清理浏览器缓存后可恢复。
5. 搜索：左侧搜索框或按 `/` 键，可同时检索 170 条专业术语与全部章节内容。
6. 章节内容检索索引由 `textbook/tools/build-search-index.mjs` 生成；新增或修改章节页后，在该目录运行 `node tools/build-search-index.mjs` 重建。
7. 云端同步配置：在 Supabase 创建项目，运行 `supabase/schema.sql`（包含笔记表 `annotations` 与学习进度表 `learning_state`），再把 Project URL 与 Publishable key（新版界面，`sb_publishable_` 开头）或 anon public key（旧版界面）填入 `textbook/assets/js/supabase-config.js`；已有项目需重新运行一次脚本以创建新表；保活方式见 `supabase/schema.sql` 中的 heartbeat 说明。
8. 页面编写规范见 `textbook/AUTHORING.md`。
