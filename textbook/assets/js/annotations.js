/* ============================================================
   Soran 教材 · 云端账号与笔记标注 annotations.js
   功能：Supabase 邮箱登录 / 划线高亮 / 下划线 / 笔记 / 本页笔记抽屉
   依赖：supabase-config.js（window.SORAN_SUPABASE）
   纯原生 JS，不使用外部 SDK 或 CDN，保持离线可用
   ============================================================ */
(function () {
  'use strict';

  var CFG = window.SORAN_SUPABASE || {};
  var PID = document.body.getAttribute('data-page-id') || '';
  var CONTENT = document.querySelector('.content');
  if (!CONTENT || !PID) return;

  var AUTH_KEY = 'soran-auth-v1';
  var CACHE_PREFIX = 'soran-ann-cache-v1:';
  var BLOCK_SELECTOR = 'p, li, td, th, blockquote, figcaption, dt, dd, h1, h2, h3, h4, h5, h6, .kv-k, .kv-v';
  var MAX_QUOTE = 1200;
  var REQUEST_TIMEOUT = 20000;

  var session = loadSession();
  var annotations = [];
  var blockEls = [];
  var markRects = [];
  var layer = null;
  var toolbar = null;
  var editor = null;
  var drawer = null;
  var backdrop = null;
  var modal = null;
  var toastHost = null;

  var pending = null;
  var pendingAfterLogin = null;
  var currentEditorAnn = null;
  var editStyle = 'highlight';
  var editColor = 'green';
  var authMode = 'login';
  var busy = false;
  var repaintTimer = 0;
  var selTimer = 0;
  var longSelToastAt = 0;

  /* ---------------- 基础工具 ---------------- */
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function el(tag, cls, html) {
    var d = document.createElement(tag);
    if (cls) d.className = cls;
    if (html != null) d.innerHTML = html;
    return d;
  }
  function isConfigured() {
    return !!(CFG && /^https?:\/\//.test(String(CFG.url || '')) && String(CFG.anonKey || '').length > 20);
  }
  function apiUrl(path) {
    return String(CFG.url || '').replace(/\/+$/, '') + path;
  }
  function httpError(msg, status) {
    var e = new Error(msg);
    e.status = status || 0;
    return e;
  }
  function trimQuote(q) {
    var s = String(q || '').replace(/\s+/g, ' ').trim();
    return s.length > 160 ? s.slice(0, 160) + '…' : s;
  }
  function findAnn(id) {
    for (var i = 0; i < annotations.length; i++) {
      if (String(annotations[i].id) === String(id)) return annotations[i];
    }
    return null;
  }

  /* ---------------- 登录会话 ---------------- */
  function loadSession() {
    try {
      var s = JSON.parse(localStorage.getItem(AUTH_KEY) || 'null');
      if (s && s.access_token && s.user && s.user.id) return s;
    } catch (e) {}
    return null;
  }
  function saveSession(s) {
    session = s;
    try { localStorage.setItem(AUTH_KEY, JSON.stringify(s)); } catch (e) {}
  }
  function clearSession() {
    session = null;
    try { localStorage.removeItem(AUTH_KEY); } catch (e) {}
  }
  function normalizeSession(data) {
    var exp = data.expires_at
      ? data.expires_at * 1000
      : Date.now() + ((data.expires_in || 3600) * 1000);
    return {
      access_token: data.access_token,
      refresh_token: data.refresh_token || '',
      expires_at: exp,
      user: data.user || (session ? session.user : null)
    };
  }

  function timedFetch(url, opts) {
    if (typeof AbortController === 'undefined') return fetch(url, opts);
    var ctrl = new AbortController();
    var timer = setTimeout(function () { ctrl.abort(); }, REQUEST_TIMEOUT);
    var o = Object.assign({}, opts || {}, { signal: ctrl.signal, cache: 'no-store' });
    return fetch(url, o).finally(function () { clearTimeout(timer); });
  }

  async function authRequest(path, body) {
    var res;
    try {
      res = await timedFetch(apiUrl(path), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'apikey': CFG.anonKey || '' },
        body: JSON.stringify(body || {})
      });
    } catch (e) {
      throw httpError('网络不可用，请检查连接', 0);
    }
    var data = {};
    try { data = await res.json(); } catch (e) {}
    if (!res.ok) {
      var msg = data.error_description || data.msg || data.message || data.error || ('HTTP ' + res.status);
      throw httpError(msg, res.status);
    }
    return data;
  }

  async function signIn(email, password) {
    var data = await authRequest('/auth/v1/token?grant_type=password', { email: email, password: password });
    if (!data.access_token) throw httpError('登录失败，请检查邮箱与密码', 0);
    return normalizeSession(data);
  }

  async function signUp(email, password) {
    var data = await authRequest('/auth/v1/signup', { email: email, password: password });
    var s = data.session || (data.access_token ? data : null);
    if (s) return { session: normalizeSession(s) };
    return { needsConfirm: true };
  }

  async function refreshSession() {
    if (!session || !session.refresh_token) throw httpError('登录已过期', 401);
    var data = await authRequest('/auth/v1/token?grant_type=refresh_token', {
      refresh_token: session.refresh_token
    });
    if (!data.access_token) throw httpError('登录已过期', 401);
    var next = normalizeSession(data);
    if (!next.user && session.user) next.user = session.user;
    saveSession(next);
    return next;
  }

  async function ensureSession() {
    if (!session) return null;
    if (session.expires_at && session.expires_at < Date.now() + 60000) {
      if (!session.refresh_token) { clearSession(); return null; }
      try {
        await refreshSession();
      } catch (e) {
        if (e.status === 400 || e.status === 401) {
          clearSession();
          updateAccountUI();
          throw httpError('登录已过期，请重新登录', 401);
        }
        throw e;
      }
    }
    return session;
  }

  async function rest(path, opts) {
    opts = opts || {};
    var s = await ensureSession();
    if (!s) throw httpError('请先登录', 401);

    function doFetch() {
      var headers = Object.assign({
        'apikey': CFG.anonKey || '',
        'Authorization': 'Bearer ' + session.access_token
      }, opts.headers || {});
      return timedFetch(apiUrl(path), Object.assign({}, opts, { headers: headers }));
    }

    var res;
    try {
      res = await doFetch();
    } catch (e) {
      throw httpError('网络不可用，请检查连接', 0);
    }

    if (res.status === 401 && session && session.refresh_token) {
      try {
        await refreshSession();
      } catch (e) {
        if (e.status === 400 || e.status === 401) {
          clearSession();
          updateAccountUI();
        }
        throw e;
      }
      try {
        res = await doFetch();
      } catch (e) {
        throw httpError('网络不可用，请检查连接', 0);
      }
    }

    if (!res.ok) {
      var data = {};
      try { data = await res.json(); } catch (e) {}
      if (res.status === 401) {
        clearSession();
        updateAccountUI();
      }
      var msg = data.message || data.error_description || data.hint || data.error || data.msg;
      throw httpError(msg || ('请求失败 HTTP ' + res.status), res.status);
    }
    if (res.status === 204) return null;
    try { return await res.json(); } catch (e) { return null; }
  }

  function authErrorText(msg) {
    var m = String(msg || '');
    if (/Invalid login credentials/i.test(m)) return '邮箱或密码不正确';
    if (/User already registered|already registered|already exists/i.test(m)) return '该邮箱已注册，请直接登录';
    if (/Password should be at least|weak_password/i.test(m)) return '密码至少 6 位';
    if (/Email not confirmed/i.test(m)) return '邮箱尚未确认，请先查收确认邮件';
    if (/JWT expired|invalid JWT|token is expired/i.test(m)) return '登录已过期，请重新登录';
    if (/permission denied|row-level security/i.test(m)) return '没有权限访问这条笔记';
    if (/rate limit|too many/i.test(m)) return '请求过于频繁，请稍后再试';
    if (/Failed to fetch|NetworkError|Load failed|aborted/i.test(m)) return '网络不可用，请检查连接';
    return m || '操作失败，请稍后重试';
  }

  /* ---------------- 本地缓存 ---------------- */
  function cacheKey() {
    return session && session.user ? CACHE_PREFIX + session.user.id + ':' + PID : '';
  }
  function saveCache() {
    var key = cacheKey();
    if (!key) return;
    try { localStorage.setItem(key, JSON.stringify(annotations)); } catch (e) {}
  }
  function renderCache() {
    var key = cacheKey();
    if (!key) return;
    try {
      var arr = JSON.parse(localStorage.getItem(key) || 'null');
      if (Array.isArray(arr)) {
        annotations = arr;
        renderAll();
        updateCount();
      }
    } catch (e) {}
  }

  /* ---------------- 文本块与锚点 ---------------- */
  function collectBlocks() {
    var all = Array.prototype.slice.call(CONTENT.querySelectorAll(BLOCK_SELECTOR));
    var candidates = all.filter(function (b) {
      return !b.closest('.quiz, svg, .ann-ui, .ann-layer, #page-toc, .page-pager, .kp-panel');
    });
    blockEls = candidates.filter(function (b) {
      return !candidates.some(function (o) {
        return o !== b && b.contains(o);
      });
    });
    return blockEls;
  }

  function blockOf(node) {
    var e = node.nodeType === 3 ? node.parentElement : node;
    if (!e || !CONTENT.contains(e)) return null;
    if (e.closest('svg, .quiz, button, input, textarea, select, .ann-ui, .ann-layer, script, style')) return null;
    var b = e.closest(BLOCK_SELECTOR);
    if (!b || !CONTENT.contains(b)) return null;
    return blockEls.indexOf(b) > -1 ? b : null;
  }

  function textNodesOf(block) {
    var nodes = [];
    var walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        var p = n.parentElement;
        if (!p) return NodeFilter.FILTER_REJECT;
        if (p.closest('svg, script, style, .ann-ui, .ann-layer')) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var n;
    while ((n = walker.nextNode())) nodes.push(n);
    return nodes;
  }

  function blockText(block) {
    var nodes = textNodesOf(block);
    var s = '';
    for (var i = 0; i < nodes.length; i++) s += nodes[i].nodeValue;
    return s;
  }

  function offsetIn(block, container, offset) {
    var nodes = textNodesOf(block);
    if (!nodes.length) return 0;

    if (container.nodeType === 3) {
      var acc = 0;
      for (var i = 0; i < nodes.length; i++) {
        if (nodes[i] === container) return acc + Math.min(offset, nodes[i].nodeValue.length);
        acc += nodes[i].nodeValue.length;
      }
      return acc;
    }

    var after = container.nodeType === 1 ? container.childNodes[offset] : null;
    var acc2 = 0;
    for (var j = 0; j < nodes.length; j++) {
      if (after && (nodes[j] === after || (after.contains && after.contains(nodes[j])))) return acc2;
      acc2 += nodes[j].nodeValue.length;
    }
    return acc2;
  }

  function pointAt(block, offset, isEnd) {
    var nodes = textNodesOf(block);
    if (!nodes.length) return null;
    var acc = 0;
    for (var i = 0; i < nodes.length; i++) {
      var len = nodes[i].nodeValue.length;
      if (offset < acc + len || (offset === acc + len && (isEnd || i === nodes.length - 1))) {
        return { node: nodes[i], offset: Math.max(0, Math.min(offset - acc, len)) };
      }
      acc += len;
    }
    var last = nodes[nodes.length - 1];
    return { node: last, offset: last.nodeValue.length };
  }

  function makeRange(si, so, ei, eo) {
    if (si < 0 || ei < si || ei >= blockEls.length) return null;
    var sp = pointAt(blockEls[si], so, false);
    var ep = pointAt(blockEls[ei], eo, true);
    if (!sp || !ep) return null;
    var r = document.createRange();
    try {
      r.setStart(sp.node, sp.offset);
      r.setEnd(ep.node, ep.offset);
    } catch (e) {
      return null;
    }
    return r.collapsed ? null : r;
  }

  function selectionAnchor() {
    var sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount) return null;
    var range = sel.getRangeAt(0);
    if (!CONTENT.contains(range.startContainer) || !CONTENT.contains(range.endContainer)) return null;

    collectBlocks();
    var sb = blockOf(range.startContainer);
    var eb = blockOf(range.endContainer);
    if (!sb || !eb) return null;

    var si = blockEls.indexOf(sb);
    var ei = blockEls.indexOf(eb);
    if (si < 0 || ei < 0 || ei < si) return null;

    var quote = range.toString();
    if (!quote.trim()) return null;
    if (quote.length > MAX_QUOTE) {
      if (Date.now() - longSelToastAt > 3000) {
        longSelToastAt = Date.now();
        toast('选择范围过长，请分段标注', 'warn');
      }
      return null;
    }

    var frag = range.cloneContents();
    if (frag.querySelector && frag.querySelector('svg, .quiz, button, input, textarea, select')) return null;

    var so = offsetIn(sb, range.startContainer, range.startOffset);
    var eo = offsetIn(eb, range.endContainer, range.endOffset);
    if (si === ei && eo <= so) return null;

    return {
      start_block: si,
      end_block: ei,
      start_offset: so,
      end_offset: eo,
      quote: quote,
      rect: range.getBoundingClientRect()
    };
  }

  function resolveAnchor(ann) {
    var si = ann.start_block;
    var ei = ann.end_block;
    var r = makeRange(si, ann.start_offset, ei, ann.end_offset);
    if (r && r.toString() === ann.quote) {
      return { si: si, ei: ei, so: ann.start_offset, eo: ann.end_offset, range: r };
    }

    var q = String(ann.quote || '');
    for (var i = 0; i < blockEls.length; i++) {
      var t = blockText(blockEls[i]);
      var idx = t.indexOf(q);
      var qq = q;
      if (idx < 0) {
        qq = q.trim();
        if (qq) idx = t.indexOf(qq);
      }
      if (idx > -1) {
        var r2 = makeRange(i, idx, i, idx + qq.length);
        if (r2) return { si: i, ei: i, so: idx, eo: idx + qq.length, range: r2 };
      }
    }
    return null;
  }

  /* ---------------- 覆盖层渲染 ---------------- */
  function createLayer() {
    if (layer) return;
    layer = el('div', 'ann-layer');
    layer.setAttribute('aria-hidden', 'true');
    CONTENT.appendChild(layer);
  }

  function renderAll() {
    if (!layer) return;
    layer.innerHTML = '';
    markRects = [];
    collectBlocks();

    var cr = CONTENT.getBoundingClientRect();
    annotations.forEach(function (ann) {
      var resolved = resolveAnchor(ann);
      ann._orphan = false;
      ann._hidden = false;
      if (!resolved) {
        ann._orphan = true;
        return;
      }
      var rects = resolved.range.getClientRects();
      var list = [];

      for (var i = 0; i < rects.length && i < 300; i++) {
        var rc = rects[i];
        if (rc.width < 1 || rc.height < 1) continue;

        var left = rc.left - cr.left + CONTENT.scrollLeft;
        var top = rc.top - cr.top + CONTENT.scrollTop;
        list.push({ left: left, top: top, width: rc.width, height: rc.height });

        var mk = el('div', 'ann-mark ann-' + ann.style + ' ann-c-' + (ann.color || 'green'));
        mk.style.left = left + 'px';
        mk.style.top = (ann.style === 'underline' ? top + rc.height - 3 : top) + 'px';
        mk.style.width = rc.width + 'px';
        mk.style.height = (ann.style === 'underline' ? 3 : rc.height) + 'px';
        mk.setAttribute('data-ann', ann.id);
        layer.appendChild(mk);
      }

      if (!list.length) {
        ann._hidden = true;
        return;
      }
      markRects.push({ ann: ann, rects: list });
    });

    updateCount();
    if (drawer && drawer.classList.contains('show')) renderDrawer();
  }

  function scheduleRepaint() {
    if (repaintTimer) cancelAnimationFrame(repaintTimer);
    repaintTimer = requestAnimationFrame(function () {
      repaintTimer = 0;
      renderAll();
    });
  }

  /* ---------------- 云端笔记读写 ---------------- */
  function loadAnnotations(silent) {
    if (!session) {
      annotations = [];
      renderAll();
      renderDrawer();
      updateCount();
      return Promise.resolve();
    }

    renderCache();
    setSyncStatus('同步中…');

    var path = '/rest/v1/annotations?page_id=eq.' + encodeURIComponent(PID) + '&select=*&order=created_at.asc';
    return rest(path).then(function (rows) {
      annotations = Array.isArray(rows) ? rows : [];
      saveCache();
      renderAll();
      renderDrawer();
      updateCount();
      setSyncStatus('已同步');
    }).catch(function (e) {
      if (e.status === 401) {
        annotations = [];
        renderAll();
        renderDrawer();
        updateCount();
        setSyncStatus('未登录');
        return;
      }
      setSyncStatus(annotations.length ? '离线缓存' : '同步失败');
      if (!silent) toast('笔记同步失败：' + authErrorText(e.message), 'warn');
    });
  }

  async function createAnnotation(anchor, style) {
    if (busy || !session) return;
    busy = true;

    var annStyle = style === 'underline' ? 'underline' : 'highlight';
    var body = {
      page_id: PID,
      start_block: anchor.start_block,
      end_block: anchor.end_block,
      start_offset: anchor.start_offset,
      end_offset: anchor.end_offset,
      quote: anchor.quote,
      style: annStyle,
      color: 'green',
      note: ''
    };

    try {
      var rows = await rest('/rest/v1/annotations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Prefer': 'return=representation' },
        body: JSON.stringify(body)
      });
      var row = Array.isArray(rows) ? rows[0] : null;
      if (!row) throw httpError('保存失败，请稍后重试', 0);

      annotations.push(row);
      saveCache();
      renderAll();
      renderDrawer();
      updateCount();
      toast(annStyle === 'underline' ? '已添加下划线' : '已高亮');
      if (style === 'note') openEditor(row, true);
    } catch (e) {
      if (e.status === 401) {
        toast('登录已过期，请重新登录', 'warn');
        openAuth('login', { style: style, anchor: anchor });
      } else {
        toast('保存失败：' + authErrorText(e.message), 'warn');
      }
    } finally {
      busy = false;
      try { window.getSelection().removeAllRanges(); } catch (e) {}
    }
  }

  async function deleteAnnotation(id) {
    var ann = findAnn(id);
    if (!ann) return;
    if (!window.confirm('删除这条标注？')) return;
    try {
      await rest('/rest/v1/annotations?id=eq.' + encodeURIComponent(String(id)), { method: 'DELETE' });
      annotations = annotations.filter(function (a) { return String(a.id) !== String(id); });
      saveCache();
      if (currentEditorAnn && String(currentEditorAnn.id) === String(id)) closeEditor();
      renderAll();
      renderDrawer();
      updateCount();
      toast('已删除');
    } catch (e) {
      toast('删除失败：' + authErrorText(e.message), 'warn');
    }
  }

  /* ---------------- 选中工具条 ---------------- */
  function createToolbar() {
    if (toolbar) return;
    toolbar = el('div', 'ann-toolbar');
    toolbar.setAttribute('role', 'toolbar');
    toolbar.innerHTML =
      '<button type="button" data-style="highlight" aria-label="高亮"><span class="ann-swatch" style="background:#3D6B57"></span>高亮</button>' +
      '<button type="button" data-style="underline" aria-label="下划线"><span class="ann-swatch" style="background:#44657F"></span>下划线</button>' +
      '<button type="button" data-style="note" aria-label="记笔记"><span class="ann-swatch" style="background:#B98F45"></span>笔记</button>';
    document.body.appendChild(toolbar);

    toolbar.addEventListener('mousedown', function (e) {
      e.preventDefault();
      e.stopPropagation();
    });
    toolbar.addEventListener('click', function (e) {
      var b = e.target.closest ? e.target.closest('button[data-style]') : null;
      if (!b || !pending) return;
      var style = b.getAttribute('data-style');
      var anchor = pending.anchor;
      hideToolbar();
      if (!session) {
        openAuth('login', { style: style, anchor: anchor });
        return;
      }
      createAnnotation(anchor, style);
    });
  }

  function showToolbar(rect) {
    if (!toolbar) return;
    toolbar.classList.add('show');

    requestAnimationFrame(function () {
      var w = toolbar.offsetWidth;
      var h = toolbar.offsetHeight;
      var left = Math.min(Math.max(8, rect.left + rect.width / 2 - w / 2), window.innerWidth - w - 8);
      var top = rect.top - h - 10;
      if (top < 8) top = rect.bottom + 10;
      toolbar.style.left = left + 'px';
      toolbar.style.top = Math.max(8, top) + 'px';
    });
  }

  function hideToolbar() {
    if (toolbar) toolbar.classList.remove('show');
    pending = null;
  }

  /* ---------------- 笔记编辑卡 ---------------- */
  function buildEditor() {
    if (editor) return;
    editor = el('div', 'ann-editor');
    editor.setAttribute('role', 'dialog');
    editor.setAttribute('aria-label', '笔记编辑');
    editor.innerHTML =
      '<div class="ae-head"><span class="ae-title">标注</span><button type="button" class="ann-x" data-editor-close aria-label="关闭">×</button></div>' +
      '<div class="ae-quote"></div>' +
      '<div class="ae-row"><span class="ae-label">样式</span><div class="ae-seg">' +
        '<button type="button" data-style="highlight">高亮</button>' +
        '<button type="button" data-style="underline">下划线</button>' +
      '</div></div>' +
      '<div class="ae-row"><span class="ae-label">颜色</span><div class="ae-colors">' +
        '<button type="button" data-color="green" aria-label="石绿"></button>' +
        '<button type="button" data-color="clay" aria-label="陶土"></button>' +
        '<button type="button" data-color="gold" aria-label="米金"></button>' +
      '</div></div>' +
      '<textarea placeholder="写点什么…"></textarea>' +
      '<div class="ae-foot">' +
        '<button type="button" class="btn ghost sm" data-editor-delete>删除</button>' +
        '<div class="ae-spacer"></div>' +
        '<button type="button" class="btn ghost sm" data-editor-cancel>取消</button>' +
        '<button type="button" class="btn sm" data-editor-save>保存</button>' +
      '</div>';
    document.body.appendChild(editor);

    editor.addEventListener('mousedown', function (e) { e.stopPropagation(); });

    editor.querySelector('[data-editor-close]').addEventListener('click', closeEditor);
    editor.querySelector('[data-editor-cancel]').addEventListener('click', closeEditor);
    editor.querySelector('[data-editor-save]').addEventListener('click', saveEditor);
    editor.querySelector('[data-editor-delete]').addEventListener('click', function () {
      if (currentEditorAnn) deleteAnnotation(currentEditorAnn.id);
    });

    editor.querySelectorAll('[data-style]').forEach(function (b) {
      b.addEventListener('click', function () {
        editStyle = b.getAttribute('data-style');
        paintEditorControls();
      });
    });
    editor.querySelectorAll('[data-color]').forEach(function (b) {
      b.addEventListener('click', function () {
        editColor = b.getAttribute('data-color');
        paintEditorControls();
      });
    });
    editor.querySelector('textarea').addEventListener('keydown', function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        saveEditor();
      }
    });
  }

  function paintEditorControls() {
    if (!editor) return;
    editor.querySelectorAll('.ae-seg [data-style]').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-style') === editStyle);
    });
    editor.querySelectorAll('.ae-colors [data-color]').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-color') === editColor);
    });
  }

  function openEditor(ann, focusNote) {
    if (!session) {
      openAuth('login');
      return;
    }
    buildEditor();
    currentEditorAnn = ann;
    editStyle = ann.style === 'underline' ? 'underline' : 'highlight';
    editColor = ann.color || 'green';

    var quoteEl = editor.querySelector('.ae-quote');
    quoteEl.textContent = trimQuote(ann.quote);
    editor.querySelector('textarea').value = ann.note || '';
    paintEditorControls();

    editor.classList.add('show');
    positionEditor(ann);

    if (focusNote) {
      var ta = editor.querySelector('textarea');
      setTimeout(function () { ta.focus(); }, 40);
    }
  }

  function positionEditor(ann) {
    if (!editor) return;
    var w = editor.offsetWidth;
    var h = editor.offsetHeight;
    var entry = null;
    for (var i = 0; i < markRects.length; i++) {
      if (String(markRects[i].ann.id) === String(ann.id)) { entry = markRects[i]; break; }
    }

    var left = (window.innerWidth - w) / 2;
    var top = 100;
    if (entry && entry.rects.length) {
      var rc = entry.rects[0];
      var cr = CONTENT.getBoundingClientRect();
      var target = {
        left: cr.left + rc.left - CONTENT.scrollLeft,
        top: cr.top + rc.top - CONTENT.scrollTop,
        width: rc.width,
        height: rc.height
      };
      left = target.left + target.width / 2 - w / 2;
      top = target.top + target.height + 10;
      if (top + h > window.innerHeight - 12) top = target.top - h - 10;
    }
    left = Math.min(Math.max(12, left), window.innerWidth - w - 12);
    top = Math.min(Math.max(12, top), Math.max(12, window.innerHeight - h - 12));
    editor.style.left = left + 'px';
    editor.style.top = top + 'px';
  }

  function closeEditor() {
    if (editor) editor.classList.remove('show');
    currentEditorAnn = null;
  }

  async function saveEditor() {
    if (!currentEditorAnn) return;
    var ann = currentEditorAnn;
    var note = editor.querySelector('textarea').value.trim();
    var saveBtn = editor.querySelector('[data-editor-save]');
    saveBtn.disabled = true;
    saveBtn.textContent = '保存中…';

    try {
      var rows = await rest('/rest/v1/annotations?id=eq.' + encodeURIComponent(String(ann.id)), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'Prefer': 'return=representation' },
        body: JSON.stringify({
          note: note,
          style: editStyle,
          color: editColor,
          updated_at: new Date().toISOString()
        })
      });
      var row = Array.isArray(rows) ? rows[0] : null;
      if (!row) throw httpError('未找到标注', 0);
      for (var i = 0; i < annotations.length; i++) {
        if (String(annotations[i].id) === String(ann.id)) { annotations[i] = row; break; }
      }
      saveCache();
      renderAll();
      renderDrawer();
      closeEditor();
      toast('已保存');
    } catch (e) {
      toast('保存失败：' + authErrorText(e.message), 'warn');
    } finally {
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.textContent = '保存';
      }
    }
  }

  /* ---------------- 笔记抽屉 ---------------- */
  function buildDrawer() {
    if (drawer) return;
    backdrop = el('div', 'ann-backdrop');
    backdrop.addEventListener('click', closeDrawer);

    drawer = el('aside', 'ann-drawer');
    drawer.setAttribute('aria-label', '本页笔记');
    drawer.innerHTML =
      '<div class="ann-drawer-head">' +
        '<div><div class="adh-title">本页笔记</div><div class="adh-sub" id="ann-sync">—</div></div>' +
        '<button type="button" class="ann-x" data-drawer-close aria-label="关闭">×</button>' +
      '</div>' +
      '<div class="ann-drawer-list" id="ann-list"></div>' +
      '<div class="ann-drawer-foot">' +
        '<button type="button" class="btn ghost sm" data-drawer-refresh>刷新</button>' +
      '</div>';
    document.body.appendChild(backdrop);
    document.body.appendChild(drawer);

    drawer.querySelector('[data-drawer-close]').addEventListener('click', closeDrawer);
    drawer.querySelector('[data-drawer-refresh]').addEventListener('click', function () {
      if (!session) { openAuth('login'); return; }
      setSyncStatus('同步中…');
      loadAnnotations(false);
    });

    drawer.querySelector('#ann-list').addEventListener('click', function (e) {
      if (e.target.id === 'ann-drawer-login') {
        openAuth('login');
        return;
      }
      var del = e.target.closest ? e.target.closest('.ani-del') : null;
      if (del) {
        e.stopPropagation();
        deleteAnnotation(del.getAttribute('data-del'));
        return;
      }
      var item = e.target.closest ? e.target.closest('.ann-note-item') : null;
      if (item) {
        var ann = findAnn(item.getAttribute('data-id'));
        if (ann) {
          closeDrawer();
          scrollToAnn(ann);
        }
      }
    });
  }

  function setSyncStatus(text) {
    var n = document.getElementById('ann-sync');
    if (n) n.textContent = text;
  }

  function openDrawer() {
    if (!isConfigured()) {
      toast('请先在 textbook/assets/js/supabase-config.js 填入 Supabase URL 与 anon key', 'warn');
      return;
    }
    buildDrawer();
    renderDrawer();
    backdrop.classList.add('show');
    drawer.classList.add('show');
    if (session) loadAnnotations(true);
  }

  function closeDrawer() {
    if (!drawer) return;
    drawer.classList.remove('show');
    if (backdrop) backdrop.classList.remove('show');
  }

  function renderDrawer() {
    if (!drawer) return;
    var list = drawer.querySelector('#ann-list');
    var title = drawer.querySelector('.adh-title');
    if (title) title.textContent = '本页笔记' + (annotations.length ? ' · ' + annotations.length : '');

    if (!session) {
      list.innerHTML =
        '<div class="ann-empty">登录后可查看和管理笔记。<br>账号只用于保存笔记，教材正文无需登录。<br>' +
        '<button type="button" class="btn sm" id="ann-drawer-login">登录 / 注册</button></div>';
      return;
    }

    if (!annotations.length) {
      list.innerHTML = '<div class="ann-empty">本页还没有标注。<br>选中正文文字后，点击「高亮」「下划线」或「笔记」。</div>';
      return;
    }

    var sorted = annotations.slice().sort(function (a, b) {
      if (a.start_block !== b.start_block) return a.start_block - b.start_block;
      return a.start_offset - b.start_offset;
    });

    var h = '';
    sorted.forEach(function (a) {
      var styleLabel = a.style === 'underline' ? '下划线' : '高亮';
      h += '<div class="ann-note-item" data-id="' + esc(a.id) + '">' +
        '<div class="ani-top">' +
          '<span class="ani-dot ann-c-' + esc(a.color || 'green') + '"></span>' +
          '<span class="ani-style">' + styleLabel + '</span>' +
          (a._orphan ? '<span class="ani-orphan">原文已变更</span>' : (a._hidden ? '<span class="ani-orphan">内容已折叠</span>' : '')) +
          '<button type="button" class="ani-del" data-del="' + esc(a.id) + '" aria-label="删除">×</button>' +
        '</div>' +
        '<div class="ani-quote">' + esc(trimQuote(a.quote)) + '</div>' +
        (a.note ? '<div class="ani-note">' + esc(a.note) + '</div>' : '') +
      '</div>';
    });
    list.innerHTML = h;
  }

  function scrollToAnn(ann) {
    var entry = null;
    for (var i = 0; i < markRects.length; i++) {
      if (String(markRects[i].ann.id) === String(ann.id)) { entry = markRects[i]; break; }
    }
    if (!entry || !entry.rects.length) {
      toast(ann._hidden ? '内容当前折叠或不可见，请展开后重试' : '原文位置已变化，无法定位', 'warn');
      return;
    }

    var cr = CONTENT.getBoundingClientRect();
    var rc = entry.rects[0];
    var y = window.scrollY + cr.top + rc.top - CONTENT.scrollTop - 100;
    window.scrollTo({ top: Math.max(0, y), behavior: 'smooth' });

    var marks = layer ? layer.querySelectorAll('.ann-mark[data-ann="' + String(ann.id) + '"]') : [];
    Array.prototype.forEach.call(marks, function (m) {
      m.classList.add('ann-flash');
      setTimeout(function () { m.classList.remove('ann-flash'); }, 1200);
    });
  }

  /* ---------------- 账号 UI ---------------- */
  function buildAccountUI() {
    var side = document.getElementById('sidebar');
    if (!side || document.getElementById('ann-account')) return;
    var box = el('div', 'ann-account');
    box.id = 'ann-account';
    var nav = side.querySelector('.nav-tree');
    if (nav) side.insertBefore(box, nav);
    else side.appendChild(box);
  }

  function updateAccountUI() {
    var box = document.getElementById('ann-account');
    if (!box) return;

    if (!isConfigured()) {
      box.innerHTML =
        '<div class="aa-title">云端笔记未配置</div>' +
        '<div class="aa-sub">填写 supabase-config.js 后启用</div>' +
        '<button type="button" class="btn ghost sm aa-btn" id="ann-setup">查看说明</button>';
      var setup = box.querySelector('#ann-setup');
      if (setup) setup.addEventListener('click', function () {
        toast('请编辑 textbook/assets/js/supabase-config.js，填入 Supabase 的 Project URL 与 anon public key', 'warn');
      });
      return;
    }

    if (session && session.user) {
      box.innerHTML =
        '<div class="aa-mail">' + esc(session.user.email || '已登录') + '</div>' +
        '<div class="aa-sub">笔记已按账号隔离</div>' +
        '<button type="button" class="btn ghost sm aa-btn" id="ann-logout">退出登录</button>';
      var lo = box.querySelector('#ann-logout');
      if (lo) lo.addEventListener('click', doSignOut);
      return;
    }

    box.innerHTML =
      '<div class="aa-title">登录后保存笔记</div>' +
      '<div class="aa-sub">划线、下划线与笔记按账号隔离</div>' +
      '<button type="button" class="btn sm aa-btn" id="ann-login">登录 / 注册</button>';
    var li = box.querySelector('#ann-login');
    if (li) li.addEventListener('click', function () { openAuth('login'); });
  }

  function buildNotesButton() {
    var top = document.querySelector('.topbar');
    if (!top || document.getElementById('ann-toggle')) return;
    var btn = el('button', 'ann-toggle');
    btn.id = 'ann-toggle';
    btn.type = 'button';
    btn.setAttribute('aria-label', '本页笔记');
    btn.innerHTML =
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
        '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v18H6.5A2.5 2.5 0 0 0 4 23.5z"/>' +
        '<path d="M8 7h8M8 11h8M8 15h5"/>' +
      '</svg><span class="at-label">笔记</span><span class="at-count" id="ann-count"></span>';
    var meter = top.querySelector('.read-meter');
    if (meter) top.insertBefore(btn, meter);
    else top.appendChild(btn);
    btn.addEventListener('click', openDrawer);
  }

  function updateCount() {
    var c = document.getElementById('ann-count');
    if (!c) return;
    var n = annotations.length;
    c.textContent = n ? String(n) : '';
    c.style.display = n ? '' : 'none';
  }

  function doSignOut() {
    var old = session;
    clearSession();
    annotations = [];
    closeEditor();
    closeDrawer();
    renderAll();
    renderDrawer();
    updateAccountUI();
    setSyncStatus('未登录');
    updateCount();

    if (old && old.access_token) {
      timedFetch(apiUrl('/auth/v1/logout'), {
        method: 'POST',
        headers: { 'apikey': CFG.anonKey || '', 'Authorization': 'Bearer ' + old.access_token }
      }).catch(function () {});
    }
    toast('已退出登录');
  }

  /* ---------------- 登录 / 注册弹层 ---------------- */
  function buildAuthModal() {
    if (modal) return;
    modal = el('div', 'ann-modal');
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.innerHTML =
      '<div class="ann-modal-card">' +
        '<div class="am-head"><div class="am-title" id="ann-mode-title">登录</div>' +
          '<button type="button" class="ann-x" data-auth-close aria-label="关闭">×</button></div>' +
        '<p class="am-sub">登录后，划线、下划线与笔记会按账号隔离保存在云端。</p>' +
        '<div class="am-tabs">' +
          '<button type="button" class="am-tab active" data-mode="login">登录</button>' +
          '<button type="button" class="am-tab" data-mode="signup">注册</button>' +
        '</div>' +
        '<form id="ann-form" novalidate>' +
          '<label class="am-label">邮箱<input id="ann-email" type="email" autocomplete="email" placeholder="you@example.com"></label>' +
          '<label class="am-label">密码<input id="ann-password" type="password" autocomplete="current-password" placeholder="至少 6 位"></label>' +
          '<div class="am-error" id="ann-error"></div>' +
          '<button type="submit" class="btn" id="ann-submit" style="width:100%;justify-content:center">登录</button>' +
        '</form>' +
        '<div class="am-tip">账号仅用于同步笔记；教材正文无需登录即可阅读。</div>' +
      '</div>';
    document.body.appendChild(modal);

    modal.querySelector('[data-auth-close]').addEventListener('click', function () { closeAuth(); });
    modal.addEventListener('mousedown', function (e) {
      if (e.target === modal) closeAuth();
    });
    modal.querySelectorAll('[data-mode]').forEach(function (b) {
      b.addEventListener('click', function () { setAuthMode(b.getAttribute('data-mode')); });
    });
    modal.querySelector('#ann-form').addEventListener('submit', submitAuth);
  }

  function setAuthMode(mode) {
    authMode = mode === 'signup' ? 'signup' : 'login';
    if (!modal) return;
    modal.querySelector('#ann-mode-title').textContent = authMode === 'signup' ? '创建账号' : '登录';
    modal.querySelector('#ann-submit').textContent = authMode === 'signup' ? '注册' : '登录';
    modal.querySelector('#ann-password').setAttribute(
      'autocomplete',
      authMode === 'signup' ? 'new-password' : 'current-password'
    );
    modal.querySelectorAll('[data-mode]').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-mode') === authMode);
    });
    setAuthError('');
  }

  function setAuthError(msg) {
    if (!modal) return;
    var e = modal.querySelector('#ann-error');
    if (e) e.textContent = msg || '';
  }

  function openAuth(mode, pendingAction) {
    if (!isConfigured()) {
      toast('请先在 textbook/assets/js/supabase-config.js 填入 Supabase URL 与 anon key', 'warn');
      return;
    }
    if (pendingAction) pendingAfterLogin = pendingAction;
    buildAuthModal();
    setAuthMode(mode || 'login');
    modal.classList.add('show');
    setTimeout(function () {
      var em = modal.querySelector('#ann-email');
      if (em) em.focus();
    }, 60);
  }

  function closeAuth(clearPending) {
    if (modal) {
      modal.classList.remove('show');
      var pw = modal.querySelector('#ann-password');
      if (pw) pw.value = '';
    }
    setAuthError('');
    if (clearPending !== false) pendingAfterLogin = null;
  }

  async function submitAuth(e) {
    e.preventDefault();
    if (!modal) return;
    var emailEl = modal.querySelector('#ann-email');
    var pwEl = modal.querySelector('#ann-password');
    var btn = modal.querySelector('#ann-submit');
    var email = (emailEl.value || '').trim();
    var pw = pwEl.value || '';

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setAuthError('请输入有效邮箱');
      emailEl.focus();
      return;
    }
    if (pw.length < 6) {
      setAuthError('密码至少 6 位');
      pwEl.focus();
      return;
    }

    btn.disabled = true;
    btn.textContent = authMode === 'signup' ? '注册中…' : '登录中…';
    setAuthError('');

    try {
      if (authMode === 'signup') {
        var r = await signUp(email, pw);
        if (r.session) {
          afterAuth(r.session);
        } else {
          setAuthMode('login');
          toast('确认邮件已发送，请查收后再登录');
        }
      } else {
        var s = await signIn(email, pw);
        afterAuth(s);
      }
    } catch (err) {
      setAuthError(authErrorText(err.message));
    } finally {
      btn.disabled = false;
      btn.textContent = authMode === 'signup' ? '注册' : '登录';
    }
  }

  function afterAuth(s) {
    saveSession(s);
    updateAccountUI();
    var pendingAction = pendingAfterLogin;
    pendingAfterLogin = null;
    closeAuth(false);
    toast('已登录');
    setSyncStatus('同步中…');
    loadAnnotations(true).then(function () {
      if (pendingAction) createAnnotation(pendingAction.anchor, pendingAction.style);
    });
  }

  /* ---------------- 提示 ---------------- */
  function createToastHost() {
    if (toastHost) return;
    toastHost = el('div', 'ann-toast-host');
    document.body.appendChild(toastHost);
  }

  function toast(msg, type) {
    createToastHost();
    while (toastHost.children.length >= 3) toastHost.removeChild(toastHost.firstChild);
    var t = el('div', 'ann-toast' + (type === 'warn' ? ' warn' : ''), esc(msg));
    toastHost.appendChild(t);
    requestAnimationFrame(function () { t.classList.add('show'); });
    setTimeout(function () {
      t.classList.remove('show');
      setTimeout(function () {
        if (t.parentNode) t.parentNode.removeChild(t);
      }, 250);
    }, 3200);
  }

  /* ---------------- 事件绑定 ---------------- */
  function scheduleSelectionCheck() {
    clearTimeout(selTimer);
    selTimer = setTimeout(function () {
      if (modal && modal.classList.contains('show')) return;
      if (drawer && drawer.classList.contains('show')) return;
      var anchor = selectionAnchor();
      if (!anchor) {
        hideToolbar();
        return;
      }
      pending = { anchor: anchor };
      showToolbar(anchor.rect);
    }, 40);
  }

  function bindSelection() {
    document.addEventListener('mouseup', function (e) {
      if (e.target.closest && e.target.closest('.ann-toolbar, .ann-editor, .ann-modal, .ann-drawer, .ann-account, .ann-toggle')) return;
      scheduleSelectionCheck();
    });
    document.addEventListener('touchend', function (e) {
      if (e.target.closest && e.target.closest('.ann-toolbar, .ann-editor, .ann-modal, .ann-drawer, .ann-account, .ann-toggle')) return;
      setTimeout(scheduleSelectionCheck, 180);
    }, { passive: true });
    document.addEventListener('keyup', function (e) {
      if (e.shiftKey || e.key === 'Shift' || e.key === 'ArrowLeft' || e.key === 'ArrowRight' || e.key === 'ArrowUp' || e.key === 'ArrowDown') {
        scheduleSelectionCheck();
      }
    });
    document.addEventListener('mousedown', function (e) {
      if (toolbar && toolbar.contains(e.target)) return;
      if (editor && editor.contains(e.target)) return;
      hideToolbar();
      if (editor && editor.classList.contains('show') && !editor.contains(e.target)) closeEditor();
    });
    window.addEventListener('scroll', hideToolbar, { passive: true });
    window.addEventListener('resize', hideToolbar);
  }

  function findHitAt(clientX, clientY) {
    var cr = CONTENT.getBoundingClientRect();
    var x = clientX - cr.left + CONTENT.scrollLeft;
    var y = clientY - cr.top + CONTENT.scrollTop;
    for (var i = markRects.length - 1; i >= 0; i--) {
      var m = markRects[i];
      for (var j = 0; j < m.rects.length; j++) {
        var r = m.rects[j];
        if (x >= r.left && x <= r.left + r.width && y >= r.top && y <= r.top + r.height) {
          return m.ann;
        }
      }
    }
    return null;
  }

  function bindHitTest() {
    document.addEventListener('click', function (e) {
      if (e.target.closest && e.target.closest('.ann-toolbar, .ann-editor, .ann-drawer, .ann-modal, .ann-account, .ann-toggle, .ann-backdrop')) return;
      if (e.target.closest && e.target.closest('a, button, input, textarea, select, .term, .quiz, svg')) return;

      var sel = window.getSelection();
      if (sel && !sel.isCollapsed && String(sel).trim()) return;

      var hit = findHitAt(e.clientX, e.clientY);
      if (hit) {
        openEditor(hit, false);
      } else if (editor && editor.classList.contains('show')) {
        closeEditor();
      }
    });
  }

  function bindResize() {
    window.addEventListener('resize', scheduleRepaint);
    window.addEventListener('load', scheduleRepaint);
    if (window.ResizeObserver) {
      try {
        new ResizeObserver(scheduleRepaint).observe(CONTENT);
      } catch (e) {}
    }
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(scheduleRepaint);
  }

  function bindGlobalEvents() {
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape') return;
      if (editor && editor.classList.contains('show')) { closeEditor(); return; }
      if (modal && modal.classList.contains('show')) { closeAuth(); return; }
      if (drawer && drawer.classList.contains('show')) { closeDrawer(); return; }
      hideToolbar();
    });

    window.addEventListener('online', function () {
      if (session) {
        setSyncStatus('同步中…');
        loadAnnotations(true);
      }
    });
    window.addEventListener('offline', function () {
      setSyncStatus('离线');
    });
  }

  /* ---------------- 启动 ---------------- */
  function init() {
    buildAccountUI();
    buildNotesButton();
    updateAccountUI();
    updateCount();

    if (!isConfigured()) return;

    createLayer();
    buildDrawer();
    createToolbar();
    createToastHost();
    bindGlobalEvents();
    bindSelection();
    bindHitTest();
    bindResize();

    if (session) {
      setSyncStatus('加载中…');
      loadAnnotations(true);
    } else {
      setSyncStatus('未登录');
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
