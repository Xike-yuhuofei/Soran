/* ============================================================
   Soran 教材框架 app.js
   功能：站点导航 / 阅读进度 / 术语弹卡 / 测验引擎 / 全局搜索
   依赖：glossary.js（术语数据）、search-index.js（搜索索引，可选）
   纯离线运行（file:// 协议兼容，不使用 fetch / ES Module）
   ============================================================ */
(function () {
  'use strict';

  /* ---------------- 站点地图 ---------------- */
  var SITE = {
    groups: [
      { name: '开始', pages: ['guide'] },
      { name: '第一篇 · 通用基础', pages: ['basics-fundamentals', 'basics-fibers', 'basics-fabrics', 'basics-quality', 'basics-supply'] },
      { name: '第二篇 · 内裤', pages: ['panties-design', 'panties-craft'] },
      { name: '第三篇 · 袜子', pages: ['socks-design', 'socks-craft'] },
      { name: '第四篇 · 文胸', pages: ['bras-design', 'bras-materials', 'bras-craft'] },
      { name: '第五篇 · 选品实战', pages: ['sourcing-judgment', 'sourcing-supplier'] },
      { name: '附录', pages: ['appendix-glossary', 'appendix-standards'] }
    ],
    pages: {
      'home':                { title: '教材首页', short: '首页', path: 'index.html', group: '' },
      'guide':               { title: '导学 · 如何使用这套教材', short: '导学', path: 'pages/guide.html', group: '开始' },
      'basics-fundamentals': { title: '产品基础与人体工学', short: '产品基础', path: 'pages/basics/fundamentals.html', group: '第一篇 · 通用基础' },
      'basics-fibers':       { title: '纤维与纱线', short: '纤维纱线', path: 'pages/basics/fibers.html', group: '第一篇 · 通用基础' },
      'basics-fabrics':      { title: '针织面料与染整', short: '面料染整', path: 'pages/basics/fabrics.html', group: '第一篇 · 通用基础' },
      'basics-quality':      { title: '性能、检测与质量标准', short: '性能标准', path: 'pages/basics/quality.html', group: '第一篇 · 通用基础' },
      'basics-supply':       { title: '生产制造与供应链', short: '生产供应链', path: 'pages/basics/supply.html', group: '第一篇 · 通用基础' },
      'panties-design':      { title: '内裤 · 分类、结构与版型', short: '分类结构', path: 'pages/panties/design.html', group: '第二篇 · 内裤' },
      'panties-craft':       { title: '内裤 · 工艺、成本与品质', short: '工艺品质', path: 'pages/panties/craft.html', group: '第二篇 · 内裤' },
      'socks-design':        { title: '袜子 · 结构、材料与规格', short: '结构材料', path: 'pages/socks/design.html', group: '第三篇 · 袜子' },
      'socks-craft':         { title: '袜子 · 工艺、性能与品质', short: '工艺性能', path: 'pages/socks/craft.html', group: '第三篇 · 袜子' },
      'bras-design':         { title: '文胸 · 承托原理、分类与结构', short: '原理结构', path: 'pages/bras/design.html', group: '第四篇 · 文胸' },
      'bras-materials':      { title: '文胸 · 材料与版型', short: '材料版型', path: 'pages/bras/materials.html', group: '第四篇 · 文胸' },
      'bras-craft':          { title: '文胸 · 工艺、品质与成本', short: '工艺品质', path: 'pages/bras/craft.html', group: '第四篇 · 文胸' },
      'sourcing-judgment':   { title: '品质判断与产品决策', short: '品质判断', path: 'pages/sourcing/judgment.html', group: '第五篇 · 选品实战' },
      'sourcing-supplier':   { title: '供应商考察与成本管理 · 汕头实战', short: '供应商考察', path: 'pages/sourcing/supplier.html', group: '第五篇 · 选品实战' },
      'appendix-glossary':   { title: '专业术语索引', short: '术语索引', path: 'pages/appendix/glossary.html', group: '附录' },
      'appendix-standards':  { title: '标准与检测方法附录', short: '标准附录', path: 'pages/appendix/standards.html', group: '附录' }
    }
  };

  /* ---------------- 状态存取 ---------------- */
  var LS_KEY = 'soran-textbook-v1';
  var state = { read: {}, quiz: {}, chk: {}, rate: {} };
  try {
    var raw = localStorage.getItem(LS_KEY);
    if (raw) { var p = JSON.parse(raw); if (p && typeof p === 'object') state = Object.assign(state, p); }
  } catch (e) { /* file:// 下个别浏览器禁用时静默降级 */ }

  function save() {
    try {
      /* 只写本模块负责的字段，避免覆盖 widgets.js 刚写入的清单/评分 */
      var cur = {};
      try {
        var raw = localStorage.getItem(LS_KEY);
        if (raw) { var prev = JSON.parse(raw); if (prev && typeof prev === 'object') cur = prev; }
      } catch (e) {}
      cur.read = state.read;
      cur.quiz = state.quiz;
      if (state.secCount) cur.secCount = state.secCount;
      localStorage.setItem(LS_KEY, JSON.stringify(cur));
    } catch (e) {}
    try { document.dispatchEvent(new Event('soran:state-saved')); } catch (e) {}
  }
  function pageProgress(pid) {
    /* 分母优先取该章节自身存储的小节数 secCount，而不是"当前页面"的 DOM 小节数，
       否则用当前页的小节数去判断其他章节，会导致已读完的 ✓ 跳页后时有时无 */
    var total = (state.secCount && state.secCount[pid]) || document.querySelectorAll('[data-sec]').length;
    if (!total) return null;
    var read = (state.read[pid] || []).length;
    return Math.min(1, read / total);
  }
  function isPageDone(pid) {
    var pp = pageProgress(pid);
    return pp !== null && pp >= 1;
  }

  /* ---------------- 通用工具 ---------------- */
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  }); }
  function el(tag, cls, html) {
    var d = document.createElement(tag);
    if (cls) d.className = cls;
    if (html != null) d.innerHTML = html;
    return d;
  }
  function rootPath() {
    /* data-root 形如 "../"、"../../"；去掉尾部斜杠，避免拼接后产生空路径段，
       否则每切换一次页面 URL 就会多出一个 "/"（如 /Soran//pages/...） */
    return (document.body.getAttribute('data-root') || '.').replace(/\/+$/, '');
  }

  /* ---------------- 侧边栏 ---------------- */
  var svgSearch = '<svg class="s-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>';

  function buildSidebar() {
    var host = document.getElementById('sidebar');
    if (!host) return;
    var pid = document.body.getAttribute('data-page-id') || '';
    var root = rootPath();
    var h = '<a class="brand" href="' + root + '/index.html">' +
      '<span class="brand-mark"><span class="brand-logo">素</span>' +
      '<span><span class="brand-name">素然之境 · Soran</span>' +
      '<span class="brand-sub">贴身衣物专业学习教材</span></span></span></a>';
    h += '<div class="side-search">' + svgSearch + '<input id="side-search-input" type="text" placeholder="搜索术语与内容  ( / )" autocomplete="off"></div>';
    h += '<div class="side-progress"><div class="sp-label"><span>总学习进度</span><span id="sp-pct">0%</span></div><div class="sp-bar"><div class="sp-fill" id="sp-fill"></div></div></div>';
    h += '<nav class="nav-tree">';
    SITE.groups.forEach(function (g) {
      h += '<div class="nav-group"><div class="nav-group-title"><span class="dot"></span>' + esc(g.name) + '</div>';
      g.pages.forEach(function (p) {
        var meta = SITE.pages[p];
        if (!meta) return;
        var done = isPageDone(p);
        h += '<a class="nav-item' + (p === pid ? ' active' : '') + (done ? ' done' : '') + '" data-nav="' + p + '" href="' + root + '/' + meta.path + '">' +
          '<span class="nav-num">' + (done ? '✓' : '') + '</span><span>' + esc(meta.short) + '</span></a>';
      });
      h += '</div>';
    });
    h += '</nav>';
    host.innerHTML = h;

    var input = document.getElementById('side-search-input');
    if (input) {
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') { e.preventDefault(); openSearch(input.value); }
        e.stopPropagation();
      });
      input.addEventListener('click', function () { openSearch(input.value); });
      input.readOnly = true; // 统一走弹层，避免移动端双键盘
    }
    var fill = document.getElementById('sp-fill');
    var pct = document.getElementById('sp-pct');
    if (fill && pct) {
      var totalDone = 0, totalPages = 0;
      SITE.groups.forEach(function (g) { g.pages.forEach(function (p) { if (SITE.pages[p] && p !== 'home') { totalPages++; if (isPageDone(p)) totalDone++; } }); });
      var v = totalPages ? Math.round(totalDone / totalPages * 100) : 0;
      fill.style.width = v + '%'; pct.textContent = v + '%';
    }
  }

  /* 移动端抽屉 */
  function buildMenuBtn() {
    var btn = document.querySelector('.menu-btn');
    var side = document.getElementById('sidebar');
    if (!btn || !side) return;
    btn.addEventListener('click', function (e) { e.stopPropagation(); side.classList.toggle('open'); });
    document.addEventListener('click', function (e) {
      if (side.classList.contains('open') && !side.contains(e.target) && e.target !== btn) side.classList.remove('open');
    });
  }

  /* ---------------- 阅读进度 ---------------- */
  function initProgress() {
    var pid = document.body.getAttribute('data-page-id');
    if (!pid) return;
    var secs = Array.prototype.slice.call(document.querySelectorAll('[data-sec]'));
    if (!secs.length) return;
    if (!state.secCount) state.secCount = {};
    if (state.secCount[pid] !== secs.length) { state.secCount[pid] = secs.length; save(); }
    var read = state.read[pid] || (state.read[pid] = []);

    function mark(id) {
      if (read.indexOf(id) === -1) { read.push(id); save(); refreshMeter(); refreshSidebarDone(pid); }
    }
    var meter = document.getElementById('read-fill');
    var pct = document.getElementById('read-pct');
    function refreshMeter() {
      var p = pageProgress(pid) || 0;
      if (meter) meter.style.width = (p * 100) + '%';
      if (pct) pct.textContent = Math.round(p * 100) + '%';
    }
    refreshMeter();

    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting && en.intersectionRatio >= 0.25) mark(en.target.getAttribute('data-sec'));
        });
      }, { threshold: [0.25], rootMargin: '-10% 0px -10% 0px' });
      secs.forEach(function (s) { io.observe(s); });
    } else {
      // 降级：滚动到底即全部标记
      window.addEventListener('scroll', function () {
        if (window.innerHeight + window.scrollY >= document.body.scrollHeight - 200) secs.forEach(function (s) { mark(s.getAttribute('data-sec')); });
      }, { passive: true });
    }

    function refreshSidebarDone(p) {
      var item = document.querySelector('[data-nav="' + p + '"]');
      var meta = SITE.pages[p];
      if (item && meta) {
        var done = isPageDone(p);
        item.classList.toggle('done', done);
        item.querySelector('.nav-num').textContent = done ? '✓' : '';
      }
    }
  }

  /* ---------------- 术语弹卡 ---------------- */
  var pop = null;
  function initTerms() {
    if (!window.GLOSSARY) return;
    document.addEventListener('mouseover', function (e) {
      var t = e.target.closest ? e.target.closest('.term') : null;
      if (t) showPop(t);
      else if (pop && !pop.contains(e.target)) hidePop();
    });
    document.addEventListener('click', function (e) {
      var t = e.target.closest ? e.target.closest('.term') : null;
      if (t) { showPop(t); e.preventDefault(); }
      else if (pop && !pop.contains(e.target)) hidePop();
    });
    window.addEventListener('scroll', hidePop, { passive: true });
    window.addEventListener('resize', hidePop);
  }
  function showPop(termEl) {
    var key = termEl.getAttribute('data-term') || termEl.textContent.trim();
    var g = window.GLOSSARY[key];
    if (!g) return;
    if (!pop) { pop = el('div', 'term-pop'); document.body.appendChild(pop); }
    var root = rootPath();
    pop.innerHTML = '<div class="tp-name">' + esc(key) + (g.en ? '<span class="tp-en">' + esc(g.en) + '</span>' : '') +
      (g.cat ? '<span class="tp-cat">' + esc(g.cat) + '</span>' : '') + '</div>' +
      '<div>' + esc(g.def) + '</div>' +
      (g.see ? '<span class="tp-link" data-goto="' + esc(g.see) + '">相关：' + esc(g.see) + ' →</span>' : '') +
      '<span class="tp-link" data-goto="">术语索引 →</span>';
    var r = termEl.getBoundingClientRect();
    pop.classList.add('show');
    var pw = pop.offsetWidth, ph = pop.offsetHeight;
    var left = Math.min(Math.max(8, r.left + window.scrollX), window.scrollX + document.documentElement.clientWidth - pw - 12);
    var top = r.bottom + window.scrollY + 8;
    if (top + ph > window.scrollY + window.innerHeight - 10) top = r.top + window.scrollY - ph - 8;
    pop.style.left = left + 'px';
    pop.style.top = Math.max(window.scrollY + 6, top) + 'px';
    var link = pop.querySelector('[data-goto]');
    if (link) link.addEventListener('click', function () {
      var t = link.getAttribute('data-goto');
      var anchor = t ? '#g-' + encodeURIComponent(t) : '';
      window.location.href = root + '/pages/appendix/glossary.html' + anchor;
    });
  }
  function hidePop() { if (pop) pop.classList.remove('show'); }

  /* ---------------- 测验引擎 ---------------- */
  var KEYS = ['A', 'B', 'C', 'D', 'E', 'F'];
  function initQuizzes() {
    document.querySelectorAll('.quiz').forEach(function (qEl) {
      var qid = qEl.getAttribute('data-quiz');
      if (!qid || qEl.getAttribute('data-ready')) return;
      qEl.setAttribute('data-ready', '1');
      var q = qEl.getAttribute('data-q') || '';
      var exp = qEl.getAttribute('data-exp') || '';
      var ans = parseInt(qEl.getAttribute('data-a'), 10);
      var opts = Array.prototype.slice.call(qEl.querySelectorAll('.quiz-opts > li, .quiz-opts > .quiz-opt'));

      var head = qEl.querySelector('.quiz-head');
      if (!head) {
        head = el('div', 'quiz-head');
        qEl.insertBefore(head, qEl.firstChild);
      }
      if (!head.querySelector('.q-badge')) {
        var b = el('span', 'q-badge', '自测');
        head.insertBefore(b, head.firstChild);
      }
      /* 认知层级徽标 + 知识点标签（知识覆盖型自测，R3） */
      var KMAP = window.SORAN_KMAP || null;
      var level = qEl.getAttribute('data-level') || '';
      if (level && KMAP && KMAP.levels[level]) {
        head.appendChild(el('span', 'q-level q-lv-' + level.toLowerCase(), level + ' · ' + KMAP.levels[level]));
      }
      var kpIds = (qEl.getAttribute('data-kp') || '').split(/\s+/).filter(Boolean);
      if (kpIds.length && KMAP) {
        var pmeta = KMAP.pages[document.body.getAttribute('data-page-id')];
        if (pmeta && pmeta.points) {
          var nameOf = {};
          pmeta.points.forEach(function (p) { nameOf[p.id] = p; });
          kpIds.forEach(function (k) {
            if (nameOf[k]) {
              var t = el('span', 'q-kp' + (nameOf[k].core ? ' q-kp-core' : ''), nameOf[k].name);
              head.appendChild(t);
            }
          });
        }
      }
      opts.forEach(function (o, i) {
        if (!o.classList.contains('quiz-opt')) {
          var text = o.innerHTML;
          o.className = 'quiz-opt';
          o.innerHTML = '<span class="q-key">' + KEYS[i] + '</span><span>' + text + '</span>';
        } else if (!o.querySelector('.q-key')) {
          o.innerHTML = '<span class="q-key">' + KEYS[i] + '</span><span>' + o.innerHTML + '</span>';
        }
        o.setAttribute('data-i', i);
      });

      var body = qEl.querySelector('.quiz-body') || qEl;
      if (q) {
        var qText = qEl.querySelector('.quiz-q');
        if (!qText) {
          qText = el('p', 'quiz-q');
          var optsWrap = qEl.querySelector('.quiz-opts');
          body.insertBefore(qText, optsWrap || body.firstChild);
        }
        qText.textContent = q;
      }
      var expEl = qEl.querySelector('.quiz-exp');
      if (!expEl) { expEl = el('div', 'quiz-exp'); body.appendChild(expEl); }
      expEl.innerHTML = '<b>解析：</b>' + exp;
      var verdict = el('div', 'quiz-verdict');
      var foot = el('div', 'quiz-foot');
      var retry = el('button', 'btn ghost sm', '重做');
      foot.appendChild(verdict); foot.appendChild(retry);
      body.appendChild(foot);

      var saved = state.quiz[qid];
      function lock() { opts.forEach(function (o) { o.classList.add('quiz-lock'); }); }
      function apply(i) {
        opts.forEach(function (o) {
          var oi = +o.getAttribute('data-i');
          o.classList.remove('correct', 'wrong', 'sel', 'dim');
          if (oi === ans) o.classList.add('correct');
          else if (oi === i) o.classList.add('wrong');
          else o.classList.add('dim');
        });
        var ok = i === ans;
        verdict.className = 'quiz-verdict ' + (ok ? 'ok' : 'no');
        verdict.textContent = ok ? '✓ 回答正确' : '✗ 再想想，解析在下方';
        expEl.classList.add('show');
        state.quiz[qid] = ok;
        save();
        lock();
      }
      function reset() {
        opts.forEach(function (o) { o.classList.remove('correct', 'wrong', 'sel', 'dim', 'quiz-lock'); });
        verdict.textContent = ''; expEl.classList.remove('show');
        delete state.quiz[qid]; save();
      }
      opts.forEach(function (o) {
        o.addEventListener('click', function () {
          if (o.classList.contains('quiz-lock')) return;
          apply(+o.getAttribute('data-i'));
        });
      });
      retry.addEventListener('click', reset);

      if (saved === true || saved === false) apply(saved === true ? ans : -2);
    });
  }

  /* ---------------- 章末知识点覆盖面板（R3） ---------------- */
  function buildKpPanel() {
    var pid = document.body.getAttribute('data-page-id');
    if (!pid || pid === 'home' || pid === 'guide') return;
    var KMAP = window.SORAN_KMAP;
    var meta = KMAP && KMAP.pages[pid];
    if (!meta || !meta.points || !meta.points.length) return;
    var content = document.querySelector('.content');
    if (!content) return;

    /* 收集本页自测题 */
    var quizzes = [];
    document.querySelectorAll('.quiz[data-quiz]').forEach(function (qEl) {
      quizzes.push({
        id: qEl.getAttribute('data-quiz'),
        level: qEl.getAttribute('data-level') || '',
        kps: (qEl.getAttribute('data-kp') || '').split(/\s+/).filter(Boolean)
      });
    });
    if (!quizzes.length) return;

    var byKp = {};
    quizzes.forEach(function (q) {
      q.kps.forEach(function (k) { (byKp[k] = byKp[k] || []).push(q); });
    });

    /* 层级分布 */
    var lvCount = { L1: 0, L2: 0, L3: 0, L4: 0, L5: 0 };
    quizzes.forEach(function (q) { if (lvCount[q.level] !== undefined) lvCount[q.level]++; });

    /* 知识点状态 */
    function pointState(p) {
      var qs = byKp[p.id] || [];
      if (!qs.length) return { cls: 'gap', label: p.core ? '⚠ 覆盖缺口' : '未挂题', qs: 0 };
      var n = 0, right = 0, wrong = 0;
      qs.forEach(function (q) {
        n++;
        var v = state.quiz[q.id];
        if (v === true) right++;
        else if (v === false) wrong++;
      });
      if (right === n) return { cls: 'ok', label: '已掌握', qs: n };
      if (wrong > 0) return { cls: 're', label: '答错待复习', qs: n };
      return { cls: 'todo', label: '未测试', qs: n };
    }

    var cores = meta.points.filter(function (p) { return p.core; });
    var others = meta.points.filter(function (p) { return !p.core; });
    var answered = 0, correct = 0;
    quizzes.forEach(function (q) {
      var v = state.quiz[q.id];
      if (v === true || v === false) answered++;
      if (v === true) correct++;
    });
    var gaps = cores.filter(function (p) { return !(byKp[p.id] || []).length; });

    var h = '';
    h += '<div class="kp-head"><span class="kp-title">本章知识点覆盖面板</span>' +
      '<span class="kp-stat">知识点 <b>' + meta.points.length + '</b>（核心 ' + cores.length + '）· 自测题 <b>' + quizzes.length + '</b> 道 · 已答 ' + answered + ' · 正确 ' + correct + '</span></div>';

    h += '<div class="kp-levels">';
    Object.keys(lvCount).forEach(function (lv) {
      h += '<span class="kp-lv q-lv-' + lv.toLowerCase() + (lvCount[lv] ? '' : ' zero') + '">' + lv + ' ' + KMAP.levels[lv] + ' × ' + lvCount[lv] + '</span>';
    });
    h += '</div>';

    if (gaps.length) {
      h += '<div class="kp-alert">⚠ 以下核心知识点暂无题目覆盖：' + gaps.map(function (p) { return esc(p.name); }).join('、') + '</div>';
    }

    h += '<div class="kp-list">';
    cores.forEach(function (p) {
      var s = pointState(p);
      var lv = KMAP.levels[p.level] || '';
      h += '<div class="kp-row"><span class="kp-chip ' + s.cls + '">' + s.label + '</span>' +
        '<span class="kp-name">' + esc(p.name) + '</span>' +
        '<span class="kp-meta">' + lv + ' · ' + s.qs + ' 题</span></div>';
    });
    h += '</div>';

    if (others.length) {
      h += '<details class="kp-more"><summary>其他知识点（' + others.length + '）</summary><div class="kp-list kp-sub">';
      others.forEach(function (p) {
        var s = pointState(p);
        h += '<div class="kp-row"><span class="kp-chip ' + s.cls + '">' + s.label + '</span>' +
          '<span class="kp-name">' + esc(p.name) + '</span>' +
          '<span class="kp-meta">' + (KMAP.levels[p.level] || '') + ' · ' + s.qs + ' 题</span></div>';
      });
      h += '</div></details>';
    }

    h += '<div class="kp-tip">覆盖面板说明：每道自测题按「认知层次（L1 识记 → L5 综合决策）」与所属知识点标注；核心知识点必须得到有效考查。答错的知识点建议回到对应小节复习后再重做。</div>';

    var panel = el('div', 'kp-panel');
    panel.id = 'kp-panel';
    panel.innerHTML = h;
    var pager = document.getElementById('page-pager');
    if (pager) content.insertBefore(panel, pager);
    else content.appendChild(panel);
  }

  /* ---------------- 全局搜索 ---------------- */
  var overlay = null, sbInput = null, sbResults = null, srItems = [], srCur = -1;
  function ensureOverlay() {
    if (overlay) return;
    overlay = el('div', 'search-overlay');
    overlay.innerHTML =
      '<div class="search-box"><div class="sb-input-row">' + svgSearch +
      '<input id="sb-input" type="text" placeholder="搜索专业术语、章节内容…" autocomplete="off">' +
      '<span class="sb-esc">ESC</span></div>' +
      '<div class="search-results" id="sb-results"></div></div>';
    document.body.appendChild(overlay);
    sbInput = overlay.querySelector('#sb-input');
    sbResults = overlay.querySelector('#sb-results');
    overlay.addEventListener('mousedown', function (e) { if (e.target === overlay) closeSearch(); });
    sbInput.addEventListener('input', doSearch);
    sbInput.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeSearch();
      else if (e.key === 'ArrowDown') { e.preventDefault(); move(1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
      else if (e.key === 'Enter') { e.preventDefault(); if (srItems[srCur]) srItems[srCur].click(); }
    });
  }
  function openSearch(pre) {
    ensureOverlay();
    overlay.classList.add('show');
    sbInput.value = pre || '';
    doSearch();
    setTimeout(function () { sbInput.focus(); sbInput.select(); }, 30);
  }
  function closeSearch() { if (overlay) overlay.classList.remove('show'); }
  function move(d) {
    if (!srItems.length) return;
    srCur = (srCur + d + srItems.length) % srItems.length;
    srItems.forEach(function (it, i) { it.classList.toggle('cur', i === srCur); });
    srItems[srCur].scrollIntoView({ block: 'nearest' });
  }
  function hl(text, q) {
    if (!q) return esc(text);
    var i = text.toLowerCase().indexOf(q.toLowerCase());
    if (i === -1) return esc(text);
    return esc(text.slice(0, i)) + '<mark>' + esc(text.slice(i, i + q.length)) + '</mark>' + esc(text.slice(i + q.length));
  }
  function doSearch() {
    var q = (sbInput.value || '').trim();
    var root = rootPath();
    var out = '';
    srItems = []; srCur = -1;
    if (!q) {
      out = '<div class="sr-empty">输入关键词，搜索术语定义与章节内容<br><span style="font-size:12px">例如：旦尼尔、钢圈、克重、AQL、模杯</span></div>';
    } else {
      var ql = q.toLowerCase();
      // 术语优先
      var terms = [];
      if (window.GLOSSARY) {
        Object.keys(window.GLOSSARY).forEach(function (k) {
          var g = window.GLOSSARY[k];
          if (k.toLowerCase().indexOf(ql) > -1 || (g.en || '').toLowerCase().indexOf(ql) > -1) {
            terms.push({ k: k, g: g });
          }
        });
        terms.sort(function (a, b) { return (a.k.toLowerCase().indexOf(ql)) - (b.k.toLowerCase().indexOf(ql)); });
        terms = terms.slice(0, 6);
      }
      if (terms.length) {
        out += '<div class="sr-group">专业术语</div>';
        terms.forEach(function (t) {
          var href = root + '/pages/appendix/glossary.html#g-' + encodeURIComponent(t.k);
          var a = el('a', 'sr-item');
          a.href = href;
          a.innerHTML = '<div class="sr-t">' + hl(t.k, q) + '<span class="sr-loc">' + esc(t.g.cat || '术语') + '</span></div><div class="sr-s">' + esc(t.g.def.slice(0, 72)) + (t.g.def.length > 72 ? '…' : '') + '</div>';
          out += a.outerHTML;
        });
      }
      // 章节内容
      var idx = window.SEARCH_INDEX || [];
      var hits = [];
      idx.forEach(function (pg) {
        (pg.secs || []).forEach(function (s) {
          var inT = (s.t || '').toLowerCase().indexOf(ql) > -1;
          var inS = (s.s || '').toLowerCase().indexOf(ql) > -1;
          if (inT || inS) hits.push({ pg: pg, s: s, w: inT ? 0 : 1 });
        });
      });
      hits.sort(function (a, b) { return a.w - b.w; });
      if (hits.length) {
        out += '<div class="sr-group">章节内容</div>';
        hits.slice(0, 14).forEach(function (h) {
          var a = el('a', 'sr-item');
          a.href = root + '/' + h.pg.path + (h.s.a ? '#' + h.s.a : '');
          var snip = h.s.s || '';
          var pos = snip.toLowerCase().indexOf(ql);
          if (pos > 40) snip = '…' + snip.slice(pos - 30);
          a.innerHTML = '<div class="sr-t">' + hl(h.s.t || h.pg.title, q) + '<span class="sr-loc">' + esc(h.pg.title) + '</span></div>' +
            '<div class="sr-s">' + hl(snip.slice(0, 110), q) + '</div>';
          out += a.outerHTML;
        });
      }
      if (!out) out = '<div class="sr-empty">未找到「' + esc(q) + '」相关内容</div>';
    }
    sbResults.innerHTML = out;
    srItems = Array.prototype.slice.call(sbResults.querySelectorAll('.sr-item'));
    srItems.forEach(function (it) { it.addEventListener('click', closeSearch); });
    if (srItems.length) { srCur = 0; srItems[0].classList.add('cur'); }
  }

  /* ---------------- 页脚：上一篇 / 下一篇 ---------------- */
  function buildPager() {
    var pid = document.body.getAttribute('data-page-id');
    if (!pid || pid === 'home') return;
    var flat = [];
    SITE.groups.forEach(function (g) { g.pages.forEach(function (p) { if (SITE.pages[p]) flat.push(p); }); });
    var i = flat.indexOf(pid);
    if (i === -1) return;
    var root = rootPath();
    var prev = i > 0 ? SITE.pages[flat[i - 1]] : null;
    var next = i < flat.length - 1 ? SITE.pages[flat[i + 1]] : null;
    var host = document.getElementById('page-pager');
    if (!host) {
      host = el('div');
      host.id = 'page-pager';
      host.style.cssText = 'display:flex;gap:12px;margin-top:56px;padding-top:22px;border-top:1px solid var(--line)';
      var content = document.querySelector('.content');
      if (content) content.appendChild(host);
    }
    function card(p, dir) {
      if (!p) return '<div style="flex:1"></div>';
      return '<a href="' + root + '/' + p.path + '" style="flex:1;text-decoration:none;color:inherit;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:13px 16px;transition:border-color .15s" onmouseover="this.style.borderColor=\'var(--green)\'" onmouseout="this.style.borderColor=\'var(--line)\'">' +
        '<div style="font-size:11.5px;color:var(--ink-faint)">' + (dir < 0 ? '← 上一篇' : '下一篇 →') + '</div>' +
        '<div style="font-size:14px;font-weight:650;margin-top:3px">' + esc(p.title) + '</div></a>';
    }
    host.innerHTML = card(prev, -1) + card(next, 1);
  }

  /* ---------------- 章节小节锚点目录（页内 TOC） ---------------- */
  function buildPageToc() {
    var secs = document.querySelectorAll('h2[data-sec]');
    if (secs.length < 3) return;
    var host = document.getElementById('page-toc');
    if (!host) return;
    var h = '<div style="font-size:12px;letter-spacing:.15em;color:var(--ink-faint);font-weight:700;margin-bottom:9px">本页内容</div>';
    secs.forEach(function (s, i) {
      h += '<a href="#' + s.getAttribute('data-sec') + '" style="display:flex;gap:9px;align-items:baseline;padding:4px 0;font-size:13.5px;color:var(--ink-soft);text-decoration:none">' +
        '<span style="font-family:var(--font-mono);font-size:11.5px;color:var(--gold);font-weight:600">' + String(i + 1).padStart(2, '0') + '</span>' +
        '<span>' + esc(s.textContent.replace(/^\d+(\.\d+)*\s*/, '')) + '</span></a>';
    });
    host.innerHTML = h;
  }

  /* ---------------- 键盘快捷键 ---------------- */
  function initKeys() {
    document.addEventListener('keydown', function (e) {
      var tag = (e.target.tagName || '').toLowerCase();
      var typing = tag === 'input' || tag === 'textarea' || e.target.isContentEditable;
      if (typing) return;
      if (e.key === '/' || (e.key.toLowerCase() === 'k' && (e.metaKey || e.ctrlKey))) {
        e.preventDefault(); openSearch('');
      }
      if (e.key === 'Escape') closeSearch();
    });
  }

  /* ---------------- 启动 ---------------- */
  function normalizeUrl() {
    /* 旧地址可能带有多余斜杠（如 /Soran/////pages/...），先收敛为单斜杠，
       避免后续相对链接继续带上空路径段 */
    try {
      var p = location.pathname.replace(/\/{2,}/g, '/');
      if (p !== location.pathname) history.replaceState(null, '', p + location.search + location.hash);
    } catch (e) { /* file:// 或受限环境下静默降级 */ }
  }

  function boot() {
    normalizeUrl();
    buildSidebar();
    buildMenuBtn();
    initProgress();
    initTerms();
    initQuizzes();
    initKeys();
    buildPager();
    buildPageToc();
    buildKpPanel();
    if (window.SORAN_WIDGETS && window.SORAN_WIDGETS.initAll) window.SORAN_WIDGETS.initAll();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();

  /* 对外暴露 */
  window.SORAN = { SITE: SITE, state: state, save: save, openSearch: openSearch };
})();
