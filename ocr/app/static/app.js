(() => {
  "use strict";

  const state = {
    config: null,
    policy: null,
    health: null,
    session: null,
    selectedIds: [],
    jobId: null,
    progress: null,
    result: null,
    activeDocId: null,
    dirty: false,
    pollTimer: null,
    uploading: false,
    running: false,
  };

  const $ = (selector) => document.querySelector(selector);
  const el = {
    dropzone: $("#dropzone"),
    fileInput: $("#file-input"),
    gallery: $("#gallery"),
    emptyState: $("#empty-state"),
    fileCounter: $("#file-counter"),
    maxMb: $("#max-mb"),
    uploadProgress: $("#upload-progress"),
    uploadBar: $("#upload-progress .bar i"),
    consent: $("#consent"),
    mode: $("#mode-select"),
    review: $("#review-select"),
    start: $("#start-btn"),
    resume: $("#resume-btn"),
    progressBlock: $("#progress-block"),
    progressStage: $("#progress-stage"),
    progressNumber: $("#progress-number"),
    progressBar: $("#progress-bar"),
    progressChunks: $("#progress-chunks"),
    progressRequests: $("#progress-requests"),
    jobErrors: $("#job-errors"),
    resultCard: $("#result-card"),
    resultBadges: $("#result-badges"),
    resultTabs: $("#result-tabs"),
    editor: $("#result-editor"),
    editorMeta: $("#editor-meta"),
    copy: $("#copy-btn"),
    save: $("#save-btn"),
    insights: $("#insights"),
    chunkDetails: $("#chunk-details"),
    chunkList: $("#chunk-list"),
    policyBanner: $("#policy-banner"),
    refreshPolicy: $("#refresh-policy"),
    keyBanner: $("#key-banner"),
    pillKey: $("#pill-key"),
    pillPolicy: $("#pill-policy"),
    footerUsage: $("#footer-usage"),
    toast: $("#toast"),
  };

  const FIELD_LABELS = {
    brand: "品牌",
    product_name: "商品名称",
    fabric_composition: "面料成分",
    size: "尺码 / 尺寸",
    size_chart: "尺码参数行",
    sku: "型号 / SKU",
    wash_instruction: "洗涤说明",
    standard: "执行标准",
    safety_category: "安全类别",
    price: "价格",
    packaging: "包装 / 数量",
  };

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function toast(message, bad = false) {
    el.toast.textContent = message;
    el.toast.classList.toggle("bad", bad);
    el.toast.classList.add("show");
    window.clearTimeout(toast._timer);
    toast._timer = window.setTimeout(() => el.toast.classList.remove("show"), 2600);
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      headers: options.body instanceof FormData ? {} : { "Content-Type": "application/json" },
      ...options,
    });
    let payload = null;
    const text = await response.text();
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = text;
      }
    }
    if (!response.ok) {
      let detail = payload && payload.detail ? payload.detail : payload || response.statusText;
      if (Array.isArray(detail)) detail = detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
      if (typeof detail === "object") detail = JSON.stringify(detail);
      throw new Error(`${response.status} ${detail}`);
    }
    return payload;
  }

  function formatDate(iso) {
    if (!iso) return "未知";
    try {
      return new Date(iso).toLocaleString("zh-CN", { hour12: false });
    } catch {
      return iso;
    }
  }

  function setPill(node, text, cls) {
    node.textContent = text;
    node.className = `pill ${cls}`;
  }

  async function loadConfig() {
    state.config = await api("/api/config");
    el.maxMb.textContent = String(state.config.max_upload_mb);
    el.mode.value = state.config.prompt_mode;
    el.review.value = state.config.review_enabled ? "true" : "false";
    el.consent.checked = false;
    el.keyBanner.classList.toggle("hidden", Boolean(state.config.api_key_configured));
    setPill(
      el.pillKey,
      state.config.api_key_configured ? "密钥已配置" : "未配置密钥",
      state.config.api_key_configured ? "pill-ok" : "pill-warn"
    );
    updateCounter();
  }

  async function loadPolicy(refresh = false) {
    const suffix = refresh ? "?refresh=true" : "";
    const policy = await api(`/api/policy${suffix}`);
    state.policy = policy;
    const models = Object.values(policy.models || {});
    const allFree = models.length > 0 && models.every((item) => item.free);
    const fresh = Boolean(policy.snapshot_fresh);
    const bannerClass = allFree && fresh ? "ok" : allFree ? "warn" : "bad";
    el.policyBanner.className = `policy-banner ${bannerClass}`;
    const rendered = models
      .map((item) => {
        const registered = item.registered === false ? "未注册" : item.free ? "免费已核实" : "未确认免费";
        return `<span class="tag ${item.free ? "tag-ok" : "tag-bad"}">${escapeHtml(registered)}</span>
          <span class="mono-inline">${escapeHtml(item.model_id)}</span>`;
      })
      .join("<br>");
    const statusText = !allFree
      ? "存在未确认免费的模型，云端调用将被阻止"
      : fresh
        ? "免费状态已核实，云端调用受白名单与额度保护"
        : `快照已过期（${policy.max_snapshot_age_hours} 小时上限），云端调用将被阻止`;
    el.policyBanner.innerHTML = `
      <div class="policy-main">
        <strong>${escapeHtml(statusText)}</strong>
        <span class="muted">快照时间：${escapeHtml(formatDate(policy.checked_at))} · 来源：官方定价页</span>
        <span class="muted">${rendered}</span>
      </div>
      <button class="btn btn-ghost btn-sm" id="refresh-policy-inline" type="button">刷新校验</button>`;
    $("#refresh-policy-inline").addEventListener("click", () => refreshPolicy());
    setPill(
      el.pillPolicy,
      allFree && fresh ? "免费策略已核实" : allFree ? "快照过期" : "调用已阻止",
      allFree && fresh ? "pill-ok" : allFree ? "pill-warn" : "pill-bad"
    );
  }

  async function refreshPolicy() {
    el.refreshPolicy.disabled = true;
    el.refreshPolicy.textContent = "校验中…";
    try {
      await loadPolicy(true);
      toast("免费状态已从官方定价页刷新");
    } catch (error) {
      toast(`刷新失败：${error.message}`, true);
    } finally {
      el.refreshPolicy.disabled = false;
      el.refreshPolicy.textContent = "刷新校验";
    }
  }

  async function loadHealth() {
    try {
      state.health = await api("/api/health");
      const daily = state.health.daily_usage || {};
      el.footerUsage.textContent = `今日云端请求 ${daily.attempts || 0} / ${
        state.config.max_requests_per_day
      } · 缓存 ${state.health.cache ? state.health.cache.entries : 0} 条`;
    } catch {
      /* health is informational */
    }
  }

  function updateCounter() {
    const max = state.config ? state.config.max_files : 12;
    el.fileCounter.textContent = `${state.selectedIds.length} / ${max}`;
    const empty = state.selectedIds.length === 0;
    el.emptyState.classList.toggle("hidden", !empty);
    el.start.disabled = state.running || state.uploading || empty;
  }

  function renderGallery() {
    el.gallery.querySelectorAll(".thumb").forEach((node) => node.remove());
    el.emptyState.classList.toggle("hidden", state.selectedIds.length > 0);
    const byId = new Map((state.session ? state.session.images : []).map((item) => [item.image_id, item]));
    state.selectedIds.forEach((imageId, index) => {
      const info = byId.get(imageId);
      if (!info) return;
      const long = info.height / Math.max(1, info.width) > 2.2;
      const card = document.createElement("div");
      card.className = `thumb${long ? " long" : ""}`;
      card.innerHTML = `
        <span class="thumb-order">${index + 1}</span>
        <img src="${info.preview_url}" alt="${escapeHtml(info.filename)}" loading="lazy" />
        <div class="thumb-body">
          <div class="thumb-name" title="${escapeHtml(info.filename)}">${escapeHtml(info.filename)}</div>
          <div class="thumb-meta">${info.width} × ${info.height}${long ? " · 长图" : ""}</div>
          <div class="thumb-actions">
            <button class="icon-btn" data-move="-1" aria-label="上移">↑</button>
            <button class="icon-btn" data-move="1" aria-label="下移">↓</button>
            <button class="icon-btn" data-remove="1" aria-label="移除">移除</button>
          </div>
        </div>`;
      card.querySelector("[data-move='-1']").disabled = index === 0;
      card.querySelector("[data-move='1']").disabled = index === state.selectedIds.length - 1;
      card.querySelector("[data-move='-1']").addEventListener("click", () => moveImage(index, -1));
      card.querySelector("[data-move='1']").addEventListener("click", () => moveImage(index, 1));
      card.querySelector("[data-remove='1']").addEventListener("click", () => removeImage(imageId));
      el.gallery.appendChild(card);
    });
    updateCounter();
  }

  function moveImage(index, delta) {
    if (state.running) return;
    const target = index + delta;
    if (target < 0 || target >= state.selectedIds.length) return;
    const [item] = state.selectedIds.splice(index, 1);
    state.selectedIds.splice(target, 0, item);
    renderGallery();
  }

  function removeImage(imageId) {
    if (state.running) return;
    state.selectedIds = state.selectedIds.filter((id) => id !== imageId);
    renderGallery();
  }

  function uploadFiles(files) {
    if (state.uploading || state.running) return;
    const incoming = Array.from(files || []).filter((file) =>
      ["image/png", "image/jpeg", "image/webp"].includes(file.type) ||
      /\.(png|jpg|jpeg|webp)$/i.test(file.name)
    );
    if (!incoming.length) {
      toast("请选择 PNG、JPEG 或 WebP 图片", true);
      return;
    }
    const max = state.config ? state.config.max_files : 12;
    const currentCount = state.session ? state.session.images.length : 0;
    if (currentCount + incoming.length > max) {
      toast(`每个会话最多 ${max} 张图片`, true);
      return;
    }
    const form = new FormData();
    incoming.forEach((file) => form.append("files", file, file.name));
    state.uploading = true;
    el.uploadProgress.classList.remove("hidden");
    el.uploadBar.style.width = "8%";
    updateCounter();

    const url = state.session
      ? `/api/sessions/${state.session.session_id}/images`
      : "/api/sessions";
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.responseType = "json";
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        const percent = Math.max(8, Math.round((event.loaded / event.total) * 100));
        el.uploadBar.style.width = `${Math.min(96, percent)}%`;
      }
    };
    xhr.onload = () => {
      state.uploading = false;
      el.uploadProgress.classList.add("hidden");
      el.uploadBar.style.width = "0";
      if (xhr.status >= 200 && xhr.status < 300) {
        state.session = xhr.response;
        state.selectedIds = state.session.images.map((item) => item.image_id);
        renderGallery();
        updateCounter();
        toast(`已添加 ${incoming.length} 张图片`);
      } else {
        const payload = xhr.response;
        const detail = payload && typeof payload === "object"
          ? payload.detail || JSON.stringify(payload)
          : payload || xhr.statusText;
        toast(`上传失败：${detail}`, true);
        updateCounter();
      }
    };
    xhr.onerror = () => {
      state.uploading = false;
      el.uploadProgress.classList.add("hidden");
      toast("上传网络错误", true);
      updateCounter();
    };
    xhr.send(form);
  }

  async function startJob() {
    if (state.running || state.uploading) return;
    if (!state.session || !state.selectedIds.length) {
      toast("请先上传图片", true);
      return;
    }
    if (!el.consent.checked) {
      toast("请先确认云端上传授权", true);
      el.consent.focus();
      return;
    }
    state.running = true;
    state.result = null;
    state.activeDocId = null;
    state.dirty = false;
    el.resultCard.classList.add("hidden");
    updateCounter();
    el.start.disabled = true;
    el.progressBlock.classList.remove("hidden");
    setProgress({ progress: 0, stage: "queued", completed_chunks: 0, total_chunks: 0, api_requests: 0 });
    el.jobErrors.innerHTML = "";
    try {
      const payload = {
        session_id: state.session.session_id,
        image_order: state.selectedIds,
        mode: el.mode.value,
        consent_cloud_upload: true,
        use_review: el.review.value === "true",
        use_cache: true,
      };
      const response = await api("/api/ocr/jobs", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      state.jobId = response.job_id;
      pollJob();
    } catch (error) {
      state.running = false;
      updateCounter();
      toast(`无法开始识别：${error.message}`, true);
      el.jobErrors.innerHTML = `<div class="error-item">${escapeHtml(error.message)}</div>`;
    }
  }

  function setProgress(progress) {
    state.progress = progress;
    const percent = Math.round((progress.progress || 0) * 100);
    el.progressBar.style.width = `${percent}%`;
    el.progressNumber.textContent = `${percent}%`;
    const stageMap = {
      queued: "排队中",
      ocr: "正在识别分块",
      merge: "合并与去重",
      done: "完成",
      blocked: "已阻止",
      failed: "失败",
      budget_stopped: "额度保护停止",
    };
    el.progressStage.textContent = stageMap[progress.stage] || progress.stage || "处理中";
    el.progressChunks.textContent = `分块 ${progress.completed_chunks || 0} / ${progress.total_chunks || 0}`;
    el.progressRequests.textContent = `云端请求 ${progress.api_requests || 0}`;
    const errors = progress.errors || [];
    el.jobErrors.innerHTML = errors
      .map((item) => `<div class="error-item">${escapeHtml(item)}</div>`)
      .join("");
  }

  async function pollJob() {
    window.clearTimeout(state.pollTimer);
    if (!state.jobId) return;
    try {
      const progress = await api(`/api/ocr/jobs/${state.jobId}`);
      setProgress(progress);
      const terminal = ["completed", "partial", "failed", "blocked"].includes(progress.status);
      if (terminal) {
        state.running = false;
        updateCounter();
        el.resume.classList.toggle("hidden", progress.status === "completed");
        if (progress.result_available) await loadResult();
        loadHealth();
        return;
      }
      state.pollTimer = window.setTimeout(pollJob, 1200);
    } catch (error) {
      state.running = false;
      updateCounter();
      toast(`轮询失败：${error.message}`, true);
    }
  }

  async function resumeJob() {
    if (!state.jobId || state.running) return;
    state.running = true;
    updateCounter();
    try {
      await api(`/api/ocr/jobs/${state.jobId}/resume`, { method: "POST" });
      el.resume.classList.add("hidden");
      pollJob();
    } catch (error) {
      state.running = false;
      updateCounter();
      toast(`继续失败：${error.message}`, true);
    }
  }

  async function loadResult() {
    const result = await api(`/api/ocr/jobs/${state.jobId}/result`);
    state.result = result;
    state.dirty = false;
    state.activeDocId = state.activeDocId && result.images.some((image) => image.image_id === state.activeDocId)
      ? state.activeDocId
      : result.images[0] ? result.images[0].image_id : null;
    renderResult();
  }

  function activeImage() {
    if (!state.result) return null;
    return state.result.images.find((image) => image.image_id === state.activeDocId) || null;
  }

  function renderResult() {
    const result = state.result;
    if (!result) return;
    el.resultCard.classList.remove("hidden");
    const totalChars = (result.text || "").replace(/\s+/g, "").length;
    const statusMap = {
      completed: ["已完成", "tag-ok"],
      partial: ["部分完成", "tag-warn"],
      failed: ["失败", "tag-bad"],
      blocked: ["已阻止", "tag-bad"],
      running: ["进行中", "tag-muted"],
    };
    const [label, cls] = statusMap[result.status] || ["未知", "tag-muted"];
    el.resultBadges.innerHTML = `
      <span class="tag ${cls}">${label}</span>
      <span class="tag ${result.needs_manual_check ? "tag-warn" : "tag-ok"}">${
        result.needs_manual_check ? "需人工核验" : "未发现需核验项"
      }</span>
      <span class="tag tag-muted">${totalChars} 字</span>
      <span class="tag tag-muted">请求 ${result.api_requests || 0}</span>`;

    renderTabs();
    renderEditor();
    renderInsights();
    renderChunks();
    el.resume.classList.toggle(
      "hidden",
      !["partial", "failed", "blocked"].includes(result.status)
    );

    if (result.edited) el.editorMeta.textContent += " · 已编辑";
  }

  function renderTabs() {
    el.resultTabs.innerHTML = "";
    (state.result.images || []).forEach((image, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.role = "tab";
      button.className = `tab${image.image_id === state.activeDocId ? " active" : ""}`;
      button.innerHTML = `图片 ${index + 1} · ${escapeHtml(image.filename)}${
        image.needs_manual_check ? '<span class="flag"></span>' : ""
      }`;
      button.addEventListener("click", () => switchTab(image.image_id));
      el.resultTabs.appendChild(button);
    });
  }

  async function switchTab(imageId) {
    if (imageId === state.activeDocId) return;
    if (state.dirty) {
      await saveEdits(true);
    }
    state.activeDocId = imageId;
    renderTabs();
    renderEditor();
    renderInsights();
    renderChunks();
  }

  function renderEditor() {
    const image = activeImage();
    el.editor.value = image ? image.text || "" : "";
    updateEditorMeta();
  }

  function updateEditorMeta() {
    const chars = el.editor.value.replace(/\s+/g, "").length;
    el.editorMeta.textContent = `${chars} 字符`;
    if (state.dirty) el.editorMeta.textContent += " · 未保存";
  }

  function renderInsights() {
    const image = activeImage();
    if (!image || !state.result) {
      el.insights.innerHTML = "";
      return;
    }
    const fieldRows = (image.key_fields || [])
      .map((field) => {
        const confidenceMap = {
          cross_checked: ["多处一致", "tag-ok"],
          conflict: ["冲突", "tag-bad"],
          unverified: ["未复核", "tag-muted"],
        };
        const [label, cls] = confidenceMap[field.confidence] || ["未复核", "tag-muted"];
        return `<tr>
          <th>${escapeHtml(FIELD_LABELS[field.name] || field.name)}</th>
          <td>${escapeHtml(field.value)}</td>
          <td><span class="tag ${cls}">${label}</span></td>
          <td class="muted">${escapeHtml(field.note || "")}</td>
        </tr>`;
      })
      .join("");
    const warningNotes = (image.warnings || [])
      .map((item) => `<div class="note warn">${escapeHtml(item)}</div>`)
      .join("");
    const errorNotes = (image.errors || [])
      .map((item) => `<div class="note bad">${escapeHtml(item)}</div>`)
      .join("");
    const chunkCount = (image.chunks || []).length;
    const reviewed = (image.chunks || []).filter((chunk) => chunk.reviewed).length;
    const cached = (image.chunks || []).filter((chunk) => chunk.from_cache).length;
    el.insights.innerHTML = `
      <div class="insight-block">
        <h3>关键字段</h3>
        ${
          fieldRows
            ? `<table class="kv-table"><thead><tr><th>字段</th><th>识别值</th><th>状态</th><th>说明</th></tr></thead><tbody>${fieldRows}</tbody></table>`
            : '<div class="muted">未识别到品牌、成分、尺码、型号、标准、价格等结构化字段。请直接核对正文。</div>'
        }
      </div>
      <div class="insight-block">
        <h3>质量与审计</h3>
        <div class="notes">
          <div class="note">分块 ${chunkCount} 个 · 已复核 ${reviewed} 个 · 缓存命中 ${cached} 个 · 重叠去重移除 ${image.overlap_removed_lines || 0} 行</div>
          <div class="note">模型置信度：云端接口未返回时为“未知”，不以启发式质量分冒充。</div>
          ${warningNotes}${errorNotes}
        </div>
      </div>`;
  }

  function renderChunks() {
    const image = activeImage();
    if (!image) {
      el.chunkList.innerHTML = "";
      return;
    }
    el.chunkList.innerHTML = "";
    (image.chunks || []).forEach((chunk) => {
      const node = document.createElement("div");
      node.className = "chunk";
      const confidence =
        chunk.confidence == null ? "未知（接口未返回）" : Number(chunk.confidence).toFixed(3);
      const tags = [
        chunk.reviewed ? '<span class="tag tag-ok">已复核</span>' : '<span class="tag tag-muted">未复核</span>',
        chunk.from_cache ? '<span class="tag tag-muted">缓存</span>' : "",
        chunk.needs_review ? '<span class="tag tag-warn">需核验</span>' : "",
        chunk.suspected_hallucination
          ? '<span class="tag tag-bad">疑似编造，已排除</span>'
          : "",
        chunk.forced_cut ? '<span class="tag tag-bad">强制切分</span>' : "",
        chunk.layout_method ? `<span class="tag tag-ok">布局 ${escapeHtml(chunk.layout_method)}</span>` : "",
        chunk.selected_mode === "markdown" ? '<span class="tag tag-ok">Markdown 布局</span>' : "",
        chunk.manual_override
          ? `<span class="tag tag-warn">已人工采用${
              chunk.override_source === "alternate" ? "备选" : "复核"
            }文本</span>`
          : "",
        chunk.error ? '<span class="tag tag-bad">错误</span>' : "",
      ].join(" ");
      node.innerHTML = `
        <div class="chunk-head">
          <span>#${chunk.index} · y ${chunk.y0}-${chunk.y1}px · ${escapeHtml(chunk.engine || "未识别")}</span>
          <span>缩放 ${Number(chunk.scale || 1).toFixed(2)} · 质量分 ${chunk.quality_score ?? "—"} · 置信度 ${confidence}</span>
        </div>
        <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap">${tags}</div>
        <div class="chunk-text">${escapeHtml(chunk.text || "（空）")}</div>
        ${
          chunk.conflicts && chunk.conflicts.length
            ? chunk.conflicts
                .map(
                  (conflict) => `<div class="conflict"><strong>${escapeHtml(conflict.kind)}</strong>：${escapeHtml(
                    conflict.detail
                  )}</div>`
                )
                .join("")
            : ""
        }
        ${
          chunk.review_text
            ? `<details style="margin-top:8px"><summary class="muted">查看复核文本（${escapeHtml(
                chunk.review_engine || "复核模型"
              )}）</summary>
                <div class="chunk-text">${escapeHtml(chunk.review_text)}</div>
                <div class="tool-actions" style="margin-top:8px">
                  ${
                    chunk.manual_override
                      ? '<button class="btn btn-ghost btn-sm" data-apply-primary="1" type="button">恢复主模型文本</button>'
                      : '<button class="btn btn-primary btn-sm" data-apply-review="1" type="button">采用复核文本</button>'
                  }
                </div></details>`
            : ""
        }
        ${
          chunk.layout_blocks && chunk.layout_blocks.length
            ? `<details style="margin-top:8px"><summary class="muted">布局块 ${chunk.layout_blocks.length} 个（原图坐标）</summary>
                <div class="chunk-text">${chunk.layout_blocks
                  .map(
                    (block) =>
                      `[${escapeHtml(block.label)} ${escapeHtml(
                        block.bbox.map((value) => Math.round(value)).join(", ")
                      )}] ${escapeHtml(block.text)}`
                  )
                  .join("\n")}</div></details>`
            : ""
        }
        ${
          chunk.alternate_text
            ? `<details style="margin-top:8px"><summary class="muted">查看备选文本（${escapeHtml(
                chunk.alternate_mode === "markdown" ? "Markdown/grounding" : "主模型纯文字"
              )}${chunk.selection_reason ? ` · ${escapeHtml(chunk.selection_reason)}` : ""}）</summary>
                <div class="chunk-text">${escapeHtml(chunk.alternate_text)}</div>
                <div class="tool-actions" style="margin-top:8px">
                  ${
                    chunk.manual_override
                      ? '<button class="btn btn-ghost btn-sm" data-apply-primary="1" type="button">恢复采用前文本</button>'
                      : `<button class="btn btn-primary btn-sm" data-apply-alternate="1" type="button">采用备选文本</button>`
                  }
                </div></details>`
            : ""
        }`;
      el.chunkList.appendChild(node);
      const reviewButton = node.querySelector("[data-apply-review]");
      if (reviewButton) {
        reviewButton.addEventListener("click", () =>
          applyChunkText(image.image_id, chunk.index, "review")
        );
      }
      const alternateButton = node.querySelector("[data-apply-alternate]");
      if (alternateButton) {
        alternateButton.addEventListener("click", () =>
          applyChunkText(image.image_id, chunk.index, "alternate")
        );
      }
      const primaryButton = node.querySelector("[data-apply-primary]");
      if (primaryButton) {
        primaryButton.addEventListener("click", () =>
          applyChunkText(image.image_id, chunk.index, "primary")
        );
      }
    });
  }

  async function applyChunkText(imageId, chunkIndex, source) {
    if (!state.jobId) return;
    const action =
      source === "review"
        ? "采用复核文本"
        : source === "alternate"
          ? "采用备选文本"
          : "恢复采用前文本";
    if (
      !window.confirm(
        `${action}会基于所有分块重新生成该图片文字，可能覆盖当前整段人工编辑。是否继续？`
      )
    ) {
      return;
    }
    try {
      const updated = await api(`/api/ocr/jobs/${state.jobId}/chunks/apply`, {
        method: "POST",
        body: JSON.stringify({
          image_id: imageId,
          chunk_index: chunkIndex,
          source,
        }),
      });
      state.result = updated;
      state.dirty = false;
      state.activeDocId = imageId;
      renderResult();
      toast(
        source === "review"
          ? "已采用复核文本"
          : source === "alternate"
            ? "已采用备选文本"
            : "已恢复采用前文本"
      );
    } catch (error) {
      toast(`${action}失败：${error.message}`, true);
    }
  }

  async function saveEdits(silent = false) {
    const image = activeImage();
    if (!image || !state.result) return;
    image.text = el.editor.value;
    const documents = state.result.images.map((item) => ({ image_id: item.image_id, text: item.text }));
    try {
      const updated = await api(`/api/ocr/jobs/${state.jobId}/result`, {
        method: "PUT",
        body: JSON.stringify({ documents }),
      });
      state.result = updated;
      state.dirty = false;
      state.result.edited = true;
      if (!silent) toast("编辑已保存");
      renderResult();
      loadHealth();
    } catch (error) {
      toast(`保存失败：${error.message}`, true);
    }
  }

  async function copyText() {
    const text = el.editor.value;
    try {
      await navigator.clipboard.writeText(text);
      toast("已复制当前文本");
    } catch {
      const temp = document.createElement("textarea");
      temp.value = text;
      document.body.appendChild(temp);
      temp.select();
      document.execCommand("copy");
      temp.remove();
      toast("已复制当前文本");
    }
  }

  async function exportResult(format) {
    if (!state.result || !state.jobId) return;
    if (state.dirty) await saveEdits(true);
    const anchor = document.createElement("a");
    anchor.href = `/api/ocr/jobs/${state.jobId}/export?format=${format}`;
    anchor.download = "";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  }

  function bindEvents() {
    el.dropzone.addEventListener("click", () => el.fileInput.click());
    el.dropzone.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        el.fileInput.click();
      }
    });
    el.fileInput.addEventListener("change", (event) => {
      uploadFiles(event.target.files);
      event.target.value = "";
    });
    ["dragenter", "dragover"].forEach((name) => {
      el.dropzone.addEventListener(name, (event) => {
        event.preventDefault();
        el.dropzone.classList.add("dragging");
      });
    });
    ["dragleave", "drop"].forEach((name) => {
      el.dropzone.addEventListener(name, (event) => {
        event.preventDefault();
        el.dropzone.classList.remove("dragging");
      });
    });
    el.dropzone.addEventListener("drop", (event) => {
      if (event.dataTransfer && event.dataTransfer.files) uploadFiles(event.dataTransfer.files);
    });
    el.start.addEventListener("click", startJob);
    el.resume.addEventListener("click", resumeJob);
    el.refreshPolicy.addEventListener("click", refreshPolicy);
    el.copy.addEventListener("click", copyText);
    el.save.addEventListener("click", () => saveEdits(false));
    el.editor.addEventListener("input", () => {
      state.dirty = true;
      updateEditorMeta();
    });
    el.editor.addEventListener("blur", () => {
      if (state.dirty) saveEdits(true);
    });
    document.querySelectorAll("[data-export]").forEach((button) => {
      button.addEventListener("click", () => exportResult(button.dataset.export));
    });
    el.consent.addEventListener("change", () => {
      if (el.consent.checked) toast("已确认云端上传授权");
    });
  }

  async function init() {
    bindEvents();
    try {
      await loadConfig();
      await loadPolicy();
      await loadHealth();
      renderGallery();
    } catch (error) {
      toast(`初始化失败：${error.message}`, true);
    }
    window.addEventListener("beforeunload", (event) => {
      if (state.dirty) {
        event.preventDefault();
        event.returnValue = "";
      }
    });
  }

  init();
})();
