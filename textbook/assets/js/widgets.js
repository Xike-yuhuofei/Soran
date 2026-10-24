/* ============================================================
   Soran 教材交互组件库 widgets.js
   提供：标签页 / 折叠面板 / 滑杆 / 可持久化清单 / 评分行 /
        SVG 热点说明 / 数字动画 / 进度条动画
   页面脚本可通过 window.W 调用；data-* 自动初始化
   ============================================================ */
(function () {
  'use strict';
  var LS_KEY = 'soran-textbook-v1';
  function load() { try { return JSON.parse(localStorage.getItem(LS_KEY)) || {}; } catch (e) { return {}; } }
  function save(s) { try { localStorage.setItem(LS_KEY, JSON.stringify(s)); } catch (e) {} }
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  }); }
  function el(tag, cls, html) { var d = document.createElement(tag); if (cls) d.className = cls; if (html != null) d.innerHTML = html; return d; }

  var CHECK_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.4"><path d="M4 12.5l5.5 5.5L20 6.5"/></svg>';

  var W = {};

  /* ---------- 标签页 ---------- */
  W.tabs = function (root) {
    root.querySelectorAll('.tabs').forEach(function (bar) {
      if (bar.getAttribute('data-ready')) return;
      bar.setAttribute('data-ready', '1');
      var scope = bar.closest('[data-tabs]') || bar.parentElement;
      var ids = Array.prototype.map.call(bar.querySelectorAll('.tab'), function (t) { return t.getAttribute('data-tab'); });
      bar.querySelectorAll('.tab').forEach(function (t) {
        t.addEventListener('click', function () {
          var id = t.getAttribute('data-tab');
          bar.querySelectorAll('.tab').forEach(function (x) { x.classList.toggle('active', x === t); });
          scope.querySelectorAll('.tab-pane').forEach(function (p) {
            if (ids.indexOf(p.id) > -1) p.classList.toggle('active', p.id === id);
          });
        });
      });
    });
  };

  /* ---------- 折叠面板 ---------- */
  W.acc = function (root) {
    root.querySelectorAll('.acc-head').forEach(function (h) {
      if (h.getAttribute('data-ready')) return;
      h.setAttribute('data-ready', '1');
      h.addEventListener('click', function () { h.parentElement.classList.toggle('open'); });
    });
  };

  /* ---------- 滑杆 ---------- */
  // W.slider({min,max,step,value,fmt,onInput}) -> {input, set}
  W.slider = function (cfg) {
    var input = document.createElement('input');
    input.type = 'range'; input.className = 'sr';
    input.min = cfg.min; input.max = cfg.max; input.step = cfg.step || 1; input.value = cfg.value;
    input.style.flex = '1 1 140px';
    var val = el('span', 'ctl-val');
    function paint() { val.textContent = cfg.fmt ? cfg.fmt(+input.value) : input.value; }
    input.addEventListener('input', function () { paint(); cfg.onInput(+input.value); });
    paint();
    return { input: input, val: val, set: function (v) { input.value = v; paint(); cfg.onInput(+input.value); } };
  };

  /* ---------- 可持久化清单 ---------- */
  W.checklist = function (root, id) {
    var boxes = root.querySelectorAll('.chk');
    var st = load();
    var on = st.chk && st.chk[id] ? st.chk[id] : [];
    function paint() {
      boxes.forEach(function (b, i) { b.classList.toggle('on', on.indexOf(i) > -1); });
      root.querySelectorAll('.chk-group').forEach(function (g) {
        var next = g.nextElementSibling, n = 0, tot = 0;
        while (next && !next.classList.contains('chk-group')) {
          if (next.classList.contains('chk')) { tot++; var gi = Array.prototype.indexOf.call(boxes, next); if (gi > -1 && on.indexOf(gi) > -1) n++; }
          next = next.nextElementSibling;
        }
        var tag = g.querySelector('.cg-n');
        if (tag) tag.textContent = n + ' / ' + tot;
      });
      var sum = root.querySelector('[data-chk-sum]');
      if (sum) {
        sum.textContent = on.length + ' / ' + boxes.length + ' 项已确认';
        var bar = root.querySelector('[data-chk-bar]');
        if (bar) bar.style.width = (boxes.length ? on.length / boxes.length * 100 : 0) + '%';
      }
    }
    boxes.forEach(function (b, i) {
      var inp = b.querySelector('input');
      if (inp) inp.checked = on.indexOf(i) > -1;
      b.addEventListener('click', function (e) {
        e.preventDefault();
        var k = on.indexOf(i);
        if (k > -1) on.splice(k, 1); else on.push(i);
        var s = load(); s.chk = s.chk || {}; s.chk[id] = on; save(s);
        paint();
      });
    });
    var reset = root.querySelector('[data-chk-reset]');
    if (reset) reset.addEventListener('click', function () { on = []; var s = load(); s.chk = s.chk || {}; s.chk[id] = on; save(s); paint(); });
    paint();
  };

  /* ---------- 评分行（样品评价表） ---------- */
  W.rates = function (root, id) {
    var rows = root.querySelectorAll('.rate-row');
    var st = load();
    var vals = (st.rate && st.rate[id]) || {};
    var scale = (root.getAttribute('data-rate-scale') || '1,2,3,4,5').split(',').map(Number);
    function paint() {
      var total = 0, max = 0;
      rows.forEach(function (r) {
        var k = r.getAttribute('data-key');
        var v = vals[k];
        var w = +(r.getAttribute('data-weight') || 1);
        if (v) total += v * w;
        max += Math.max.apply(null, scale) * w;
        r.querySelectorAll('.dot-b').forEach(function (b) { b.classList.toggle('on', +b.getAttribute('data-v') === v); });
        var sum = r.querySelector('.rr-sum');
        if (sum) sum.textContent = v ? v + ' / ' + Math.max.apply(null, scale) + ' 分' : '未评';
      });
      var sumEl = root.querySelector('[data-rate-sum]');
      if (sumEl) sumEl.textContent = '总分：' + total + ' / ' + max + (max ? '（' + Math.round(total / max * 100) + '%）' : '');
      var barEl = root.querySelector('[data-rate-bar]');
      if (barEl) barEl.style.width = (max ? total / max * 100 : 0) + '%';
    }
    rows.forEach(function (r) {
      var k = r.getAttribute('data-key');
      var dots = r.querySelector('.rr-dots');
      if (!dots) { dots = el('span', 'rr-dots'); r.appendChild(dots); }
      if (!dots.children.length) {
        scale.forEach(function (n) {
          var b = el('button', 'dot-b', String(n));
          b.type = 'button'; b.setAttribute('data-v', n);
          b.addEventListener('click', function () {
            if (vals[k] === n) delete vals[k]; else vals[k] = n;
            var s = load(); s.rate = s.rate || {}; s.rate[id] = vals; save(s);
            paint();
          });
          dots.appendChild(b);
        });
        if (!r.querySelector('.rr-sum')) r.appendChild(el('span', 'rr-sum'));
      }
    });
    var reset = root.querySelector('[data-rate-reset]');
    if (reset) reset.addEventListener('click', function () { vals = {}; var s = load(); s.rate = s.rate || {}; s.rate[id] = vals; save(s); paint(); });
    paint();
  };

  /* ---------- SVG 热点说明 ---------- */
  // <div data-hotroot> <svg>…<g class="svg-hot" data-tip="标题|说明文字">…</g></svg>
  // <div data-hotout></div> </div>
  W.hotspots = function (root) {
    root.querySelectorAll('.svg-hot').forEach(function (h) {
      if (h.getAttribute('data-ready')) return;
      h.setAttribute('data-ready', '1');
      h.addEventListener('click', function () {
        var scope = h.closest('[data-hotroot]') || root;
        var tip = h.getAttribute('data-tip') || '';
        var parts = tip.split('|');
        var out = scope.querySelector('[data-hotout]');
        scope.querySelectorAll('.svg-hot').forEach(function (x) { x.classList.toggle('on', x === h && !h.classList.contains('on')); });
        var active = h.classList.contains('on');
        if (out) {
          out.innerHTML = active
            ? '<b style="color:var(--green-deep)">' + esc(parts[0]) + '</b>' + (parts[1] ? '<span style="color:var(--ink-soft)">' + esc(parts[1]) + '</span>' : '')
            : '<span style="color:var(--ink-faint)">点击图中编号查看结构说明</span>';
        }
      });
    });
  };

  /* ---------- 数字滚动 ---------- */
  W.count = function (node, to, opts) {
    opts = opts || {};
    var dur = opts.dur || 500, dec = opts.dec || 0, suf = opts.suf || '', pre = opts.pre || '';
    var from = 0, t0 = null;
    function step(t) {
      if (!t0) t0 = t;
      var p = Math.min(1, (t - t0) / dur);
      var v = from + (to - from) * (1 - Math.pow(1 - p, 3));
      node.textContent = pre + v.toFixed(dec).replace(/\B(?=(\d{3})+(?!\d))/g, ',') + suf;
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  };

  /* ---------- 自动初始化 ---------- */
  function initAll() {
    document.querySelectorAll('[data-tabs]').forEach(W.tabs);
    document.querySelectorAll('[data-acc], [data-acc-open]').forEach(W.acc);
    document.querySelectorAll('[data-checklist]').forEach(function (n) { W.checklist(n, n.getAttribute('data-checklist')); });
    document.querySelectorAll('[data-rate]').forEach(function (n) { W.rates(n, n.getAttribute('data-rate')); });
    document.querySelectorAll('[data-hotroot]').forEach(W.hotspots);
    if (window.__SORAN_PAGE_INIT__) { try { window.__SORAN_PAGE_INIT__(); } catch (e) { console.error(e); } }
  }
  W.initAll = initAll;
  window.W = W;
  window.SORAN_WIDGETS = W;
})();
