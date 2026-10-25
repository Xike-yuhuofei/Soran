# SORAN HTML 教材严谨性审计报告

- 审计日期：2026-10-25
- 审计范围：`textbook/` 全部 17 个内容页 + `index.html`、193 道自测题、74 张表格、204 个知识点、1403 条 SVG 文本
- 审计方式：静态结构校验 + 数据元素清单 + 跨页主题对照 + 逐题语义审读 + HTML 解析器验证 + 关键标准外部核对
- 本阶段只出报告，不修改教材文件。机器可读清单见 [issues.jsonl](computer:///Volumes/Extreme%20SSD/Projects/Soran/audit/issues.jsonl)。

## 0. 结论摘要

教材的架构、组件体系、知识点覆盖和绝大多数专业内容是可用的；真正的问题集中在三处：

1. **数值与口径跨页不一致**：同一主题在不同页面各写一套数，且没有标注“可适配区间 / 标称区间 / 含弹力跨度”等口径。
2. **题目解析与选项指代错位**：答案键大多正确，但解析里的 A/B/C/D 经常指向错误选项，甚至引用已经不存在的旧选项。
3. **HTML 属性与表格结构不严谨**：3 道题的题干/解析被裸双引号截断；3 张表的 `<caption>` 用 `</td>` 闭合；30 张表把 caption 放在 tbody 之后。

共记录 **50** 个问题：**P0 9 个、P1 23 个、P2 13 个、P3 5 个**。截至 2026-10-25，**全部 50 个问题已修复**，并通过结构扫描、HTML 解析器与全站 202 题浏览器回归。其中 Q8 不是孤例，而是“题干前提、解析、同页表格、跨页表格”四层没有对齐的典型样本。

### 修复总状态（2026-10-25）

| 批次 | 范围 | 关闭数 |
|---|---|---|
| Batch A | P0-002~008、P1-015~018、P3-001~003 | 14 |
| Batch B | P0-001、P0-009、P1-001~013、P2-009/011/012/013 | 19 |
| Batch C | P1-014/019/020/023、P2-001~008/010、P3-004/005 | 15 |
| Batch D | P1-021、P1-022 | 2 |
| **合计** |  | **50** |

关键修复：A 类 pH 四处改为 4.0-7.5；3 道 socks/design 题属性转义；Q8 题干与解析重写；guide-2 答案键改为 C；13 处解析字母重写；内裤/袜码/量价/零售倍率/净利率口径统一；9 个核心 KP 补目标层级题；答案分布从 A70/B86/C34/D3 调整为 A60/B62/C50/D30（202 题）。

---

## 1. 审计方法与基线

### 1.1 机械校验（已执行）

| 检查项 | 结果 |
|---|---|
| 页面数 | 17 个内容页 + index，共 18 个 HTML |
| 自测题 | 202 道，全部 4 个选项 |
| data-quiz 唯一性 | 0 重复 |
| data-level / data-kp 缺失 | 0 |
| data-kp 未登记 | 0 |
| core 知识点覆盖缺口 | 0（按“有题挂接”口径） |
| core 知识点目标层级缺口 | 0（每个核心 KP 至少一题达到目标层级） |
| 知识点总数 | 204 个唯一 id |
| data-term 术语缺失 | 0 |
| 重复 DOM id | 0 |
| 搜索索引页面/锚点覆盖 | 17/17 页、全部小节锚点覆盖 |
| 内部链接 | 0 失效 |
| HTML 标签闭合 | 0 错误 |
| 表格 caption | 74/74 张表有 caption，且均为 table 首个子元素 |
| 表格合计校验 | panties / socks / supply 的 BOM 合计全部正确；AQL 表数值正确 |
| 计算器默认值与公式 | supply、bras design、bras materials、bras craft、fabrics gauge 均与正文公式一致 |
| 答案分布 | A 60 / B 62 / C 50 / D 30（202 题；A29.7% / B30.7% / C24.8% / D14.9%） |

### 1.2 外部标准核对（抽检）

已核对并通过：

- GB 18401-2010 甲醛、色牢度、异味、芳香胺限值；**A 类 pH 错误，见 P0-002~005**
- FZ/T 73024-2014 已于 2024-08-09 废止，由 GB/T 8878-2023《针织内衣》整合覆盖
- FZ/T 73012-2025《文胸》2028-01-01 实施
- FZ/T 74002-2025《运动文胸》2027-05-01 实施

未逐条外部核对的：其余方法标准、认证规则、行业价格/产能数据。它们大多已标注“示例/教学参考”，本报告不把“示例值本身”当错误，只把“示例值互相冲突”或“示例值被当作标准值”当问题。

---

## 2. P0：会直接误导读者，必须优先修

### 2.1 Q8 题干前提不成立，解析重复错误（P0-001）

- 位置：[fundamentals.html 522 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/basics/fundamentals.html#L522-L531)
- 题干：“S/M/L 各档的腰围区间比臀围区间更宽（如 M：腰 64-72、臀 88-96）。”
- 同页表格：[fundamentals.html 335-343 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/basics/fundamentals.html#L335-L343)

| 尺码 | 腰围跨度 | 臀围跨度 | 是否“更宽” |
|---|---|---|---|
| S | 58–66 = 8cm | 82–90 = 8cm | 相等 |
| M | 64–72 = 8cm | 88–96 = 8cm | 相等 |
| L | 70–80 = 10cm | 93–102 = 9cm | 仅宽 1cm |
| XL | 76–86 = 10cm | 98–108 = 10cm | 相等 |

问题有三层：

1. **事实层**：四档中三档相等，题干举的 M 恰好是两个 8cm，“更宽”不成立。只有换算成相对跨度才成立（8/68≈11.8% vs 8/92≈8.7%），但题干没有写“相对”。
2. **逻辑层**：“腰围区间更宽”推不出“尺码锚定臀围”。即使腰围区间更窄，尺码照样可以锚臀围；论据与结论脱节。
3. **解析层**：解析 C 写“区间窄是因为它是硬约束”，再次暗示臀围区间更窄，与表格不符；且“硬约束”与“区间窄”没有必然因果关系。

建议改法（保留答案 A）：

> 内裤尺码表按臀围分档，腰围只给一个可被弹力腰头消化的参考区间（如 M：腰 64–72、臀 88–96）。这背后的版型逻辑是？

或者保留比较但写清“相对跨度更大”。同步删除解析 C 的“区间窄”断言。

> 关联问题：P2-009（男款锚点的绝对化表述）、P2-013（“硬约束→区间窄”的因果错误）。

### 2.2 GB 18401 A 类 pH 写错，共 4 处（P0-002 / P0-003 / P0-004 / P0-005）

| 位置 | 原文 | 应改为 |
|---|---|---|
| [appendix/standards.html 102 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/appendix/standards.html#L102) 表（P0-002） | A 类 4.0-8.5 | **4.0-7.5** |
| [basics/quality.html 102 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/basics/quality.html#L102) 表（P0-003） | A 类 4.0-8.5 | **4.0-7.5** |
| [basics/quality.html 72 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/basics/quality.html#L72) 图（P0-004） | “A / B 类：4.0 - 8.5” | 拆成 A 4.0-7.5、B 4.0-8.5 |
| [basics/quality.html 554 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/basics/quality.html#L554) 解析（P0-005） | “A 类……pH 4.0-8.5” | **4.0-7.5** |

正确值：GB 18401-2010 表 1 —— **A 类 4.0-7.5；B 类 4.0-8.5；C 类 4.0-9.0**。官方标准 PDF 前言明确“B 类的 pH 值由 4.0~7.5 修改为 4.0~8.5”，A 类维持 4.0~7.5。

同页 q6 的解析已经写对“B 类 pH 4.0-8.5”，所以这是同页自相矛盾，不是版本差异。四处必须一起改，否则学员会在表格、图和解析之间来回打架。

### 2.3 3 道题的题干/解析被裸双引号截断（P0-006 / P0-007 / P0-008）

| 题目 | 位置 | 被截断的属性 | 用户看到的结果 |
|---|---|---|---|
| socks-design-q7（P0-006） | [socks/design.html 556 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/socks/design.html#L556) | data-exp 在 `3.5"` 处截断 | 解析只剩前半段，后续变成非法属性 |
| socks-design-q9（P0-007） | [socks/design.html 578 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/socks/design.html#L578) | data-exp 在 `3.5"` 处截断 | 解析只剩“筒径决定可织尺码范围：3.5” |
| socks-design-q13（P0-008） | [socks/design.html 622 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/socks/design.html#L622) | data-q 和 data-exp 都在 `3.5"` 处截断 | 题干不完整，解析也不完整 |

证据：Python HTMLParser 解析 q7 时，`data-exp` 的值止于“3.5”，随后出现 `3.75"`、`4.5"` 等无值属性；app.js 用 `getAttribute('data-exp')` 读取，必然拿到截断值。这不是“显示样式”问题，而是内容真的丢了。

修法：把属性内的英寸符号统一改为 `&quot;` 或中文“英寸”（推荐后者，和全书中文表述一致），然后全站扫描 `data-*` 属性中的裸双引号。修复后再用解析器确认 `data-q` / `data-exp` 完整闭合。

### 2.4 guide-2 答案键与解析冲突

- 位置：[guide.html 266 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/guide.html#L266)
- 题干：“价格差异最不可能是以下哪个原因？”
- 答案键：`data-a="3"`（D）
- 解析：通篇论证“针数高低对成本影响有限”，即 C 最不可能；完全没有解释 D 为什么不可能。

这不是措辞问题，而是答案键与解析指向两个不同选项。建议：

- 若本意是 C：`data-a` 改为 2，补一句“D 进口氨纶确实可能推高报价，不属于‘不可能’”。
- 若本意是 D：重写解析，说明“进口氨纶即使贵数倍，在 5% 含量下也难以造成 60% 差价”。

我建议采用前者，因为解析的论证已经完整支持 C。

---

## 3. P1：会明显降低可信度或让学员学错

### 3.1 解析字母指代错位（13 处）

答案键大多正确，但解析把“某个选项的内容”标成了另一个字母。学员按解析复习时，会把正确项当成错误项。

| ID | 位置 | 解析错标 | 实际应对应 |
|---|---|---|---|
| P1-001 | appendix-standards-q1 | “C 男士背心” | 选项 B 是男士背心；C 是正确答案女士文胸 |
| P1-002 | appendix-standards-q10 | “B 去掉年份” | 选项 C 是去掉年份；B 是正确答案“立即更新版本” |
| P1-003 | bras-craft-q11 | “A 整批返工” | 选项 B 是车缝返工；A 是正确答案“版型问题” |
| P1-004 | panties-design-q10 | “C 消费者说不清” | 选项 D 是“消费者看不出版型”；C 是正确答案“男女版型不可互改” |
| P1-005 | fundamentals-q12 | “B 静电吸附” | 选项 C 是静电；B 是正确答案“纤维端机械刺激” |
| P1-006 | fabrics-q4 | “B 梭织没有线圈” | 选项 D 才是“针织比梭织紧密”；B 是“棉纱本身有弹性” |
| P1-007 | fabrics-q9 | “A 预缩不足” | 选项 A 原文是“预缩做得太足”，两者相反 |
| P1-008 | fabrics-q11 | “D 拒绝一切抗菌宣称” | 选项 C 才是“抗菌与内裤无关”；D 是“有银字就采信” |
| P1-009 | bras-craft-q3 | “A 车缝路线”“B 模杯芯材” | A 是模杯款、B 是车缝款，A/B 完全互换 |
| P1-010 | panties-design-q7 | “B 一片式最省” | 选项 A 是一片式；B 是正确答案立体囊袋 |
| P1-011 | panties-design-q11 | “C 数量多≠覆盖广”“D 中间方案” | “数量多”回应 B；“中间方案”是 C |
| P1-012 | socks-craft-q2 | “C 包装”“D 全盘换橡筋” | 现有选项没有包装/换橡筋，属于旧题解析残留 |
| P1-013 | socks-craft-q5 | “B 缝头在染色前完成，不受染整影响” | 流程是“缝头→染色”，缝头恰恰会经历染整，逻辑相反 |

修法：逐题对照选项重写解析标签，而不是只改字母。P1-012、P1-013 需要重写解析，因为现有句子不对应任何选项或与流程事实矛盾。

### 3.2 其余 P1

| ID | 位置 | 问题 | 建议 |
|---|---|---|---|
| P1-014 | [supplier.html 750 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/sourcing/supplier.html#L750) | 付款比例 30%+70%+10~20% = 110~120%，超过 100% | 改为“定金 30% + 出货前付至 70-90% + 留 10-20% 验货后付” |
| P1-015 | [guide.html 250 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/guide.html#L250) | `href="fundamentals.html"` 指向不存在的 pages/fundamentals.html | 改为 `basics/fundamentals.html` |
| P1-016 | [standards.html 215 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/appendix/standards.html#L215) | `<caption>` 用 `</td>` 闭合 | 改为 `</caption>` 并前移 |
| P1-017 | [standards.html 235 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/appendix/standards.html#L235) | 同上 | 同上 |
| P1-018 | [standards.html 249 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/appendix/standards.html#L249) | 同上 | 同上 |
| P1-019 | [fundamentals.html 335 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/basics/fundamentals.html#L335) vs [panties/design.html 493 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/panties/design.html#L493) | 两张女式内裤尺码表区间不同（M 腰 64-72 vs 67-71，臀 88-96 vs 89-93），且都称“教学参考” | 已标注“可适配区间（含弹力）”与“标称参考区间”，并补互见说明 |
| P1-020 | [supply.html 504 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/basics/supply.html#L504) vs [supplier.html 633 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/sourcing/supplier.html#L633) | 量价曲线冲突：supply 的 300→1000 为 -17.6%、1000→5000 为 -17.9%；supplier 表却写 -8~-15% 与 -5~-10%；q7 又写 3000 件 -3~-6% | 已统一为 -12~-18% / -10~-18% / -3~-8%，q7 改为 -10~-18% |
| P1-021 | [knowledge-map.js 49 行起](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/assets/js/knowledge-map.js#L49) | 9 个核心知识点只有低于目标层级的题；另有 24 道题低于所挂 KP 目标层级 | 已补 9 道 L2/L4 题；当前 core 目标层级缺口 0 |
| P1-022 | 全部 202 题 | 答案分布 A70 / B86 / C34 / D3；D 仅 1.6% | 已重排 34 题选项，当前 A60 / B62 / C50 / D30（A29.7% / B30.7% / C24.8% / D14.9%） |
| P1-023 | [socks/design.html 429 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/socks/design.html#L429) vs [fundamentals.html 356 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/basics/fundamentals.html#L356) | 袜码欧码换算整体偏移 1–2 码（22–24→36–38 vs 35–38；24–26→39–42 vs 38–41；26–28→43–46 vs 41–45） | 已按 EU≈(脚长+1.5)×1.5 对齐为 35–38 / 38–41 / 41–45 |

#### P1-021 的 9 个核心知识点

| 知识点 | 目标层级 | 现有最高题 | 题目 |
|---|---|---|---|
| sd-map 三维分类框架 | L2 | L1 | socks-design-q4 |
| sd-verify 验货三件套 | L4 | L3 | socks-design-q11 |
| sc-flow 织袜六道主工序 | L2 | L1 | socks-craft-q4 |
| sc-reinforce 跟尖加固与寿命 | L4 | L3 | socks-craft-q3 |
| bm-layers 罩杯四层结构 | L2 | L1 | bras-materials-q4 |
| bc-routes 四条工艺路线 | L4 | L1 | bras-craft-q4 |
| sy-sample 打样链路与封样 | L4 | L3 | basics-supply-q7 |
| jg-case 同名称不同品质案例 | L4 | L3 | sourcing-judgment-q9 |
| jg-verify3 消费者验证三步 | L4 | L3 | sourcing-judgment-q15 |

#### P1-022 的分布细节

- B 作为正确答案 86/193 = 44.6%
- A 70/193 = 36.3%
- C 34/193 = 17.6%
- D 3/193 = 1.6%
- appendix-standards 10 题中 8 题答案为 B；basics-fibers 18 题中 11 题 B。

这会直接削弱自测的诊断价值：学员不读题、只选 B，长期正确率会接近 45%。

---

## 4. P2：口径、术语、编号与专业表述

| ID | 位置 | 问题 | 建议 |
|---|---|---|---|
| P2-001 | [panties/design.html 480 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/panties/design.html#L480) | 图注“常见区间 −5%~−15%”，正文“三角裤臀围 −5%~−12%”，q9 又用 −5%~−15% | 明确图是“含腰头的通用上限”还是“三角裤臀围”，建议与正文统一 |
| P2-002 | [socks/design.html 622 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/socks/design.html#L622) | 3.5"/144N 针距写成约 2.2mm；实际 279÷144≈1.94mm | 改为约 1.9mm；2.1mm 只能对应 3.75" |
| P2-003 | [supplier.html 739 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/sourcing/supplier.html#L739) | 3000 件返单引用 -3%~-6%，但表中 1000→5000 档是 -5%~-10% | 改为 -5%~-10%，或把题干改为 5000 件以上 |
| P2-004 | [supply.html 118 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/basics/supply.html#L118) | 正文“零售价≈出厂价×3-5”，示例却是 7.6~9.3 倍 | 改为“3-8 倍，随渠道/投流变化”，或区分线下与电商 |
| P2-005 | [judgment.html 665 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/sourcing/judgment.html#L665) | “税前利润 8-12 元”被称“毛利率 20-30%”，实际是税前净利率；毛利率约 87% | 改为“税前净利率”或“净利率” |
| P2-006 | 全站图号 | 图号两套规则混用：有的每页从 N-1 开始（导致 1-1~1-5 重复），有的按篇章连续编号；第 5 篇也重复 5-1~5-3 | 选定一套规则并更新 AUTHORING 与正文引用 |
| P2-007 | 全站 30 张表 | `<caption>` 放在 `<tbody>` 之后，不符合 HTML5 table 模型 | 批量移到 `<table>` 第一个子元素 |
| P2-008 | [AUTHORING.md 90 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/AUTHORING.md#L90) | 规范同时写“2-4 道自测题”和“8-14 题/页”，互相冲突 | 统一为“按知识密度，一般 8-14；导学/工具页可 2-4” |
| P2-009 | [fundamentals.html 522 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/basics/fundamentals.html#L522) | 断言“男女内裤的锚都是臀围”，但教材没有男款尺码表；男装实务常按腰围标注 | 区分“标注锚点”与“结构约束”，补男款尺码说明 |
| P2-010 | [bras/materials.html 524 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/bras/materials.html#L524) | “金属圈必然被检针机拦截”过度绝对；NiTi 等非铁磁金属未必报警 | 改为“取决于检针机类型与金属种类；出口客户常直接禁用金属钢圈” |
| P2-011 | [socks/craft.html 536 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/socks/craft.html#L536) | 干扰项写“棉 80%、氨纶 20%”，20% 氨纶远超常规 3-5%，制造了非预期解题线索 | 改为“棉 80%、锦纶 15%、氨纶 5%，无加固” |
| P2-012 | [supplier.html 728 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/sourcing/supplier.html#L728) | “连续 B 级无改善按 C 级处理”只出现在 JS 结论文案，静态表格没有 | 写进分级表或正文，或从题目解析删除 |
| P2-013 | [fundamentals.html 522 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/basics/fundamentals.html#L522) | 解析“区间窄是因为它是硬约束”把“硬约束”与“区间窄”强行因果化 | 改为“臀围决定合体，需单独控制裆宽、直裆与档差；腰围由弹力腰头吸收，所以允许更宽适配” |

---

## 5. P3：低风险但与“严谨”不一致

| ID | 位置 | 问题 | 建议 |
|---|---|---|---|
| P3-001 | [panties/craft.html 595 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/panties/craft.html#L595) | 中文正文夹用英文“slower 产能” | 改为“产能下降” |
| P3-002 | [socks/craft.html 97 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/socks/craft.html#L97) | 8-15 双/小时 × 20 小时 = 160-300，正文写 200-300 | 改为 160-300，或把小时产量改为 10-15 |
| P3-003 | [bras/craft.html 461 行](file:///Volumes/Extreme%20SSD/Projects/Soran/textbook/pages/bras/craft.html#L461) | 图注“损耗与管理 10%-16%”，计算器是 8%-16% | 改为 8%-16%，或让图注引用计算器同组区间 |
| P3-004 | 全站 | 区间连接符混用：`58–66`、`62-66`、`20～22` | 统一为一种（建议 en dash），写入 AUTHORING |
| P3-005 | 若干表格 | quality 250/292、guide 238 等表格无 caption，无法从表格本身判断口径 | 补“示例/教学参考/以标准原文为准” |

---

## 6. 建议修复批次

### Batch A：低风险、可直接改（已完成 2026-10-25）

1. P0-002~005：四处 A 类 pH 全部改为 4.0-7.5；quality 图拆成 A/B/C 三条。
2. P0-006~008：把 socks/design 三道题属性内的英寸符号改为 `&quot;`，修复后用解析器复验。
3. P1-015：guide 链接改为 `basics/fundamentals.html`。
4. P1-016~018：三处 `</td>` 改为 `</caption>`，caption 前移。
5. P3-001/002/003：三个文字/算术小错。

### Batch B：题目语义与答案键（已完成 2026-10-25）

1. P0-009：guide-2 答案键改为 C，并补 D 的解释。
2. P1-001~013：13 处解析字母指代错位全部重写。
3. P2-009、P2-011、P2-012、P2-013：Q8 的性别限定、20% 氨纶干扰项、隐藏规则、硬约束因果全部修正。
4. P1-022：重排 34 题选项并同步解析，答案分布调整为 A60/B62/C50/D30。

### Batch C：数据口径与结构（已完成 2026-10-25）

1. P1-019：两张内裤尺码表标注口径，并补互见说明。
2. P1-020：量价曲线统一为 -12~-18% / -10~-18% / -3~-8%，q7 改为 -10~-18%。
3. P2-001、P2-003、P2-004、P2-005、P2-006、P2-007、P2-008：负放量、返单区间、零售倍率、净利率、图号、caption 位置、AUTHORING 题量全部修正。
4. P1-014、P1-023：付款比例改为 30% + 70-90% + 10-20%；袜码欧码表按公式对齐。
5. P3-004、P3-005：数值区间统一规则写入 AUTHORING，主尺码表改用 en dash；74 张表全部补 caption。

### Batch D：教学系统（已完成 2026-10-25）

1. P1-021：为 9 个核心 KP 补 9 道 L2/L4 题；当前 core 目标层级缺口 0。
2. P1-022：复查全站答案分布；当前 A29.7% / B30.7% / C24.8% / D14.9%，无单项 >35% 或 <10%。

---

## 7. 验收标准

修复后必须全部满足：

- [x] `issues.jsonl` 中 50/50 全部关闭（P0 9、P1 23、P2 13、P3 5）。
- [x] 全站 `data-*` 属性无裸双引号；3 道 socks/design 题的题干与解析完整显示。
- [x] GB 18401 四处 A 类 pH 均为 4.0-7.5；表格、图、解析三处一致。
- [x] Q8 题干前提为真，解析不再出现“区间窄”的错误因果。
- [x] guide-2 答案键与解析指向同一选项（答案 C）。
- [x] 13 处解析字母全部与选项内容对应；34 道重排题逐题复核，202 题点击正确答案全部通过。
- [x] 两张内裤尺码表口径明确；量价曲线/零售倍率/净利率口径一致；袜码欧码表已对齐。
- [x] HTML 解析器：0 个 unmatched tag、0 个未闭合 caption、0 个非法属性。
- [x] 202 道题：data-q/data-exp 非空、4 个选项、data-a 有效、data-level/data-kp 已登记。
- [x] 9 个核心 KP 至少有一道达到目标层级的题（当前缺口 0）。
- [x] 答案分布无单项超过 35% 或低于 10%（A29.7% / B30.7% / C24.8% / D14.9%）。
- [x] 浏览器回归：17 页无 console 报错；202 题点击正确答案全部通过；知识点覆盖面板无缺口；计算器默认值与表格一致；搜索可用；guide 链接可跳转；`file://` 离线加载无报错。

---

## 8. 本轮已通过的项目（不要误改）

- 202 道题的 id 全部唯一，前缀与 pageId 一致。
- data-level / data-kp 无缺失，data-kp 全部在 knowledge-map.js 登记。
- 按“有题挂接”口径，core 知识点无覆盖缺口；按“目标层级”口径，core 缺口也为 0。
- 所有 `data-term` 都能在 glossary.js 找到。
- 搜索索引覆盖 17 个页面与全部小节锚点。
- 无重复 DOM id。
- 74 张表全部有 caption，且均为 table 首个子元素。
- 图号按篇章连续，0 重复、0 缺口（0-1；1-1~1-26；2-1~2-12；3-1~3-9；4-1~4-13；5-1~5-8；A-1）。
- panties / socks / supply 的 BOM 分项与合计全部对得上。
- AQL 表：H/J/K/L/M 的 n、Ac 值与 GB/T 2828.1 常用档一致。
- 文胸尺码计算器、克重计算器、成本估算器、机号匹配器的默认值与公式一致。
- FZ/T 73024 废止、GB/T 8878-2023 整合、FZ/T 73012-2025 / 74002-2025 实施日期均核对通过。
- 全站 202 题点击正确答案全部标记正确；17 页 console error = 0；`file://` 离线加载无报错。

---

## 9. 局限与待人工判断

1. 全站 17 页已做 http 无头浏览器回归（202 题点击正确答案、console error = 0）；`file://` 离线加载抽检了 index、socks/design、standards、supply 四页，均无报错。若要更严格，可再对全部 17 页跑一遍 `file://` 截图回归。
2. 外部标准只抽检了 GB 18401、FZ/T 73024、FZ/T 73012、FZ/T 74002；其他标准/认证/价格未逐条外部核对。
3. SVG 只抽取了文本与数字，未逐张审读图形语义；图形比例、箭头、标注位置不在本轮范围。
4. 74 张表全部解析，但只对成本/BOM/AQL/尺码等关键表做了逐项算术校验；其余表格按“示例值互相不冲突”口径检查。
5. 原“待人工判断”项已按以下决策处理：
   - P0-009 guide-2 采用 C（解析原本就支持 C），并补 D 的解释；
   - P1-019 两张尺码表保留双口径，分别标注“含弹力适配区间”与“标称参考区间”；
   - P1-020 量价曲线统一为 -12~-18% / -10~-18% / -3~-8%；
   - P1-021 选择补 9 道 L2/L4 题，而不是降低 target level；
   - P2-009 把男款“按腰围标注”与“结构锚在臀围/座围”分开表述；
   - P2-010 把“金属圈必然报警”改为“取决于检针机类型与客户标准”。
6. 残余风险：34 道题做了选项位置重排；已逐题复核选项内容、答案键与解析字母，并通过 202 题点击回归，但重排后的语义细微差别仍建议在下一轮内容评审时人工扫一遍。

---

## 10. 附录：问题清单索引

机器可读清单：[issues.jsonl](computer:///Volumes/Extreme%20SSD/Projects/Soran/audit/issues.jsonl)

字段：`id, file, line, category, severity, original_text, issue, evidence, suggestion, confidence, needs_human`。

建议工作流：先按 `severity` 排序，再按 `file` 分组；每修完一组，重新跑一次结构校验与浏览器回归，不要一次性全改后再排查。

---

## 11. Batch A 修复记录（2026-10-25）

| ID | 修改内容 | 复验结果 |
|---|---|---|
| P0-002 | standards 表 A 类 pH 4.0-8.5 → 4.0-7.5 | 全文已无 A 类 4.0-8.5 |
| P0-003 | quality 表 A 类 pH → 4.0-7.5 | 同上 |
| P0-004 | quality 图拆为 A 4.0-7.5 / B 4.0-8.5 / C 4.0-9.0 三条 | 图内文本核对通过 |
| P0-005 | quality q3 解析 pH → 4.0-7.5 | 解析与 q6 一致 |
| P0-006 | socks-design q7 data-exp 英寸符号 → `&quot;` | HTMLParser 解析完整，无非法属性 |
| P0-007 | socks-design q9 data-exp 英寸符号 → `&quot;` | 同上 |
| P0-008 | socks-design q13 data-q/data-exp 英寸符号 → `&quot;` | 题干 107 字、解析 289 字，完整 |
| P1-015 | guide 链接 → `basics/fundamentals.html` | 全站链接扫描 0 错误 |
| P1-016 | standards 认证表 caption → `</caption>` 并前移 | HTMLParser 0 错误 |
| P1-017 | standards 内控表 caption → `</caption>` 并前移 | 同上 |
| P1-018 | standards 送检包表 caption → `</caption>` 并前移 | 同上 |
| P3-001 | “slower 产能” → “产能下降” | 文本核对通过 |
| P3-002 | 200-300 双/台/日 → 160-300 | 8×20=160、15×20=300 |
| P3-003 | 损耗与管理 10%-16% → 8%-16% | 与计算器 DATA.rate 一致 |

复验命令与结果：

- 结构扫描：`PAGES 18 / QUIZZES 202 / TABLES 74 / KP 204`；`STRUCTURAL_ISSUES 0`、`DUP_IDS []`、`COVERAGE_MISSING []`。
- 属性引号扫描：`none`。
- HTMLParser 标签闭合：`bad files 0`。
- 链接扫描：`badHrefs []`。
- 术语扫描：`missingTerms 0`。
- 无头 Chromium 回归：q7/q9/q13 的 data-exp 完整（161/193/289 字），q13 题干完整；quality 表与图、standards 表均为 A 4.0-7.5；三张修复表的 caption 为首个子元素；guide 链接可跳转；目标页面 console error = 0。
- 最终全站回归：17 页、202 题逐题点击正确答案，`failures []`、`console_errors []`；`file://` 抽检 4 页无报错。
- 搜索索引已重建：17 页 / 135 个小节；`file://` 打开 index 时 `SEARCH_INDEX` 加载 17 页，console error = 0。

说明：`issues.jsonl` 中已修复项的 `line` 仍是修复前定位；修复后行号可能偏移 1-3 行。后续修复请以文件内容检索为准，不要只依赖旧行号。

---

## 12. Batch B / C / D 修复记录（2026-10-25）

| 批次 | 关键修改 | 复验 |
|---|---|---|
| B | Q8 题干/解析重写；guide-2 答案改 C；13 处解析字母重写；P2-009/011/012/013 修正 | 202 题点击正确；Q8 题干不再出现“更宽/区间窄”；guide-2 解析与 C 一致 |
| C | 付款比例改为 30%+70-90%+10-20%；内裤/袜码表口径与数值统一；量价曲线统一；零售倍率 3-8；净利率术语；图号篇章连续；74 表 caption；AUTHORING 题量/区间规范；正文 496 处数值区间归一化为 en dash（日期/标准号 hyphen 保留，SVG path d 属性保持 ASCII hyphen） | 表格 74/74 caption-first；图号 0 重复/0 缺口；量价曲线与 q7 一致；袜码表与 fundamentals 一致；SVG 报错 0 |
| D | 9 个核心 KP 各补 1 道 L2/L4 题；34 题重排选项 | 202 题、4 选项；core 目标层级缺口 0；答案分布 A60/B62/C50/D30（29.7/30.7/24.8/14.9%） |

最终答案分布明细：

| 选项 | 题数 | 占比 |
|---|---:|---:|
| A | 60 | 29.7% |
| B | 62 | 30.7% |
| C | 50 | 24.8% |
| D | 30 | 14.9% |
