# Soran · 素然之境

素然之境（Soran）—— 多品类精选品牌，会员制精选电商模式。

## 项目说明

- 品牌定位：多品类精选选品，覆盖全年龄段人群
- 首发品类：内衣（女性纯棉、男士莫代尔）
- 供应链：支持多品类供应商与商品管理

## 目录结构

- `textbook/` — 贴身衣物专业学习教材（纯离线 HTML，双击即用）

## 本地使用教材

1. 打开 `textbook/index.html`（双击即可，支持 Mac / Windows 主流浏览器；也可用任意静态服务器托管）。
2. 正文、图表与自测无需网络：全部图形为内联 SVG，无外部字体 / CDN 依赖；登录后的云端同步需要联网，离线操作会留在本机并在恢复联网后补传。
3. 未登录时，学习进度、自测答题、清单勾选与评分自动保存在浏览器 localStorage 中（按浏览器与设备隔离，清除浏览器数据会重置进度）。
4. 登录后，上述学习进度与划线、下划线和笔记一并同步到 Supabase，并按账号隔离（数据库 RLS 强制）；离线仍可正常答题，恢复联网后自动补传，换设备或清理浏览器缓存后可恢复。
5. 搜索：左侧搜索框或按 `/` 键，可同时检索 170 条专业术语与全部章节内容。
6. 章节内容检索索引由 `textbook/tools/build-search-index.mjs` 生成；新增或修改章节页后，在该目录运行 `node tools/build-search-index.mjs` 重建。
7. 云端同步配置：在 Supabase 创建项目，运行 `supabase/schema.sql`（包含笔记表 `annotations` 与学习进度表 `learning_state`），再把 Project URL 与 Publishable key（新版界面，`sb_publishable_` 开头）或 anon public key（旧版界面）填入 `textbook/assets/js/supabase-config.js`；已有项目需重新运行一次脚本以创建新表；保活方式见 `supabase/schema.sql` 中的 heartbeat 说明。
8. 页面编写规范见 `textbook/AUTHORING.md`。
