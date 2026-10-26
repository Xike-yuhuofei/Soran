/* ============================================================
   Soran 教材 · 知识点地图（知识覆盖型自测数据）
   - 每章的知识点清单：id / 名称 / 是否核心(core) / 目标认知层次(level)
   - 各页自测题通过 data-kp="空格分隔的知识点id" 与 data-level="L1-L5"
     挂接到知识点；app.js 据此渲染层级徽标与章末覆盖面板。
   - 维护规范见 AUTHORING.md。纯离线，file:// 可用。
   ============================================================ */
window.SORAN_KMAP = {
  levels: { L1: '识记', L2: '理解', L3: '分析', L4: '应用', L5: '综合决策' },

  pages: {
    /* ================= 第二篇 · 内裤 ================= */
    'panties-craft': {
      points: [
        { id: 'pc-routes',   name: '三大工艺路线选择（车缝/无痕/无缝）', core: true, level: 'L4' },
        { id: 'pc-stitch',   name: '车缝线迹组合（包缝/绷缝/针距）', core: true, level: 'L2' },
        { id: 'pc-waist',    name: '腰头三工艺与触肤对策', core: true, level: 'L3' },
        { id: 'pc-bond',     name: '无痕工艺：切边/胶条三要素/耐洗', core: true, level: 'L4' },
        { id: 'pc-seamless', name: '无缝工艺：分区织造与后道工序', core: true, level: 'L3' },
        { id: 'pc-defect',   name: '内裤缺陷图鉴与工序定责', core: true, level: 'L4' },
        { id: 'pc-cost',     name: '三路线 BOM 成本对比', core: true, level: 'L4' },
        { id: 'pc-check',    name: '选品判断清单（14 项）', core: false, level: 'L3' },
        { id: 'pc-buy',      name: '花钱优先级：里裆/橡筋/胶条', core: true, level: 'L5' },
        { id: 'pc-case',     name: '完整案例：无痕三角裤开发五步与异常归因', core: true, level: 'L5' }
      ]
    },

    'panties-design': {
      points: [
        { id: 'pd-map',        name: '三变量分类框架（覆盖度/腰高/后片）', core: true, level: 'L2' },
        { id: 'pd-anatomy',    name: '结构八件与侧缝/脚边选择', core: true, level: 'L3' },
        { id: 'pd-wave',       name: '前后浪差铁律（后浪>前浪）', core: true, level: 'L4' },
        { id: 'pd-crotchwidth', name: '裆宽：夹裆与堆积的总开关', core: true, level: 'L4' },
        { id: 'pd-rise',       name: '直裆深度与坐姿工况', core: true, level: 'L3' },
        { id: 'pd-hipcup',     name: '臀杯剪接塑形', core: false, level: 'L3' },
        { id: 'pd-mens',       name: '男士前囊三方案与裤脚防卷', core: true, level: 'L4' },
        { id: 'pd-crossfit',   name: '男女版型不可互改', core: true, level: 'L3' },
        { id: 'pd-gusset',     name: '底裆：双层/材质/固定/色牢度', core: true, level: 'L4' },
        { id: 'pd-antibac',    name: '抗菌裆实证态度（洗后数据）', core: true, level: 'L3' },
        { id: 'pd-negative',   name: '负放量第一性原理', core: true, level: 'L3' },
        { id: 'pd-sizeconv',   name: '内外裤尺码不互通', core: true, level: 'L3' },
        { id: 'pd-sku',        name: 'SKU 矩阵：宽度换深度的陷阱', core: true, level: 'L5' }
      ]
    },

    /* ================= 第三篇 · 袜子 ================= */
    'socks-design': {
      points: [
        { id: 'sd-map',        name: '三维分类框架（长度×功能×工艺）', core: true, level: 'L2' },
        { id: 'sd-anatomy',    name: '八部位解剖与「部位=织造程序」', core: true, level: 'L2' },
        { id: 'sd-cuff',       name: '袜口三式（罗口/橡筋口/翻口）', core: true, level: 'L2' },
        { id: 'sd-gauge',      name: '针数定义与针距公式（π×筒径÷针数）', core: true, level: 'L3' },
        { id: 'sd-gaugesize',  name: '筒径决定尺码范围：加码靠换机', core: true, level: 'L3' },
        { id: 'sd-gauge-fit',  name: '针数与定位匹配：针数≠品质', core: true, level: 'L3' },
        { id: 'sd-yarn',       name: '添纱三层纱结构与成分标重量≠结构', core: true, level: 'L3' },
        { id: 'sd-blend',      name: '四类袜子配比逻辑（运动袜低棉+加固）', core: true, level: 'L4' },
        { id: 'sd-weight',     name: '克重区间与针数×克重四组合', core: true, level: 'L3' },
        { id: 'sd-verify',     name: '验货三件套：标+秤+拆', core: true, level: 'L4' },
        { id: 'sd-size',       name: '尺码宽容原理与实测脚长区间标注', core: true, level: 'L2' },
        { id: 'sd-sku',        name: 'SKU 矩阵（144N走量/高针形象/功能款）', core: true, level: 'L5' },
        { id: 'sd-color',      name: '深色摩擦色牢度风险与颜色配比', core: true, level: 'L2' },
        { id: 'sd-owner',      name: '材质故事诚实边界与配比岗位论', core: true, level: 'L3' }
      ]
    },

    'socks-craft': {
      points: [
        { id: 'sc-flow',      name: '织袜六道主工序与机台参数管理', core: true, level: 'L2' },
        { id: 'sc-flow-dye',  name: '先织后染：染整风险暴露时点与返工损失', core: true, level: 'L3' },
        { id: 'sc-toe',       name: '缝头三法与品质分水岭（机缝有棱原理）', core: true, level: 'L4' },
        { id: 'sc-heel',      name: '收放针转跟与掉跟三成因排查', core: true, level: 'L3' },
        { id: 'sc-terry',     name: '毛圈三规格词（高度/密度/范围）', core: true, level: 'L3' },
        { id: 'sc-reinforce', name: '跟尖加固与运动袜寿命逻辑', core: true, level: 'L4' },
        { id: 'sc-set',       name: '定型四事与氨纶烫伤隐性定责', core: true, level: 'L4' },
        { id: 'sc-antibac',   name: '抗菌宣称只认洗后数据', core: true, level: 'L3' },
        { id: 'sc-defect',    name: '袜子八类缺陷：长相-成因-责任-验货', core: true, level: 'L4' },
        { id: 'sc-cost',      name: '成本公式与三档 BOM 拆解', core: true, level: 'L3' },
        { id: 'sc-cost-gap',  name: '规模厂与小厂价差五处来源', core: true, level: 'L3' },
        { id: 'sc-priority',  name: '里子加钱优先级：橡筋>缝头>针数', core: true, level: 'L5' },
        { id: 'sc-case',      name: '完整案例：通勤女袜开发五步与异常归因', core: true, level: 'L5' },
        { id: 'sc-check',     name: '选品判断清单 12 项执行', core: false, level: 'L3' }
      ]
    },

    /* ================= 第四篇 · 文胸 ================= */
    'bras-design': {
      points: [
        { id: 'bd-ligament',  name: '库珀韧带不可逆与品类存在理由', core: true, level: 'L1' },
        { id: 'bd-support',   name: '承托两路径：底围为主、肩带为辅', core: true, level: 'L3' },
        { id: 'bd-diagnosis', name: '问诊顺序：先底围→杯容→肩带最后', core: true, level: 'L4' },
        { id: 'bd-matrix',    name: '四维分类矩阵（钢圈/覆盖/厚度/形态）', core: true, level: 'L2' },
        { id: 'bd-anatomy',   name: '结构十件与部位即功能', core: true, level: 'L2' },
        { id: 'bd-panel',     name: '下扒/钢圈槽/侧比/后比核心职责', core: true, level: 'L3' },
        { id: 'bd-seam',      name: '杯面剪接与钢圈槽两种做法', core: false, level: 'L2' },
        { id: 'bd-size',      name: '尺码体系：5cm底围档×差值定字母', core: true, level: 'L2' },
        { id: 'bd-vol',       name: '同字母不同围杯容不同', core: true, level: 'L3' },
        { id: 'bd-sister',    name: '姐妹码：上移一围下移一杯', core: true, level: 'L4' },
        { id: 'bd-fit',       name: '版型＞尺码与胸型定杯型', core: true, level: 'L3' },
        { id: 'bd-defect',    name: '八大试穿问题归因（码/版/工艺）', core: true, level: 'L4' },
        { id: 'bd-education', name: '七成尺码错配与教育优先经营', core: true, level: 'L5' }
      ]
    },

    'bras-materials': {
      points: [
        { id: 'bm-layers',        name: '罩杯四层结构与读 BOM 顺序', core: true, level: 'L2' },
        { id: 'bm-bom',           name: 'BOM 要素与罩杯外材料族成本占比', core: true, level: 'L3' },
        { id: 'bm-tricot',        name: '锦氨特里科第一性原理（稳定成形）', core: true, level: 'L3' },
        { id: 'bm-fabric-compare', name: '五种杯面/里布对比与纯棉定位', core: true, level: 'L2' },
        { id: 'bm-lining',        name: '里布两路线与场景取舍（贴肤三处）', core: true, level: 'L3' },
        { id: 'bm-core',          name: '四种芯材特性与选型速查', core: true, level: 'L3' },
        { id: 'bm-core-elastic',  name: '芯材回弹命门与洗后状态', core: true, level: 'L4' },
        { id: 'bm-hardware',      name: '钢圈三档材质与圈径×开口', core: true, level: 'L2' },
        { id: 'bm-hardware-check', name: '低价辅料偷工点与 10 秒验法', core: true, level: 'L4' },
        { id: 'bm-grade',         name: '放码三条独立规则与姐妹码分别放码', core: true, level: 'L4' },
        { id: 'bm-bigcup',        name: '大杯力学与先中间后两端扩码', core: true, level: 'L5' },
        { id: 'bm-config',        name: '三条配置路线与预算投入逻辑', core: true, level: 'L4' },
        { id: 'bm-card',          name: '材料卡要素与营销俗称鉴定', core: true, level: 'L4' }
      ]
    },

    'bras-craft': {
      points: [
        { id: 'bc-routes',    name: '四条工艺路线全景与选择决策树', core: true, level: 'L4' },
        { id: 'bc-chain',     name: '车缝工序链：碗→架子→总装', core: true, level: 'L2' },
        { id: 'bc-gate',      name: '三大品质关口（杯部/骨架/总装后）', core: true, level: 'L3' },
        { id: 'bc-labor',     name: '工缴底层逻辑：工序秒数×秒单价', core: true, level: 'L3' },
        { id: 'bc-molding',   name: '模压三要素与参数-缺陷对应', core: true, level: 'L3' },
        { id: 'bc-mold-cost', name: '模具账与外购模杯打样路径', core: true, level: 'L4' },
        { id: 'bc-onedefect', name: '一体成型误区与大杯跑杯', core: true, level: 'L3' },
        { id: 'bc-bond',      name: '热压无痕命门：剥离强度+洗3次', core: true, level: 'L4' },
        { id: 'bc-seamless',  name: '无缝针织特性与看厂要点', core: false, level: 'L3' },
        { id: 'bc-defect',    name: '十二项缺陷溯源（材/艺/版/储）', core: true, level: 'L4' },
        { id: 'bc-wash',      name: '洗后复测的时间性劣化逻辑', core: true, level: 'L4' },
        { id: 'bc-cost',      name: '成本五段结构与路线大头科目', core: true, level: 'L4' },
        { id: 'bc-cost-cut',  name: '降本三刀：剪接/模杯标准化/量价阶梯', core: true, level: 'L5' },
        { id: 'bc-inspect',   name: '验货三节点与重心前移', core: true, level: 'L4' },
        { id: 'bc-case',      name: '完整案例：光面无痕文胸开发五步与降本防御', core: true, level: 'L5' }
      ]
    },

    /* ================= 第一篇 · 通用基础 ================= */
    'basics-fundamentals': {
      points: [
        { id: 'fu-layer',      name: '三层着装与贴身层四大使命', core: true, level: 'L1' },
        { id: 'fu-sweat',      name: '汗液四步旅程与「闷/干爽」机理', core: true, level: 'L3' },
        { id: 'fu-heat',       name: '保暖＝锁静止空气与「湿冷」', core: true, level: 'L3' },
        { id: 'fu-touch',      name: '触感：扎感的纤维端来源', core: true, level: 'L2' },
        { id: 'fu-pressure',   name: '服装压强与「以面积换压强」', core: true, level: 'L3' },
        { id: 'fu-breast',     name: '乳房悬吊结构与「承托靠底盘」', core: true, level: 'L3' },
        { id: 'fu-crotch',     name: '腰臀差、直裆与坐姿极限工况', core: true, level: 'L4' },
        { id: 'fu-foot',       name: '足部三点受力与袜子角色', core: true, level: 'L2' },
        { id: 'fu-size',       name: '号型制 vs 围度制，内裤锚在臀围', core: true, level: 'L2' },
        { id: 'fu-bra-size',   name: '文胸尺码框架（下围号＋罩杯字母）', core: false, level: 'L1' },
        { id: 'fu-sock-size',  name: '袜子厘米码：弹性覆盖围度难覆盖长度', core: true, level: 'L2' },
        { id: 'fu-freesize',   name: '「均码」的机制与局限', core: true, level: 'L4' },
        { id: 'fu-category',   name: '三大品类商业画像差异', core: true, level: 'L5' },
        { id: 'fu-priority',   name: '功能优先级先定、款式后定', core: true, level: 'L5' }
      ]
    },

    'basics-supply': {
      points: [
        { id: 'sy-chain',   name: '全链路八环与两套计价逻辑换算', core: true, level: 'L3' },
        { id: 'sy-mfg',     name: '三品类制造差异（裁缝/成型/组装）', core: true, level: 'L2' },
        { id: 'sy-cluster', name: '七大产业集群与选择逻辑', core: true, level: 'L2' },
        { id: 'sy-mode',    name: 'OEM/ODM/自研与「ODM+规格书」起步', core: true, level: 'L4' },
        { id: 'sy-sample',  name: '打样链路五步、封样基准与翻车点', core: true, level: 'L4' },
        { id: 'sy-moq',     name: 'MOQ 摊销逻辑与小单快反代价', core: true, level: 'L3' },
        { id: 'sy-cost',    name: '成本公式拆解与量级感', core: true, level: 'L4' },
        { id: 'sy-lead',    name: '交期链与品质成本 1:10:100', core: true, level: 'L3' },
        { id: 'sy-vendor',  name: '供应商评估五维总览', core: true, level: 'L3' }
      ]
    },

    'basics-fibers': {
      points: [
        { id: 'fib-map',       name: '纤维分类地图（天然/再生/合成）', core: true,  level: 'L1' },
        { id: 'fib-cotton',    name: '棉的性能与品质阶梯（普梳/精梳/长绒棉）', core: true, level: 'L2' },
        { id: 'fib-wetstrong', name: '棉湿强高于干强的应用含义', core: true, level: 'L2' },
        { id: 'fib-animal',    name: '蚕丝/羊毛/麻的特性与贴身适用性', core: false, level: 'L2' },
        { id: 'fib-viscose',   name: '粘胶：吸湿强项与湿强骤降软肋', core: true, level: 'L2' },
        { id: 'fib-modal',     name: '莫代尔与品牌纤维溢价逻辑', core: true, level: 'L2' },
        { id: 'fib-lyocell',   name: '莱赛尔工艺与「天丝」商标规则', core: true, level: 'L2' },
        { id: 'fib-bamboo',    name: '竹浆粘胶本质与「天然抗菌」话术拆解', core: true, level: 'L3' },
        { id: 'fib-polyester', name: '涤纶：不吸湿≠不能导湿', core: true, level: 'L3' },
        { id: 'fib-nylon',     name: '锦纶：耐磨冠军与锦氨弹力体系', core: true, level: 'L2' },
        { id: 'fib-spandex',   name: '氨纶：含量档位与「三怕」（氯/高温/油）', core: true, level: 'L2' },
        { id: 'fib-pp',        name: '丙纶：导湿极限与原液着色', core: false, level: 'L2' },
        { id: 'fib-table',     name: '九纤维性能对比与混纺互补逻辑', core: true, level: 'L3' },
        { id: 'fib-yarn',      name: '细度三把尺子：纱支/旦数(dtex换算)/F数', core: true, level: 'L3' },
        { id: 'fib-twist',     name: '加捻、合股与纱线性格', core: false, level: 'L2' },
        { id: 'fib-elastyarn', name: '包芯纱 vs 包覆纱（单包/双包）', core: true, level: 'L4' },
        { id: 'fib-filament',  name: '短纤纱 vs 长丝：手感与用途分工', core: true, level: 'L2' },
        { id: 'fib-label',     name: '成分标规则（GB/T 29862：降序/合并/允差三档/纯100%）', core: true, level: 'L3' },
        { id: 'fib-detect',    name: '虚标识别与营销名词鉴定', core: true, level: 'L4' },
        { id: 'fib-threepq',   name: '成分决策三问（功能/成本/可验证）', core: true, level: 'L5' }
      ]
    },

    'basics-fabrics': {
      points: [
        { id: 'fb-knit',      name: '针织弹性的线圈来源与三大代价', core: true, level: 'L2' },
        { id: 'fb-weft',      name: '纬编家族组织与用途分工（汗布/罗纹/棉毛/毛圈/提花）', core: true, level: 'L2' },
        { id: 'fb-plating',   name: '添纱：面纱/地纱各占一面', core: true, level: 'L4' },
        { id: 'fb-warp',      name: '经编三大特性与文胸面料', core: true, level: 'L2' },
        { id: 'fb-spec',      name: '机号/克重/幅宽与「偷密度」', core: true, level: 'L3' },
        { id: 'fb-dye',       name: '染料-纤维匹配与染整六步', core: true, level: 'L2' },
        { id: 'fb-whitecore', name: '露白芯机理（酸性染料不上染氨纶）', core: true, level: 'L3' },
        { id: 'fb-finish',    name: '定型/超喂与缩水的分水岭', core: true, level: 'L3' },
        { id: 'fb-soft',      name: '硅油手感鉴别（滴水/过水复摸）', core: true, level: 'L3' },
        { id: 'fb-shade',     name: '灰卡与分缸管理', core: true, level: 'L4' },
        { id: 'fb-func',      name: '功能整理宣称的实证（洗后数据）', core: true, level: 'L4' },
        { id: 'fb-buy',       name: '面料采购实务（四要素/测试单）', core: true, level: 'L4' }
      ]
    },

    'basics-quality': {
      points: [
        { id: 'q-inout',       name: '内在质量 vs 外观质量与分等制度', core: true, level: 'L2' },
        { id: 'q-gb18401',     name: 'GB 18401 A/B/C 分类与核心限值', core: true, level: 'L1' },
        { id: 'q-gb31701',     name: 'GB 31701 婴幼儿加严与 A 类标注合规', core: true, level: 'L3' },
        { id: 'q-shrink',      name: '水洗尺寸变化率：面料缩率与成衣缩率', core: true, level: 'L2' },
        { id: 'q-fastness',    name: '色牢度体系与耐湿摩擦高发风险', core: true, level: 'L3' },
        { id: 'q-elastic',     name: '拉伸弹性回复率与氨纶品质', core: true, level: 'L2' },
        { id: 'q-stduse',      name: '产品标准家族与分等验收（GB/T 8878-2023 等）', core: true, level: 'L3' },
        { id: 'q-defect',      name: '缺陷图鉴：五大类缺陷的长相·成因·定责', core: true, level: 'L4' },
        { id: 'q-4point',      name: '四分制验布评分', core: false, level: 'L2' },
        { id: 'q-aql',         name: 'AQL 抽样判定（批量→字码→n→Ac/Re）', core: true, level: 'L4' },
        { id: 'q-inspectflow', name: '验货五道闸流程与留样证据链', core: true, level: 'L3' },
        { id: 'q-report',      name: '读第三方检测报告五步与 CMA/CNAS', core: true, level: 'L3' },
        { id: 'q-internal',    name: '内控标准搭建思路（严可感/宽无感）', core: true, level: 'L5' }
      ]
    },

    /* ================= 第五篇 · 选品实战 ================= */
    'sourcing-judgment': {
      points: [
        { id: 'jg-quadrant',  name: '贵与好的四象限与 Soran 定位', core: true, level: 'L2' },
        { id: 'jg-priority',  name: '好产品优先级链（版型>材料>工艺>细节）', core: true, level: 'L2' },
        { id: 'jg-hype',      name: '营销噱头识别（冰丝/牛奶丝/蚕丝蛋白/抗菌竹炭/石墨烯）', core: true, level: 'L3' },
        { id: 'jg-cert',      name: '认证核验与证书挂靠防范', core: true, level: 'L3' },
        { id: 'jg-handtest',  name: '快速手评六法与对比原则', core: true, level: 'L4' },
        { id: 'jg-teardown',  name: '竞品拆解五步与记录表', core: true, level: 'L4' },
        { id: 'jg-legal',     name: '拆解的合法与伦理边界', core: true, level: 'L3' },
        { id: 'jg-techpack',  name: '规格书七件套', core: true, level: 'L3' },
        { id: 'jg-aql',       name: '验收标准与 AQL 条款落地', core: true, level: 'L4' },
        { id: 'jg-case',      name: '同名称不同品质案例拆解', core: true, level: 'L4' },
        { id: 'jg-gate',      name: '样品评审：合规红线与加权质量的分离决策', core: true, level: 'L5' },
        { id: 'jg-cross',     name: '跨章节综合：从纤维到验收的完整决策链', core: true, level: 'L5' },
        { id: 'jg-perception', name: '感知分级：强感知/洗后感知/弱感知/无感知', core: true, level: 'L4' },
        { id: 'jg-verify3',   name: '消费者验证三步：试穿/洗测/回访归因', core: true, level: 'L4' },
        { id: 'jg-waterfall', name: '零售价瀑布：出厂价到成交价的科目拆解', core: true, level: 'L5' }
      ]
    },

    'sourcing-supplier': {
      points: [
        { id: 'sp-cluster',  name: '产业集群逻辑（谷饶生态与打样小单优势）', core: true, level: 'L2' },
        { id: 'sp-factory',  name: '工厂形态与贸易商识别', core: true, level: 'L4' },
        { id: 'sp-audit',    name: '实地考察方法（动线/清单/访谈）', core: true, level: 'L4' },
        { id: 'sp-trial',    name: '试单闸门与关键项全检', core: true, level: 'L4' },
        { id: 'sp-score',    name: '季度评分卡：红线+加权', core: true, level: 'L3' },
        { id: 'sp-tier',     name: 'A/B/C 分级与订单联动、淘汰机制', core: true, level: 'L3' },
        { id: 'sp-cost',     name: '成本谈判（BOM 拆解/量价联动）', core: true, level: 'L4' },
        { id: 'sp-payment',  name: '付款账期与资金红线', core: true, level: 'L3' },
        { id: 'sp-profit',   name: '健康利润观：质价比≠最低价', core: true, level: 'L5' }
      ]
    },

    /* ================= 附录 ================= */
    'appendix-standards': {
      points: [
        { id: 'std-hierarchy', name: '标准层级：GB 强制 / GB·FZ 推荐 / 内控', core: true, level: 'L1' },
        { id: 'std-18401',     name: 'GB 18401 限值全表速查', core: true, level: 'L2' },
        { id: 'std-31701',     name: 'GB 31701 婴幼儿线叠加要求', core: false, level: 'L2' },
        { id: 'std-29862',     name: 'GB/T 29862 标识规则与允差分档', core: true, level: 'L3' },
        { id: 'std-5296',      name: 'GB 5296.4 使用说明与耐久性标签三项', core: true, level: 'L2' },
        { id: 'std-product',   name: '产品标准速查与版本时效（GB/T 8878-2023 整合 FZ/T 73024 等）', core: true, level: 'L3' },
        { id: 'std-method',    name: '检测方法标准按指标速查与审报告三步', core: true, level: 'L3' },
        { id: 'std-cert',      name: '认证核验五步（OEKO-TEX/GOTS/GRS/CMA/CNAS）', core: true, level: 'L3' },
        { id: 'std-internal',  name: '内控加严方向与送检三包', core: true, level: 'L4' },
        { id: 'std-version',   name: '标准版本时效风险与核对渠道', core: true, level: 'L4' }
      ]
    },

    'appendix-glossary': {
      points: [
        { id: 'gl-use',      name: '三种入口：弹卡/搜索/分类浏览', core: true, level: 'L2' },
        { id: 'gl-chain',    name: '相关链路学习法与锚点引用', core: false, level: 'L2' },
        { id: 'gl-dynamic',  name: '动态生成与「待收录」机制', core: true, level: 'L1' },
        { id: 'gl-verify',   name: '用索引核实营销话术的路径', core: true, level: 'L4' }
      ]
    },

    /* 导学页（不参与章末覆盖面板，题目 KP 供全站图谱统计） */
    'guide': {
      points: [
        { id: 'gd-position', name: '四层问题：是什么/为什么/怎么比/怎么定', core: false, level: 'L2' },
        { id: 'gd-map',      name: '五篇结构与学习顺序（先地基后品类）', core: false, level: 'L1' },
        { id: 'gd-path',     name: '三种学习路径选择', core: true, level: 'L3' },
        { id: 'gd-tools',    name: '四大功能：术语/搜索/进度/自测', core: false, level: 'L1' },
        { id: 'gd-data',     name: '教学示例值与数据严谨性原则', core: false, level: 'L2' },
        { id: 'gd-habit',    name: '三个学习习惯：拆/对比/带问题下厂', core: true, level: 'L3' }
      ]
    }
  }
};
