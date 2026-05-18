const APP_VERSION = "0.3.7";

const app = document.getElementById("app");
const state = {
  view: initialViewFromLocation(),
  selectedDate: initialDateFromLocation(),
  editingDate: initialEditDateFromLocation(),
  selectedImpressionName: initialImpressionFromLocation(),
  bootstrap: null,
  diary: { items: [], archive: [], selected: null, loaded: false },
  search: { query: initialSearchFromLocation(), results: [], backend: "" },
  impressions: [],
  selectedImpression: null,
  media: [],
  settings: null,
  notice: "",
  error: "",
  rendered: new Set(),
};

const navItems = [
  ["dashboard", "首页", "Home"],
  ["diary", "日记", "Entries"],
  ["write", "写入", "Write"],
  ["search", "检索", "Recall"],
  ["impressions", "印象", "People"],
  ["media", "媒体", "Media"],
  ["settings", "设置", "Config"],
];

function initialViewFromLocation() {
  const path = window.location.pathname;
  if (path.startsWith("/diary")) return "diary";
  if (path === "/write") return "write";
  if (path === "/search") return "search";
  if (path === "/impressions") return "impressions";
  if (path === "/media") return "media";
  if (path === "/settings") return "settings";
  return "dashboard";
}

function initialDateFromLocation() {
  const path = window.location.pathname;
  if (!path.startsWith("/diary/")) return "";
  return decodeURIComponent(path.split("/").filter(Boolean).pop() || "");
}

function initialEditDateFromLocation() {
  if (window.location.pathname !== "/write") return "";
  return new URLSearchParams(window.location.search).get("date") || "";
}

function initialSearchFromLocation() {
  if (window.location.pathname !== "/search") return "";
  return new URLSearchParams(window.location.search).get("q") || "";
}

function initialImpressionFromLocation() {
  if (window.location.pathname !== "/impressions") return "";
  return new URLSearchParams(window.location.search).get("name") || "";
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (response.status === 401) {
    location.href = "/login";
    return null;
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  return response.json();
}

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function splitWords(value = "") {
  return String(value)
    .replace(/[，、；;]/g, ",")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function ensureShell() {
  if (document.getElementById("view-diary")) return;
  app.innerHTML = `
    <div class="app" data-app-version="${APP_VERSION}">
      <aside class="nav">
        <button class="brand" data-view="dashboard" type="button">
          <span class="brand-mark" id="brand-mark">窝</span>
          <span><strong id="brand-title">小窝</strong><small>Private Nest</small></span>
        </button>
        <nav class="nav-links">
          ${navItems.map(([key, label, meta]) => `<button class="nav-link" data-nav="${key}" data-view="${key}" type="button">${label}<span>${meta}</span></button>`).join("")}
        </nav>
        <div class="nav-footer">
          <div id="app-version"></div>
          <div id="search-backend"></div>
        </div>
      </aside>
      <main class="main" id="view">
        <div id="notice-slot"></div>
        <section class="view-panel" id="view-dashboard" data-panel="dashboard"></section>
        <section class="view-panel" id="view-diary" data-panel="diary"></section>
        <section class="view-panel" id="view-write" data-panel="write"></section>
        <section class="view-panel" id="view-search" data-panel="search"></section>
        <section class="view-panel" id="view-impressions" data-panel="impressions"></section>
        <section class="view-panel" id="view-media" data-panel="media"></section>
        <section class="view-panel" id="view-settings" data-panel="settings"></section>
      </main>
    </div>
  `;
}

function panel(name) {
  return document.getElementById(`view-${name}`);
}

function updateShell() {
  ensureShell();
  const siteTitle = currentSiteTitle();
  const avatarUrl = currentAvatarUrl();
  document.title = siteTitle;
  const brandTitle = document.getElementById("brand-title");
  if (brandTitle) brandTitle.textContent = siteTitle;
  const brandMark = document.getElementById("brand-mark");
  if (brandMark) {
    brandMark.innerHTML = avatarUrl
      ? `<img src="${escapeHtml(avatarUrl)}" alt="${escapeHtml(siteTitle)}">`
      : `${escapeHtml(siteTitle.slice(0, 1) || "窝")}`;
  }
  document.querySelectorAll("[data-nav]").forEach((node) => node.classList.toggle("active", node.dataset.nav === state.view));
  document.querySelectorAll("[data-panel]").forEach((node) => {
    node.hidden = node.dataset.panel !== state.view;
  });
  const versionNode = document.getElementById("app-version");
  if (versionNode) versionNode.textContent = `服务 v${state.bootstrap?.version || ""} · 前端 ${APP_VERSION}`;
  const backendNode = document.getElementById("search-backend");
  if (backendNode) backendNode.textContent = state.bootstrap?.search?.backend || "local index";
  const notice = document.getElementById("notice-slot");
  notice.innerHTML = `
    ${state.notice ? `<div class="notice">${escapeHtml(state.notice)}</div>` : ""}
    ${state.error ? `<div class="notice error">${escapeHtml(state.error)}</div>` : ""}
  `;
}

function currentSiteTitle() {
  return state.bootstrap?.settings?.site_title || state.settings?.settings?.site_title || "小窝";
}

function currentAvatarUrl() {
  return state.bootstrap?.settings?.brand_avatar_url || state.settings?.settings?.brand_avatar_url || "";
}

function pageHead(eyebrow, title, actions = "") {
  return `
    <header class="topbar">
      <div class="page-title"><p>${escapeHtml(eyebrow)}</p><h1>${escapeHtml(title)}</h1></div>
      <div class="actions">${actions}</div>
    </header>
  `;
}

async function loadBootstrap() {
  if (!state.bootstrap) state.bootstrap = await api("/api/ui/bootstrap");
}

async function setView(view, options = {}) {
  state.view = view;
  state.notice = options.keepNotice ? state.notice : "";
  state.error = "";
  if (Object.prototype.hasOwnProperty.call(options, "date")) state.selectedDate = options.date || "";
  if (Object.prototype.hasOwnProperty.call(options, "editDate")) state.editingDate = options.editDate || "";
  if (Object.prototype.hasOwnProperty.call(options, "query")) state.search.query = options.query || "";
  await loadView();
}

document.addEventListener(
  "click",
  (event) => {
    const target = event.target.closest("[data-view], [data-date], [data-edit-date], [data-search-query], [data-impression-name], [data-new-impression]");
    if (!target) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    event.stopPropagation();
    if (target.dataset.view) {
      setView(target.dataset.view);
      return;
    }
    if (target.dataset.date) {
      selectDiary(target.dataset.date);
      return;
    }
    if (target.dataset.editDate) {
      setView("write", { editDate: target.dataset.editDate });
      return;
    }
    if (target.dataset.searchQuery) {
      setView("search", { query: target.dataset.searchQuery });
      return;
    }
    if (target.dataset.impressionName) {
      selectImpression(target.dataset.impressionName);
      return;
    }
    if (target.dataset.newImpression !== undefined) {
      newImpression();
    }
  },
  true
);

async function loadView() {
  try {
    ensureShell();
    await loadBootstrap();
    if (state.view === "dashboard") renderDashboard();
    if (state.view === "diary") await renderDiary();
    if (state.view === "write") await renderWrite();
    if (state.view === "search") await renderSearch();
    if (state.view === "impressions") await renderImpressions();
    if (state.view === "media") await renderMedia();
    if (state.view === "settings") await renderSettings();
    updateShell();
  } catch (err) {
    state.error = err.message;
    updateShell();
    panel(state.view).innerHTML = `<div class="loading">加载失败：${escapeHtml(err.message)}</div>`;
  }
}

function renderDashboard() {
  const target = panel("dashboard");
  const stats = state.bootstrap.stats;
  const recent = state.bootstrap.recent_entries || [];
  const siteTitle = currentSiteTitle();
  target.innerHTML = `
    <section class="home-hero">
      <div class="home-hero-copy">
        <p class="eyebrow">Private Nest</p>
        <h1>${escapeHtml(siteTitle)}</h1>
        <p class="home-lead">把今天安放好，旧事也能被轻轻找回来。</p>
        <div class="home-actions">
          <button class="button primary" data-view="write" type="button">写日记</button>
          <button class="button" data-view="diary" type="button">看日记</button>
          <button class="button ghost" data-view="search" type="button">检索回忆</button>
        </div>
      </div>
      <div class="home-status">
        <div class="home-stat"><span>日记</span><strong>${stats.entries}</strong></div>
        <div class="home-stat"><span>媒体</span><strong>${stats.media}</strong></div>
        <div class="home-stat"><span>人物印象</span><strong>${stats.people}</strong></div>
        <div class="home-status-foot">
          <span>${escapeHtml(state.bootstrap.search.backend)}</span>
          <span>v${escapeHtml(state.bootstrap.version || APP_VERSION)}</span>
        </div>
      </div>
    </section>
    <section class="home-grid">
      <article class="card">
        <div class="card-head"><h2>最近日记</h2><button class="text-button" data-view="diary" type="button">查看全部</button></div>
        <div class="list">${recent.map(entryRow).join("") || `<div class="card-body muted">还没有日记。</div>`}</div>
      </article>
      <article class="card home-search-card">
        <div class="card-head"><h2>回忆检索</h2><span class="meta">${escapeHtml(state.bootstrap.search.backend)}</span></div>
        <div class="card-body">
          <form class="searchbar" data-action="quick-search">
            <input name="q" placeholder="关键词、人物、事件或情绪" />
            <button class="primary">检索</button>
          </form>
        </div>
      </article>
    </section>
  `;
  bindQuickSearch();
}

function entryRow(entry) {
  return `
    <button class="row ${state.diary.selected?.date === entry.date ? "active" : ""}" data-date="${escapeHtml(entry.date)}" type="button">
      <span>${escapeHtml(entry.date)}</span>
      <strong>${escapeHtml(entry.title || entry.date)}</strong>
    </button>
  `;
}

async function ensureDiaryList(force = false) {
  if (state.diary.loaded && !force) return;
  const payload = await api("/api/ui/diary");
  state.diary.items = payload.items;
  state.diary.archive = payload.archive;
  state.diary.loaded = true;
}

async function loadDiaryEntry(date) {
  await ensureDiaryList();
  const selectedDate = date || state.diary.selected?.date || state.diary.items[0]?.date;
  state.selectedDate = selectedDate || "";
  state.diary.selected = selectedDate ? await api(`/api/ui/diary/${encodeURIComponent(selectedDate)}`) : null;
}

async function renderDiary() {
  await loadDiaryEntry(state.selectedDate);
  if (!state.rendered.has("diary")) {
    panel("diary").innerHTML = `
      ${pageHead("Entries", "日记", `<button class="button primary" data-view="write" type="button">写一篇</button>`)}
      <section class="diary-layout">
        <aside class="card diary-list">
          <div id="diary-archive"></div>
          <div class="list" id="diary-list"></div>
        </aside>
        <article class="card diary-article" id="diary-article"></article>
      </section>
    `;
    state.rendered.add("diary");
  }
  updateDiaryArchive();
  updateDiaryList();
  updateDiaryArticle({ preserveScroll: false });
}

async function selectDiary(date) {
  if (state.view !== "diary") {
    await setView("diary", { date });
    return;
  }
  state.error = "";
  state.notice = "";
  const article = document.getElementById("diary-article");
  const previousScroll = article ? article.scrollTop : 0;
  await loadDiaryEntry(date);
  updateDiaryList();
  updateDiaryArchive();
  updateDiaryArticle({ preserveScroll: true, previousScroll });
  updateShell();
}

function updateDiaryArchive() {
  const target = document.getElementById("diary-archive");
  if (!target) return;
  const dates = state.diary.items.map((entry) => entry.date).filter(Boolean);
  const years = [...new Set(dates.map((date) => date.slice(0, 4)))];
  const months = [...new Set(dates.map((date) => date.slice(0, 7)))];
  target.innerHTML = `
    <div class="archive-picker">
      <label>年份<select data-jump-level="year"><option value="">全部</option>${years.map((year) => `<option value="${year}">${year}</option>`).join("")}</select></label>
      <label>月份<select data-jump-level="month"><option value="">全部</option>${months.map((month) => `<option value="${month}">${month}</option>`).join("")}</select></label>
      <label>日期<select data-jump-level="date"><option value="">选择日记</option>${dates.map((date) => `<option value="${date}" ${date === state.diary.selected?.date ? "selected" : ""}>${date}</option>`).join("")}</select></label>
    </div>
  `;
  target.querySelectorAll("[data-jump-level]").forEach((node) => {
    node.addEventListener("change", (event) => {
      const value = event.currentTarget.value;
      if (!value) return;
      const match = state.diary.items.find((entry) => entry.date.startsWith(value));
      if (match) selectDiary(match.date);
    });
  });
}

function updateDiaryList() {
  const target = document.getElementById("diary-list");
  if (!target) return;
  target.innerHTML = state.diary.items.map(entryRow).join("") || `<div class="card-body muted">还没有日记。</div>`;
}

function updateDiaryArticle({ preserveScroll = false, previousScroll = 0 } = {}) {
  const target = document.getElementById("diary-article");
  if (!target) return;
  const selected = state.diary.selected;
  target.innerHTML = selected
    ? `<div class="card-head">
        <div><p class="eyebrow">${escapeHtml(selected.date)}</p><h2>${escapeHtml(selected.title)}</h2></div>
        <div class="actions"><button class="button" data-edit-date="${escapeHtml(selected.date)}" type="button">编辑</button><button class="danger" data-delete="${escapeHtml(selected.date)}">删除</button></div>
      </div>
      <div class="card-body">
        <div class="meta">重要度 ${selected.importance} · ${escapeHtml(selected.source || "")}</div>
        <div class="chips">${[...(selected.mood || []), ...(selected.tags || []), ...(selected.people || [])].map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join("")}</div>
        <div class="article-body">${escapeHtml(selected.body)}</div>
        ${(selected.media_refs || []).length ? `<div class="media-refs"><h3>媒体引用</h3>${selected.media_refs.map((item) => `<p>${escapeHtml(item)}</p>`).join("")}</div>` : ""}
      </div>`
    : `<div class="card-body muted">选择一篇日记。</div>`;
  bindDiaryArticleActions();
  if (preserveScroll) target.scrollTop = Math.min(previousScroll, target.scrollHeight);
}

function bindDiaryArticleActions() {
  document.querySelector("[data-delete]")?.addEventListener("click", async (event) => {
    const date = event.currentTarget.dataset.delete;
    if (!confirm(`删除 ${date} 的日记？`)) return;
    await api(`/api/ui/diary/${encodeURIComponent(date)}`, { method: "DELETE" });
    state.diary.loaded = false;
    state.diary.selected = null;
    state.selectedDate = "";
    state.notice = "日记已删除。";
    await renderDiary();
    updateShell();
  });
}

async function renderWrite() {
  if (state.editingDate) await loadDiaryEntry(state.editingDate);
  const editing = state.editingDate;
  const selected = editing && state.diary.selected?.date === editing ? state.diary.selected : null;
  panel("write").innerHTML = `
    ${pageHead("Write", editing ? "编辑日记" : "写入日记")}
    <section class="card">
      <form class="card-body form" data-action="write-diary">
        <div class="form-grid">
          <label>日期<input name="date" type="date" value="${escapeHtml(editing || new Date().toISOString().slice(0, 10))}" required></label>
          <label>标题<input name="title" value="${escapeHtml(selected?.title || "")}" placeholder="由 bot 或管理员概括，不要只写日期"></label>
          <label>情绪<input name="mood" value="${escapeHtml((selected?.mood || []).join(","))}"></label>
          <label>标签<input name="tags" value="${escapeHtml((selected?.tags || []).join(","))}"></label>
          <label>人物<input name="people" value="${escapeHtml((selected?.people || []).join(","))}"></label>
          <label>重要度<input name="importance" type="number" min="1" max="5" value="${selected?.importance || 3}"></label>
        </div>
        <label>正文<textarea name="body" required>${escapeHtml(selected?.body || "")}</textarea></label>
        <label>媒体引用<textarea name="media_refs" placeholder="每行一个图片、语音或附件引用">${escapeHtml((selected?.media_refs || []).join("\n"))}</textarea></label>
        <div class="actions"><button class="primary">保存日记</button><button class="button" data-view="diary" type="button">返回日记</button></div>
      </form>
    </section>
  `;
  panel("write").querySelector('[data-action="write-diary"]').addEventListener("submit", saveDiary);
}

async function saveDiary(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = {
    date: form.get("date"),
    title: form.get("title"),
    body: form.get("body"),
    mood: splitWords(form.get("mood")),
    tags: splitWords(form.get("tags")),
    people: splitWords(form.get("people")),
    media_refs: String(form.get("media_refs") || "").split(/\n+/).map((item) => item.trim()).filter(Boolean),
    importance: Number(form.get("importance") || 3),
    source: "admin",
    reason: "web_app_update",
  };
  const result = await api("/api/ui/diary", { method: "POST", body: JSON.stringify(payload) });
  state.diary.loaded = false;
  state.editingDate = "";
  state.notice = "日记已保存。";
  await setView("diary", { date: result.entry.date, keepNotice: true });
}

async function loadSearch(query = "") {
  state.search.query = query || "";
  if (!state.search.query) {
    state.search.results = [];
    return;
  }
  const payload = await api(`/api/ui/search?q=${encodeURIComponent(state.search.query)}&top_k=8`);
  state.search.results = payload.results;
  state.search.backend = payload.search.backend;
}

async function renderSearch() {
  await loadSearch(state.search.query);
  panel("search").innerHTML = `
    ${pageHead("Recall", "检索")}
    <section class="card">
      <div class="card-body">
        <form class="searchbar" data-action="search">
          <input name="q" value="${escapeHtml(state.search.query)}" placeholder="关键词、人物、事件或情绪" />
          <button class="primary">检索</button>
        </form>
        <p class="muted">当前检索：${escapeHtml(state.search.backend || state.bootstrap.search.backend)}</p>
      </div>
      <div class="list">
        ${
          state.search.results.length
            ? state.search.results.map((item) => `<button class="row" data-date="${escapeHtml(item.date)}" type="button"><span>${escapeHtml(item.date)}</span><strong>${escapeHtml(item.title)}</strong><em>${escapeHtml(item.snippet || "")}</em></button>`).join("")
            : `<div class="card-body muted">输入关键词后只返回相关片段，不会把整本日记翻进上下文。</div>`
        }
      </div>
    </section>
  `;
  panel("search").querySelector('[data-action="search"]').addEventListener("submit", (event) => {
    event.preventDefault();
    const q = new FormData(event.currentTarget).get("q");
    setView("search", { query: q });
  });
}

function bindQuickSearch() {
  panel("dashboard")?.querySelector('[data-action="quick-search"]')?.addEventListener("submit", (event) => {
    event.preventDefault();
    const q = new FormData(event.currentTarget).get("q");
    setView("search", { query: q });
  });
}

async function renderImpressions() {
  state.impressions = (await api("/api/ui/impressions")).items;
  if (state.selectedImpressionName) {
    state.selectedImpression = state.impressions.find((item) => item.name === state.selectedImpressionName) || null;
  } else {
    state.selectedImpression = state.impressions[0] || null;
    state.selectedImpressionName = state.selectedImpression?.name || "";
  }
  panel("impressions").innerHTML = `
    ${pageHead("People", "人物印象", `<button class="button primary" data-new-impression type="button">新建人物</button>`)}
    <section class="impression-layout">
      <aside class="card impression-list">
        <div class="card-head"><h2>人物</h2><span class="meta">${state.impressions.length} 条</span></div>
        <div class="list">
          ${state.impressions.map(renderImpressionRow).join("") || `<div class="card-body muted">还没有人物印象。</div>`}
        </div>
      </aside>
      <article class="card impression-detail" id="impression-detail">
        ${renderImpressionDetail(state.selectedImpression)}
      </article>
    </section>
  `;
  bindImpressionForm();
}

function renderImpressionRow(item) {
  return `
    <button class="row ${state.selectedImpressionName === item.name ? "active" : ""}" data-impression-name="${escapeHtml(item.name)}" type="button">
      <span>${escapeHtml(item.updated_at ? item.updated_at.slice(0, 10) : "")}</span>
      <strong>${escapeHtml(item.name)}</strong>
      <em>${escapeHtml(item.identity || item.relationship || item.summary || "")}</em>
    </button>
  `;
}

function renderImpressionDetail(item) {
  const empty = {
    name: "",
    summary: "",
    identity: "",
    traits: [],
    hobbies: [],
    interests: [],
    preferences: [],
    relationship: "",
    affinity: 3,
    special_comment: "",
    evidence_dates: [],
    confidence: 3,
    notes: "",
  };
  const value = item || empty;
  return `
    <div class="card-head">
      <div><p class="eyebrow">${item ? "Profile" : "New Profile"}</p><h2>${escapeHtml(item?.name || "新建人物印象")}</h2></div>
      ${item ? `<button class="danger" data-delete-impression="${escapeHtml(item.name)}" type="button">删除</button>` : ""}
    </div>
    <form class="card-body form impression-form" data-action="save-impression">
      <input type="hidden" name="previous_name" value="${escapeHtml(item?.name || "")}">
      <div class="form-grid compact">
        <label>名字<input name="name" value="${escapeHtml(value.name)}" required></label>
        <label>身份<input name="identity" value="${escapeHtml(value.identity || "")}" placeholder="身份、关系定位或长期角色"></label>
        <label>关系<input name="relationship" value="${escapeHtml(value.relationship || "")}" placeholder="与 bot、项目或管理员的关系"></label>
        <label>喜爱程度<input name="affinity" type="number" min="1" max="5" value="${value.affinity || 3}"></label>
        <label>可信度<input name="confidence" type="number" min="1" max="5" value="${value.confidence || 3}"></label>
        <label>证据日期<input name="evidence_dates" value="${escapeHtml((value.evidence_dates || []).join(","))}" placeholder="2026-05-18,2026-05-19"></label>
      </div>
      <label>总结评价<textarea name="summary" required placeholder="稳定、可追溯的长期总结，不要只写一句标签。">${escapeHtml(value.summary || "")}</textarea></label>
      <div class="form-grid compact">
        <label>性格特征<input name="traits" value="${escapeHtml((value.traits || []).join(","))}" placeholder="多个用逗号分隔"></label>
        <label>爱好<input name="hobbies" value="${escapeHtml((value.hobbies || []).join(","))}" placeholder="多个用逗号分隔"></label>
        <label>兴趣<input name="interests" value="${escapeHtml((value.interests || []).join(","))}" placeholder="多个用逗号分隔"></label>
        <label>偏好<input name="preferences" value="${escapeHtml((value.preferences || []).join(","))}" placeholder="相处方式、表达偏好、边界"></label>
      </div>
      <label>特殊点评<textarea name="special_comment" placeholder="bot 按自己人设写出的主观点评，可以保留语气，但必须有依据。">${escapeHtml(value.special_comment || "")}</textarea></label>
      <label>备注<textarea name="notes" placeholder="其他情报、待验证观察、长期边界。">${escapeHtml(value.notes || "")}</textarea></label>
      <div class="notice soft">日记写完后如果开启人物印象自检，bot 应先读取旧印象，再根据新证据决定是否更新；没有稳定变化就不用硬写。</div>
      <div class="actions"><button class="primary">保存人物印象</button></div>
    </form>
  `;
}

async function selectImpression(name) {
  state.selectedImpressionName = name || "";
  state.selectedImpression = state.impressions.find((item) => item.name === state.selectedImpressionName) || null;
  if (state.view !== "impressions") {
    await setView("impressions");
    return;
  }
  await renderImpressions();
  updateShell();
}

function newImpression() {
  state.selectedImpressionName = "";
  state.selectedImpression = null;
  panel("impressions").querySelectorAll("[data-impression-name]").forEach((node) => node.classList.remove("active"));
  const target = document.getElementById("impression-detail");
  if (target) {
    target.innerHTML = renderImpressionDetail(null);
    bindImpressionForm();
  }
}

function bindImpressionForm() {
  panel("impressions").querySelector('[data-action="save-impression"]')?.addEventListener("submit", saveImpression);
  panel("impressions").querySelector("[data-delete-impression]")?.addEventListener("click", deleteImpression);
}

async function saveImpression(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = {
    previous_name: form.get("previous_name"),
    name: form.get("name"),
    identity: form.get("identity"),
    summary: form.get("summary"),
    traits: splitWords(form.get("traits")),
    hobbies: splitWords(form.get("hobbies")),
    interests: splitWords(form.get("interests")),
    preferences: splitWords(form.get("preferences")),
    relationship: form.get("relationship"),
    affinity: Number(form.get("affinity") || 3),
    special_comment: form.get("special_comment"),
    evidence_dates: splitWords(form.get("evidence_dates")),
    confidence: Number(form.get("confidence") || 3),
    notes: form.get("notes"),
  };
  const result = await api("/api/ui/impressions", { method: "POST", body: JSON.stringify(payload) });
  state.notice = "人物印象已保存。";
  state.selectedImpressionName = result.item.name;
  state.bootstrap = null;
  await renderImpressions();
  updateShell();
}

async function deleteImpression(event) {
  const name = event.currentTarget.dataset.deleteImpression;
  if (!confirm(`删除 ${name} 的人物印象？`)) return;
  await api(`/api/ui/impressions/${encodeURIComponent(name)}`, { method: "DELETE" });
  state.notice = "人物印象已删除。";
  state.selectedImpressionName = "";
  state.selectedImpression = null;
  state.bootstrap = null;
  await renderImpressions();
  updateShell();
}

async function renderMedia() {
  state.media = (await api("/api/ui/media")).items;
  panel("media").innerHTML = `
    ${pageHead("Media", "媒体")}
    <section class="grid">
      ${state.media.map((manifest) => `<article class="card"><div class="card-head"><h2>${escapeHtml(manifest.date)}</h2><span class="meta">${manifest.assets?.length || 0} 个文件</span></div><div class="card-body">${(manifest.assets || []).map((asset) => `<p><a href="${asset.url}" target="_blank" rel="noreferrer">${escapeHtml(asset.original_name || asset.sha256)}</a></p>`).join("")}</div></article>`).join("") || `<article class="card"><div class="card-body muted">还没有媒体归档。</div></article>`}
    </section>
  `;
}

async function renderSettings() {
  const payload = await api("/api/ui/settings");
  state.settings = payload;
  const settings = payload.settings;
  panel("settings").innerHTML = `
    ${pageHead("Config", "设置")}
    <form class="settings-sections" data-action="save-settings">
      <article class="card">
        <div class="card-head"><div><p class="eyebrow">Core</p><h2>日记与回忆</h2></div><span class="meta">${escapeHtml(payload.search.backend)}</span></div>
        <div class="card-body form">
          <div class="setting-line"><div><strong>日记模块</strong><p class="muted">控制 bot 与网页的日记写入、读取、归档和检索。</p></div>${switchControl("enable_diary_module", settings.enable_diary_module)}</div>
          <div class="setting-line"><div><strong>主动回忆</strong><p class="muted">当上下文不足且提到过去事件时，引导 bot 优先检索日记片段。</p></div>${switchControl("memory_recall_enabled", settings.memory_recall_enabled)}</div>
          <div class="form-grid compact">
            <label>回忆策略<select name="memory_recall_policy"><option value="conservative" ${settings.memory_recall_policy === "conservative" ? "selected" : ""}>谨慎</option><option value="active" ${settings.memory_recall_policy === "active" ? "selected" : ""}>积极</option></select></label>
            <label>默认检索条数<input name="search_default_top_k" type="number" min="1" max="20" value="${settings.search_default_top_k}"></label>
          </div>
          <details>
            <summary>检索、归档与印象提示</summary>
            <div class="form-grid compact">
              <label>片段长度<input name="search_snippet_chars" type="number" min="80" max="360" value="${settings.search_snippet_chars}"></label>
              <label>归档粒度<select name="diary_archive_granularity"><option value="day" ${settings.diary_archive_granularity === "day" ? "selected" : ""}>年月日</option><option value="month" ${settings.diary_archive_granularity === "month" ? "selected" : ""}>年月</option><option value="year" ${settings.diary_archive_granularity === "year" ? "selected" : ""}>年</option></select></label>
            </div>
            ${check("allow_media_refs", "允许媒体引用", settings.allow_media_refs)}
            ${check("show_impression_prompt", "启用人物印象提示", settings.show_impression_prompt)}
            <label>人物印象提示词<textarea name="impression_prompt">${escapeHtml(settings.impression_prompt || "")}</textarea></label>
          </details>
        </div>
      </article>
      <article class="card">
        <div class="card-head"><div><p class="eyebrow">Appearance</p><h2>外观</h2></div><span class="meta">framework/user_custom/webui</span></div>
        <div class="card-body form">
          <div class="brand-settings">
            <div class="brand-preview">${settings.brand_avatar_url ? `<img src="${escapeHtml(settings.brand_avatar_url)}" alt="${escapeHtml(settings.site_title || "小窝")}">` : `<span>${escapeHtml((settings.site_title || "小窝").slice(0, 1))}</span>`}</div>
            <div class="form-grid compact">
              <label>小窝标题<input name="site_title" value="${escapeHtml(settings.site_title || "小窝")}" placeholder="例如：小莫的小窝"></label>
              <label>头像地址<input name="brand_avatar_url" value="${escapeHtml(settings.brand_avatar_url || "")}" placeholder="可填写图片 URL，也可在下方上传"></label>
              <label>上传左上角头像<input name="brand_avatar_file" type="file" accept="image/png,image/jpeg,image/webp,image/gif"></label>
            </div>
          </div>
          <div class="form-grid compact">
            <label>前端样式<select name="active_frontend_style">${payload.frontend_styles.map((style) => `<option value="${escapeHtml(style.id)}" ${settings.active_frontend_style === style.id ? "selected" : ""}>${escapeHtml(style.name)} · ${escapeHtml(style.kind)}</option>`).join("")}</select></label>
            <label>自定义前端目录<input name="custom_webui_dir" value="${escapeHtml(settings.custom_webui_dir || "")}" placeholder="留空则使用小窝数据目录下的 framework/user_custom/webui"></label>
          </div>
          ${check("backup_custom_before_update", "更新前备份自定义内容", settings.backup_custom_before_update)}
        </div>
      </article>
      <article class="card module-console-card">
        <div class="card-head"><div><p class="eyebrow">Modules</p><h2>模块控制台</h2></div><span class="meta">官方稳定，自定义隔离</span></div>
        <div class="card-body form">
          <div class="notice soft">官方模块会随插件更新；如果要改日记这类官方能力，优先做拓展包。确实要替代整套功能时，请做自定义完整模块并声明 feature_tags、replaces、conflicts_with。</div>
          ${moduleWarnings(payload.module_catalog.conflicts || [])}
          <div class="module-console">
            ${moduleGroup("官方模块", payload.module_catalog.official, settings.enabled_official_modules, "enabled_official_modules", "插件更新可能替换官方实现；数据仍在数据目录中。")}
            ${moduleGroup("自定义完整模块", payload.module_catalog.custom, settings.enabled_custom_modules, "enabled_custom_modules", "用于替代或新增完整功能，数据放 modules/<module-id>/。")}
            ${moduleGroup("拓展包", payload.module_catalog.extensions || [], settings.enabled_custom_extensions || [], "enabled_custom_extensions", "用于增强现有模块，数据放 modules/extensions/<extension-id>/。")}
          </div>
        </div>
      </article>
      <div class="sticky-save"><button class="primary">保存小窝设置</button><span class="muted">常用项在外层，低频项已收进折叠区。</span></div>
    </form>
    <section class="settings-sections">
      <article class="card">
        <div class="card-head"><div><p class="eyebrow">Access</p><h2>访问与备份</h2></div><span class="meta">插件内部工具不依赖外部 API Key</span></div>
        <form class="card-body form" data-action="save-security">
          <div class="form-grid compact">
            <label>新管理员密码<input name="admin_password" type="password" placeholder="留空则不修改"></label>
            <label>外部 API Key<input name="bot_api_token" value="${escapeHtml(payload.security.bot_api_token || "")}"></label>
          </div>
          <details><summary>外部 API 选项</summary>${check("generate_bot_api_token", "保存时生成新的外部 API Key", false)}${check("external_api_enabled", "启用外部 API", payload.security.external_api_enabled)}</details>
          <div class="actions"><button class="primary">保存访问密钥</button></div>
        </form>
      </article>
      <article class="card">
        <div class="card-head"><div><p class="eyebrow">Backup</p><h2>分层导入导出</h2></div><span class="meta">manifest.json</span></div>
        <div class="card-body form">
          <form class="form-grid compact" data-action="export-backup">
            <label>导出范围<select name="package_type">${exportOptions(payload.module_catalog)}</select></label>
            <label>模块 ID<input name="module_id" placeholder="导出自定义模块或拓展包时填写"></label>
            ${check("include_security", "包含管理员密码/API Key", false)}
            <div class="actions"><button class="primary">导出所选范围</button></div>
          </form>
          <form class="upload-zone" data-action="import-backup">
            <input name="backup_file" type="file" accept=".zip" required>
            <label>导入策略<select name="strategy"><option value="safe">安全合并：已有文件跳过</option><option value="overwrite">覆盖合并：先备份再覆盖</option></select></label>
            <div class="actions"><button class="primary">导入备份包</button></div>
            <p class="muted">导入会读取 manifest 自动识别完整备份、日记、人物印象、媒体、个性化前端、自定义模块或拓展包。</p>
          </form>
        </div>
      </article>
    </section>
  `;
  panel("settings").querySelector('[data-action="save-settings"]').addEventListener("submit", saveSettings);
  panel("settings").querySelector('[data-action="save-security"]').addEventListener("submit", saveSecurity);
  panel("settings").querySelector('[data-action="export-backup"]').addEventListener("submit", exportBackup);
  panel("settings").querySelector('[data-action="import-backup"]').addEventListener("submit", importBackup);
}

function check(name, label, checked) {
  return `<label class="check"><input name="${name}" type="checkbox" ${checked ? "checked" : ""}>${escapeHtml(label)}</label>`;
}

function switchControl(name, checked) {
  return `<label class="switch"><input name="${name}" type="checkbox" ${checked ? "checked" : ""}><span></span></label>`;
}

function moduleWarnings(conflicts) {
  return conflicts.length
    ? `<div class="module-warnings">${conflicts.map((item) => `<div class="notice ${item.level === "danger" ? "error" : "soft"}"><strong>${escapeHtml(item.title)}：</strong>${escapeHtml(item.message)}</div>`).join("")}</div>`
    : `<div class="notice soft">当前没有检测到已启用模块的功能标签冲突。</div>`;
}

function moduleGroup(title, modules, enabled, inputName, hint) {
  return `
    <section class="module-group">
      <div class="module-group-head"><h3>${escapeHtml(title)}</h3><p class="muted">${escapeHtml(hint)}</p></div>
      ${modules.length ? modules.map((module) => moduleCard(module, enabled, inputName)).join("") : `<p class="muted">暂无。</p>`}
    </section>
  `;
}

function moduleCard(module, enabled, inputName) {
  const tags = module.feature_tags || [];
  const targets = module.target_modules || [];
  const replaces = module.replaces || [];
  const conflicts = module.conflicts_with || [];
  return `
    <label class="module-card">
      <input name="${inputName}" value="${escapeHtml(module.id)}" type="checkbox" ${enabled.includes(module.id) ? "checked" : ""}>
      <span class="module-card-main">
        <strong>${escapeHtml(module.name || module.id)}</strong>
        <em>${escapeHtml(module.description || "没有说明。")}</em>
        <span class="chips small">
          <span class="chip">${escapeHtml(module.type || "module")}</span>
          ${tags.map((tag) => `<span class="chip">${escapeHtml(tag)}</span>`).join("")}
          ${targets.map((target) => `<span class="chip">挂载 ${escapeHtml(target)}</span>`).join("")}
          ${replaces.map((target) => `<span class="chip">替代 ${escapeHtml(target)}</span>`).join("")}
          ${conflicts.map((target) => `<span class="chip">冲突 ${escapeHtml(target)}</span>`).join("")}
        </span>
        ${(module.data_path || module.frontend_path) ? `<span class="module-paths">${escapeHtml([module.data_path, module.frontend_path].filter(Boolean).join(" · "))}</span>` : ""}
      </span>
    </label>
  `;
}

function exportOptions(catalog) {
  const options = [
    ["full", "完整备份"],
    ["diary", "日记模块"],
    ["impressions", "人物印象"],
    ["media", "媒体归档"],
    ["webui_custom", "个性化前端"],
    ["security", "安全配置"],
    ["custom_module", "指定自定义模块"],
    ["extension", "指定拓展包"],
  ];
  return options.map(([value, label]) => `<option value="${value}">${label}</option>`).join("");
}

async function saveSettings(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  let avatarUrl = String(form.get("brand_avatar_url") || "");
  const avatarFile = form.get("brand_avatar_file");
  if (avatarFile && avatarFile.size) {
    avatarUrl = await uploadAvatar(avatarFile);
  }
  const payload = {
    site_title: form.get("site_title"),
    brand_avatar_url: avatarUrl,
    search_default_top_k: Number(form.get("search_default_top_k") || 5),
    search_snippet_chars: Number(form.get("search_snippet_chars") || 180),
    memory_recall_enabled: form.has("memory_recall_enabled"),
    memory_recall_policy: form.get("memory_recall_policy"),
    enable_diary_module: form.has("enable_diary_module"),
    diary_archive_granularity: form.get("diary_archive_granularity"),
    allow_media_refs: form.has("allow_media_refs"),
    show_impression_prompt: form.has("show_impression_prompt"),
    active_frontend_style: form.get("active_frontend_style"),
    enabled_official_modules: form.getAll("enabled_official_modules"),
    enabled_custom_modules: form.getAll("enabled_custom_modules"),
    enabled_custom_extensions: form.getAll("enabled_custom_extensions"),
    custom_webui_dir: form.get("custom_webui_dir"),
    backup_custom_before_update: form.has("backup_custom_before_update"),
    impression_prompt: form.get("impression_prompt"),
  };
  await api("/api/ui/settings", { method: "POST", body: JSON.stringify(payload) });
  state.notice = "设置已保存。";
  state.bootstrap = null;
  await renderSettings();
  updateShell();
}

async function uploadAvatar(file) {
  const payload = new FormData();
  payload.append("file", file);
  const response = await fetch("/api/ui/avatar", {
    method: "POST",
    credentials: "same-origin",
    body: payload,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  const data = await response.json();
  return data.avatar_url;
}

function exportBackup(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const params = new URLSearchParams({
    package_type: form.get("package_type") || "full",
    module_id: form.get("module_id") || "",
    include_security: form.has("include_security") ? "true" : "false",
  });
  window.location.href = `/api/ui/export?${params.toString()}`;
}

async function importBackup(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = new FormData();
  payload.append("backup_file", form.get("backup_file"));
  payload.append("strategy", form.get("strategy") || "safe");
  const response = await fetch("/api/ui/import", {
    method: "POST",
    credentials: "same-origin",
    body: payload,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  const data = await response.json();
  const result = data.result || {};
  state.notice = `导入完成：${result.imported || 0} 个文件，跳过 ${result.skipped || 0} 个，覆盖 ${result.overwritten || 0} 个。`;
  state.bootstrap = null;
  await renderSettings();
  updateShell();
}

async function saveSecurity(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await api("/api/ui/security", {
    method: "POST",
    body: JSON.stringify({
      admin_password: form.get("admin_password"),
      bot_api_token: form.get("bot_api_token"),
      generate_bot_api_token: form.has("generate_bot_api_token"),
      external_api_enabled: form.has("external_api_enabled"),
    }),
  });
  state.notice = "访问密钥已保存。";
  await renderSettings();
  updateShell();
}

ensureShell();
panel(state.view).innerHTML = `<div class="loading">正在进入小窝...</div>`;
loadView();
