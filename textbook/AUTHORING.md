# Soran 教材 · 页面作者规范（AUTHORING）

所有章节页面必须遵循本规范，保证全站视觉、交互与维护一致性。
**先读样板页 `pages/guide.html`，再动笔。**样板页是最权威的参考实现。

## 0. 硬性约束

1. **禁止修改共享文件**：`assets/css/main.css`、`assets/js/app.js`、`assets/js/widgets.js`、`assets/js/glossary.js`、`index.html`。并行编写期间这些文件是冻结的。需要新增术语或样式变体时，写入你的交付报告，由主编统一合并。
2. **纯离线**：禁止引用任何外部 URL（字体/CDN/图片）。所有图形用内联 SVG 手绘，禁止位图。
3. **纯原生 JS**：页面专属交互写在页面底部 `<script>` 中，入口统一挂到 `window.__SORAN_PAGE_INIT__ = function(){...}`（widgets.js 会自动调用，无需自己监听 DOMContentLoaded）。
4. 依赖只允许：`main.css`、`glossary.js`、`search-index.js`、`widgets.js`、`app.js`、`window.W`（widgets API）。

## 1. 页面骨架（必须完整照抄结构）

路径层级决定 `data-root` 与资源相对路径：

- `pages/guide.html` → `data-root="../"`，资源 `../assets/...`
- `pages/basics/xxx.html`、`pages/panties/...`、`pages/socks/...`、`pages/bras/...`、`pages/sourcing/...`、`pages/appendix/...` → `data-root="../../"`，资源 `../../assets/...`

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{页标题} — 素然之境 Soran</title>
<link rel="stylesheet" href="{root}assets/css/main.css">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%233D6B57'/%3E%3Ctext x='16' y='22' font-size='16' text-anchor='middle' fill='white' font-family='serif'%3E素%3C/text%3E%3C/svg%3E">
</head>
<body data-page-id="{pageId}" data-root="{root}">
<div class="layout">
  <aside class="sidebar" id="sidebar"></aside>
  <div class="main">
    <div class="topbar">
      <button class="menu-btn" aria-label="菜单">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M4 7h16M4 12h16M4 17h16"/></svg>
      </button>
      <div class="crumb"><b>{面包屑：篇章名 · 页短标题}</b></div>
      <div class="spacer"></div>
      <div class="read-meter"><i id="read-fill"></i></div><span class="read-pct" id="read-pct"></span>
    </div>

    <div class="content">
      <header class="page-head">
        <div class="page-kicker">{篇章英文 kicker，如 BASICS · FIBERS}</div>
        <h1 class="page-title">{页标题}</h1>
        <p class="page-lede">{150-200字导语：本页解决什么问题、读完能做什么}</p>
        <div class="page-meta">
          <span class="chip">阅读时间 约 N 分钟</span>
          <span class="chip">前置：{前置页面短名，无则写「无」}</span>
        </div>
      </header>

      <div id="page-toc" style="background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px 20px;margin-bottom:10px"></div>

      <!-- 章节内容，全部小节用 h2.sec-title + data-sec -->

    </div>
  </div>
</div>

<script src="{root}assets/js/glossary.js"></script>
<script src="{root}assets/js/search-index.js"></script>
<script src="{root}assets/js/widgets.js"></script>
<script src="{root}assets/js/app.js"></script>
<script>
/* 页面专属交互 */
window.__SORAN_PAGE_INIT__ = function () {
  // ...
};
</script>
</body>
</html>
```

## 2. 小节与目录

- 每个主要小节：`<h2 class="sec-title" id="s-{slug}" data-sec="s-{slug}"><span class="sec-no">0N</span>{标题}</h2>`，N 按顺序 01、02…。`data-sec` 是阅读进度单位，**每页 6-10 个为宜**。
- 二级标题 `<h3 class="sub-title">`，三级 `<h4 class="mini-title">`。
- 每页正文量：6000-11000 字 + 6-12 个图/交互组件。宁可深度足、页数多，不要塞成一页的百科堆砌。

## 3. 内容风格（教材灵魂，务必遵守）

1. **零基础友好**：每个专业概念先用一句生活化类比或场景引入，再给严格定义。例：「旦尼尔就像‘每 9000 米有多重’——数字越大，纱越粗，就像面条越粗。」
2. **四问结构**：讲一个材料/工艺时尽量覆盖：是什么 → 为什么用它（解决什么问题）→ 与替代方案比优劣 → 对成本/品质意味着什么。
3. **主理人视角**：每页至少 1-2 个 `callout owner`（选品与决策含义）、至少 1 个 `callout warn`（常见误区/营销噱头）。
4. **数据诚实**：示例数据必须写明「示例」「约」「教学参考」等字样；标准限值等有出处的数据注明标准编号。禁止编造「实测数据」。价格区间标注为出厂价参考区间并加「（示例）」。
5. **对比优先**：能用表格对比的不要用段落；重要二选一用 `duo` 组件。
6. **术语标注**：首次出现的重点术语用 `<dfn class="term" data-term="术语名">显示文字</dfn>`。**data-term 必须与 glossary.js 中的键完全一致**；共享词库没有的术语直接写普通 `<b>` 并在报告中列出待补词条（含 en/cat/def），不要自己改 glossary.js。每页术语标注 5-15 个为宜，不要滥用。
7. 每页收尾必须有 1 个「本页小结」小节（kv 或 plain list 形式）+ 2-4 道自测题。

## 4. 组件用法速查（类名必须精确）

### 提示框
```html
<div class="callout owner"> <div class="co-head">…svg…主理人视角</div> <p>…</p> </div>
<!-- 变体：owner(绿)/warn(陶土·误区)/info(蓝·延伸)/deep(金·深入理解可跳过)/data(灰·数据表) -->
```
co-head 内 svg 统一：owner 用星形、warn 用三角警示、info 用圆圈i、deep 用灯泡、data 用网格。直接从样板页复制。

### 图卡（SVG 图解）
```html
<figure class="fig">
  <div class="fig-canvas">
    <svg viewBox="0 0 760 H" xmlns="http://www.w3.org/2000/svg" font-family="PingFang SC, Microsoft YaHei, sans-serif">…</svg>
  </div>
  <figcaption class="fig-cap"><span class="fig-no">图 N-M</span><b>标题。</b>说明文字。</figcaption>
</figure>
```
- viewBox 宽统一 760，高按内容 260-560。文字最小 11px，中文标签注意留白。
- 图号规则：N=篇章号（guide 0 / basics 1 / panties 2 / socks 3 / bras 4 / sourcing 5 / appendix A），M=本页序号。
- SVG 配色只用 CSS 变量同源的色值：主绿 #3D6B57、深绿 #2C5142、浅绿底 #EAF1ED、陶土 #B0603F、浅陶 #F7EAE2、金 #B98F45、浅金 #F6EFDF、蓝 #44657F、浅蓝 #E9EFF3、墨 #26231D、灰 #5D574B、线 #E6E0D3、纸 #FAF8F3。禁止艳红大紫渐变。
- 需要动画的 SVG 用 CSS `@keyframes`（写在页面 `<style>` 里，允许）或 JS 驱动，注意低性能设备流畅度；`prefers-reduced-motion` 由框架全局处理。

### 表格
```html
<div class="tbl-wrap"><table class="tbl">
<caption>示例数据，用于教学参考</caption>
<thead><tr><th>…</th></tr></thead><tbody><tr><td class="num">…</td></tr></tbody>
</table></div>
```
数字列加 `class="num"`。

### 自测题（每题独立 data-quiz，全站唯一）
```html
<section class="quiz" data-quiz="{pageId}-q1"
  data-level="L3" data-kp="kp-id1 kp-id2"
  data-q="题干（可含提问场景）" data-a="2" data-exp="解析：为什么对、为什么其他错。">
  <div class="quiz-body"><div class="quiz-opts">
    <li>选项一</li><li>选项二</li><li>选项三</li><li>选项四</li>
  </div></div>
</section>
```
- `data-a` 为正确选项序号（0 起）。选项 3-5 个。题干侧重判断/决策/对比，不出纯记忆题。解析必须解释错误选项。
- `data-level`（L1 识记 / L2 理解 / L3 分析 / L4 应用 / L5 综合决策）与 `data-kp`（空格分隔的知识点 id）为**必填**，缺省会导致章末覆盖面板失真。
- `data-kp` 可引用其他页面的知识点 id 做跨知识点综合题（如 `sd-blend`）；章末面板只统计本页 KMAP 登记的知识点，跨页引用不会误报。

### 术语、键值表、对比栏
```html
<dfn class="term" data-term="包覆纱">包覆纱</dfn>
<div class="kv"><div class="kv-row"><div class="kv-k">关键词</div><div class="kv-v">解释</div></div></div>
<div class="duo"><div class="d-cell d-good"><h5><span class="d-ico">A</span>标题</h5><ul><li>…</li></ul></div><div class="d-cell d-bad">…</div></div>
```

## 5. 交互组件（widgets.js，直接用）

### 标签页
```html
<div class="wg"><div class="wg-panel" data-tabs>
  <div class="tabs"><button class="tab active" data-tab="t1">标签一</button><button class="tab" data-tab="t2">标签二</button></div>
  <div class="wg-body">
    <div class="tab-pane active" id="t1">…</div>
    <div class="tab-pane" id="t2">…</div>
  </div>
</div></div>
```
同一页内 pane id 必须全局唯一（建议 t1/t2… 或语义 id）。

### 折叠面板
```html
<div class="acc"><div class="acc-head">标题<span class="acc-arrow">▶</span></div><div class="acc-body">…</div></div>
```

### 滑杆（页面脚本用 W.slider）
```js
var s = W.slider({min:0,max:100,step:1,value:40,fmt:function(v){return v+' G';},onInput:function(v){ /* 更新SVG */ }});
ctlRow.appendChild(s.input); ctlRow.appendChild(s.val);
// ctlRow: <div class="ctl-row"><label>机号</label></div>
```

### 计算器数值卡
```html
<div class="calc-grid"><div class="calc-card acc-g"><div class="cc-l">出厂价</div><div class="cc-v"><span id="x">0.00</span><small>元/件</small></div></div>…</div>
```
acc-g 绿 / acc-c 陶土 / acc-gold 金 / acc-b 蓝。输入用 `<input class="num-input" type="number">`。

### 可持久化清单（工厂考察等）
```html
<div data-checklist="unique-list-id">
  <div class="chk-group">资质类<span class="cg-line"></span><span class="cg-n"></span></div>
  <label class="chk"><input type="checkbox"><span class="box"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.4"><path d="M4 12.5l5.5 5.5L20 6.5"/></svg></span>
    <span class="chk-t">条目文字<span class="chk-d">补充说明（为什么查这项、怎么判断）</span></span></label>
  …
  <div style="display:flex;align-items:center;gap:10px;margin-top:14px">
    <div style="flex:1;height:5px;background:var(--surface-2);border-radius:3px;overflow:hidden"><div data-chk-bar style="height:100%;width:0;background:var(--green)"></div></div>
    <span data-chk-sum style="font-size:12.5px;color:var(--ink-faint)"></span>
    <button class="btn ghost sm" data-chk-reset>重置</button>
  </div>
</div>
```

### 评分表（样品评价等）
```html
<div data-rate="unique-rate-id">
  <div class="rate-gate-head">第一部分 · 合规红线（一票否决 · 不计入质量分）</div>
  <div class="rate-row" data-key="gate-x" data-weight="0" data-gate="1" data-gate-min="4"><span class="rr-label">红线项说明</span></div>
  <div class="rate-gate-head">第二部分 · 可权衡品质（加权计分）</div>
  <div class="rate-row" data-key="fabric" data-weight="2"><span class="rr-label">面料手感</span></div>
  <!-- dots/sum 由 JS 生成 -->
  <div style="display:flex;align-items:center;gap:10px;margin-top:14px">
    <div style="flex:1;height:5px;background:var(--surface-2);border-radius:3px;overflow:hidden"><div data-rate-bar style="height:100%;width:0;background:var(--gold)"></div></div>
    <span data-rate-sum style="font-size:13px;font-weight:650"></span>
    <button class="btn ghost sm" data-rate-reset>重置</button>
  </div>
</div>
```
- **红线行（合规门）**：`data-gate="1"` 的行不计入加权总分；达到 `data-gate-min`（默认 4）显示「通过」，否则显示「未通过」并使整表结论无效。用于安全合规类不可妥协项，**不允许被其他高分项抵消**。
- 普通行按 `data-weight` 加权；页面脚本自行读取 localStorage 的 `rate[id]` 计算结论（红线行 `gate`/`gmin` 逻辑见 sourcing/judgment.html 样例）。

### SVG 热点图（结构拆解）
```html
<div data-hotroot>
  <svg>…<g class="svg-hot" data-tip="鸡心|两罩杯之间的连接部件，宽度影响稳定性与聚拢感。">…</g>…</svg>
  <div class="wg-note" data-hotout>点击图中编号查看结构说明</div>
</div>
```
热点元素要画一个编号圆圈 + 高亮描边（class="hot-ring" 的元素随 .on 显示，配合 CSS `.svg-hot:hover`）。热点 4-10 个为宜。

## 6. 页面脚本规约

- 全部放在 `window.__SORAN_PAGE_INIT__` 内；DOM 查询用 id/类选择器；禁止全局变量污染（用 IIFE 局部变量）。
- SVG 动画用 `requestAnimationFrame` + `cancelAnimationFrame`，页面不可见时无影响；单个动画节点数 <300。
- 数字滚动用 `W.count(node, to, {dec:2, suf:' 元'})`。
- 一切用户输入默认 `parseFloat` 后校验 NaN。

## 7. 篇章号与页 id 对照（写图号、data-quiz 前缀用）

| pageId | 篇章号 | 文件 |
|---|---|---|
| guide | 0 | pages/guide.html |
| basics-fundamentals / -fibers / -fabrics / -quality / -supply | 1 | pages/basics/*.html |
| panties-design / panties-craft | 2 | pages/panties/*.html |
| socks-design / socks-craft | 3 | pages/socks/*.html |
| bras-design / bras-materials / bras-craft | 4 | pages/bras/*.html |
| sourcing-judgment / sourcing-supplier | 5 | pages/sourcing/*.html |
| appendix-glossary / appendix-standards | A | pages/appendix/*.html |

## 8. 交付自查（提交前逐项确认）

1. 骨架与 data-root 正确；head/body 结构与样板一致。
2. 所有 `data-term` 均存在于 glossary.js。
3. 所有图 SVG 在窄屏（<560px）不溢出（viewBox 缩放天然安全，但要检查文字密度）。
4. quiz data-quiz 全站唯一（用 pageId 前缀）、data-a 正确、解析完整、data-level/data-kp 已标注。
5. 示例数据均标注；标准引用写编号+名称。
6. 每页 ≥1 owner callout、≥1 warn callout、1 个小结；自测题量按知识密度定（一般 8-14 题/页），核心知识点必须挂题。
7. 用浏览器打开过自己写的页面（http 任意端口），无 console 报错、交互可用。

## 9. 知识点地图与覆盖面板维护规范

章末「知识点覆盖面板」的数据源是 [assets/js/knowledge-map.js](assets/js/knowledge-map.js)（`window.SORAN_KMAP`）。改题、加题、改章节时同步维护：

### 9.1 数据结构
```js
'page-id': {
  points: [
    { id: '前缀-缩写', name: '知识点名（≤22字，括注关键参数）', core: true, level: 'L3' }
  ]
}
```
- `id` 全站唯一，用页面缩写前缀（如 `pd-` 内裤设计、`sd-` 袜子设计、`bc-` 文胸工艺）。
- `core: true` 的知识点**必须**有题目挂接，否则面板显示「⚠ 覆盖缺口」。
- `level` 是该知识点的目标认知层次，出题应至少达到该层次。

### 9.2 出题与挂接规则
1. 题量由知识密度决定，不设上限也不凑数；核心知识点可从多角度出多题（场景/计算/决策），避免同一题型机械重复。
2. 每题 `data-level` + `data-kp` 必填；跨知识点综合题允许引用他页 KP id（如 `data-kp="sc-reinforce sd-blend"`）。
3. 新增知识点：先在正文确认有对应内容，再登记 KMAP，最后出题挂接——三点缺一即出现「有图无题」或「有题无图」。
4. guide 页不渲染覆盖面板（app.js 显式排除），其 KP 仅用于全站统计；非知识页（导学/工具页）的核心点可标 `core: false`。

### 9.3 校验（提交前跑一遍）
用 node 校验脚本核对：quiz id 无重复、data-level/data-kp 无缺失、data-kp 均已登记、core 点无覆盖缺口、HTML 闭合完整。改动后必须打开对应页面确认：层级徽标渲染、覆盖面板无「⚠ 覆盖缺口」误报。

### 9.4 案例小节与小结编号
带「完整案例」小节的页面，案例插在判断清单/验货要点之前、小结之前；插入后需顺延后续 `<span class="sec-no">` 编号，并确认 page-toc 自动收录。案例必须包含：需求翻译 → 技术方案 → 打样验证 → 成本核算 → 验收标准五步 + 至少一次「方案取舍」+ 一条「品质异常归因练习」，并挂一道 L5 复盘决策题。
