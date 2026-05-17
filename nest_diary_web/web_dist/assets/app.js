const state = {
  route: parseRoute(),
  bootstrap: null,
  diary: { items: [], archive: [], selected: null },
  search: { query: "", results: [], backend: "" },
  impressions: [],
  media: [],
  settings: null,
  notice: "",
  error: "",
};

const APP_VERSION = "0.3.1";
const app = document.getElementById("app");

const navItems = [
  ["dashboard", "/", "总览", "Home"],
  ["diary", "/diary", "日记", "Entries"],
  ["write", "/write", "写入", "Write"],
  ["search", "/search", "搜索", "Recall"],
  ["impressions", "/impressions", "印象", "People"],
  ["media", "/media", "媒体", "Media"],
  ["settings", "/settings", "设置", "Config"],
];

function parseRoute() {
  const path = window.location.pathname;
  if (path.startsWith("/diary/")) return { name: "diary", date: decodeURIComponent(path.split("/").pop()) };
  if (path === "/diary") return { name: "diary" };
  if (path === "/write") return { name: "write" };
  if (path === "/search") return { name: "search", query: new URLSearchParams(location.search).get("q") || "" };
  if (path === "/impressions") return { name: "impressions" };
  if (path === "/media") return { name: "media" };
  if (path === "/settings") return { name: "settings" };
  return { name: "dashboard" };
}

function navigate(path) {
  if (path === window.location.pathname + window.location.search) return;
  history.pushState({}, "", path);
  state.route = parseRoute();
  state.notice = "";
  state.error = "";
  loadRoute();
}

window.addEventListener("popstate", () => {
  state.route = parseRoute();
  loadRoute();
});

document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-route], a[data-link]");
  if (!target) return;
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  event.stopPropagation();
  navigate(target.dataset.route || target.getAttribute("href"));
}, true);

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (response.status === 401) {
    location.href = "/login";
    return;
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
    .replaceAll("，", ",")
    .replaceAll("、", ",")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function ensureShell() {
  if (document.getElementById("view")) return;
  app.innerHTML = `
    <div class="app" data-app-version="${APP_VERSION}">
      <aside class="nav">
        <button class="brand" data-route="/" type="button">
          <span class="brand-mark">小</span>
          <span><strong>小窝</strong><small>Private Nest</small></span>
        </button>
        <nav class="nav-links">
          ${navItems
            .map(([key, href, label, meta]) => `<button class="nav-link" data-nav="${key}" data-route="${href}" type="button">${label}<span>${meta}</span></button>`)
            .join("")}
        </nav>
        <div class="nav-footer">
          <div id="app-version"></div>
          <div id="search-backend"></div>
        </div>
      </aside>
      <main class="main" id="view"></main>
    </div>
  `;
}

function renderShell(content) {
  ensureShell();
  const active = state.route.name;
  document.querySelectorAll("[data-nav]").forEach((node) => node.classList.toggle("active", node.dataset.nav === active));
  const versionNode = document.getElementById("app-version");
  if (versionNode) versionNode.textContent = `v${state.bootstrap?.version || ""} · app ${APP_VERSION}`;
  const backendNode = document.getElementById("search-backend");
  if (backendNode) backendNode.textContent = state.bootstrap?.search?.backend || "local index";
  document.getElementById("view").innerHTML = `
    ${state.notice ? `<div class="notice">${escapeHtml(state.notice)}</div>` : ""}
    ${state.error ? `<div class="notice error">${escapeHtml(state.error)}</div>` : ""}
    ${content}
  `;
}

function pageHead(eyebrow, title, actions = "") {
  return `
    <header class="topbar">
      <div class="page-title"><p>${eyebrow}</p><h1>${title}</h1></div>
      <div class="actions">${actions}</div>
    </header>
  `;
}

async function loadBootstrap() {
  if (!state.bootstrap) {
    state.bootstrap = await api("/api/ui/bootstrap");
  }
}

async function loadRoute() {
  try {
    await loadBootstrap();
    if (state.route.name === "diary") await loadDiary(state.route.date);
    if (state.route.name === "search") await loadSearch(state.route.query);
    if (state.route.name === "impressions") await loadImpressions();
    if (state.route.name === "media") await loadMedia();
    if (state.route.name === "settings") await loadSettings();
    render();
  } catch (err) {
    state.error = err.message;
    renderShell(`<div class="loading">加载失败：${escapeHtml(err.message)}</div>`);
  }
}

function render() {
  if (state.route.name === "diary") return renderDiary();
  if (state.route.name === "write") return renderWrite();
  if (state.route.name === "search") return renderSearch();
  if (state.route.name === "impressions") return renderImpressions();
  if (state.route.name === "media") return renderMedia();
  if (state.route.name === "settings") return renderSettings();
  return renderDashboard();
}

function renderDashboard() {
  const stats = state.bootstrap.stats;
  const recent = state.bootstrap.recent_entries || [];
  renderShell(`
    ${pageHead("Nest Diary", "小窝")}
    <section class="grid three">
      <article class="card stat"><span>日记</span><strong>${stats.entries}</strong></article>
      <article class="card stat"><span>媒体</span><strong>${stats.media}</strong></article>
      <article class="card stat"><span>人物印象</span><strong>${stats.people}</strong></article>
    </section>
    <section class="grid two" style="margin-top:16px">
      <article class="card">
        <div class="card-head"><h2>最近日记</h2><a href="/diary" data-link>查看全部</a></div>
        <div class="list">${recent.map(entryRow).join("") || `<div class="card-body muted">还没有日记。</div>`}</div>
      </article>
      <article class="card">
        <div class="card-head"><h2>回忆检索</h2><span class="meta">${state.bootstrap.search.backend}</span></div>
        <div class="card-body">
          <form class="searchbar" data-action="quick-search">
            <input name="q" placeholder="关键词、人物、事情、情绪" />
            <button class="primary">搜索</button>
          </form>
        </div>
      </article>
    </section>
  `);
  bindQuickSearch();
}

function entryRow(entry) {
  return `
    <button class="row ${state.diary.selected?.date === entry.date ? "active" : ""}" data-route="/diary/${encodeURIComponent(entry.date)}" type="button">
      <span>${escapeHtml(entry.date)}</span>
      <strong>${escapeHtml(entry.title || entry.date)}</strong>
      <em>${escapeHtml((entry.body || "").slice(0, 96))}</em>
    </button>
  `;
}

async function loadDiary(date) {
  if (!state.diary.items.length) {
    const payload = await api("/api/ui/diary");
    state.diary.items = payload.items;
    state.diary.archive = payload.archive;
  }
  const selectedDate = date || state.diary.items[0]?.date;
  state.diary.selected = selectedDate ? await api(`/api/ui/diary/${encodeURIComponent(selectedDate)}`) : null;
}

function renderDiary() {
  const selected = state.diary.selected;
  renderShell(`
    ${pageHead("Entries", "日记", `<a class="button primary" href="/write" data-link>写一篇</a>`)}
    <section class="diary-layout">
      <aside class="card diary-list"><div class="list">${state.diary.items.map(entryRow).join("") || `<div class="card-body muted">还没有日记。</div>`}</div></aside>
      <article class="card diary-article">
        ${
          selected
            ? `<div class="card-head">
                <div><p class="eyebrow">${escapeHtml(selected.date)}</p><h2>${escapeHtml(selected.title)}</h2></div>
                <div class="actions"><button class="button" data-route="/write?date=${encodeURIComponent(selected.date)}" type="button">编辑</button><button class="danger" data-delete="${escapeHtml(selected.date)}">删除</button></div>
              </div>
              <div class="card-body">
                <div class="meta">重要度 ${selected.importance} · ${escapeHtml(selected.source || "")}</div>
                <div class="chips">${[...(selected.mood || []), ...(selected.tags || []), ...(selected.people || [])].map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join("")}</div>
                <div class="article-body" style="margin-top:18px">${escapeHtml(selected.body)}</div>
              </div>`
            : `<div class="card-body muted">选择一篇日记。</div>`
        }
      </article>
    </section>
  `);
  document.querySelector("[data-delete]")?.addEventListener("click", async (event) => {
    const date = event.currentTarget.dataset.delete;
    if (!confirm(`删除 ${date} 的日记？`)) return;
    await api(`/api/ui/diary/${encodeURIComponent(date)}`, { method: "DELETE" });
    state.diary.items = [];
    state.notice = "日记已删除。";
    navigate("/diary");
  });
}

function renderWrite() {
  const query = new URLSearchParams(location.search);
  const editing = query.get("date");
  const selected = editing && state.diary.selected?.date === editing ? state.diary.selected : null;
  renderShell(`
    ${pageHead("Write", editing ? "编辑日记" : "写入日记")}
    <section class="card">
      <form class="card-body form" data-action="write-diary">
        <div class="form-grid">
          <label>日期<input name="date" type="date" value="${escapeHtml(editing || new Date().toISOString().slice(0, 10))}" required></label>
          <label>标题<input name="title" value="${escapeHtml(selected?.title || "")}" placeholder="由 bot 或你总结，不要只写日期"></label>
          <label>情绪<input name="mood" value="${escapeHtml((selected?.mood || []).join(","))}"></label>
          <label>标签<input name="tags" value="${escapeHtml((selected?.tags || []).join(","))}"></label>
          <label>人物<input name="people" value="${escapeHtml((selected?.people || []).join(","))}"></label>
          <label>重要度<input name="importance" type="number" min="1" max="5" value="${selected?.importance || 3}"></label>
        </div>
        <label>正文<textarea name="body" required>${escapeHtml(selected?.body || "")}</textarea></label>
        <label>媒体引用<textarea name="media_refs">${escapeHtml((selected?.media_refs || []).join("\\n"))}</textarea></label>
        <div class="actions"><button class="primary">保存日记</button></div>
      </form>
    </section>
  `);
  document.querySelector('[data-action="write-diary"]').addEventListener("submit", saveDiary);
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
  state.diary.items = [];
  state.notice = "日记已保存。";
  navigate(`/diary/${encodeURIComponent(result.entry.date)}`);
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

function renderSearch() {
  renderShell(`
    ${pageHead("Recall", "搜索")}
    <section class="card">
      <div class="card-body">
        <form class="searchbar" data-action="search">
          <input name="q" value="${escapeHtml(state.search.query)}" placeholder="关键词、人物、事情、情绪" />
          <button class="primary">搜索</button>
        </form>
        <p class="muted">当前检索：${escapeHtml(state.search.backend || state.bootstrap.search.backend)}</p>
      </div>
      <div class="list">
        ${
          state.search.results.length
            ? state.search.results.map((item) => `<button class="row" data-route="/diary/${encodeURIComponent(item.date)}" type="button"><span>${escapeHtml(item.date)}</span><strong>${escapeHtml(item.title)}</strong><em>${escapeHtml(item.snippet || "")}</em></button>`).join("")
            : `<div class="card-body muted">输入关键词后，只返回片段，不会整本翻日记。</div>`
        }
      </div>
    </section>
  `);
  document.querySelector('[data-action="search"]').addEventListener("submit", (event) => {
    event.preventDefault();
    const q = new FormData(event.currentTarget).get("q");
    navigate(`/search?q=${encodeURIComponent(q)}`);
  });
}

function bindQuickSearch() {
  document.querySelector('[data-action="quick-search"]')?.addEventListener("submit", (event) => {
    event.preventDefault();
    const q = new FormData(event.currentTarget).get("q");
    navigate(`/search?q=${encodeURIComponent(q)}`);
  });
}

async function loadImpressions() {
  state.impressions = (await api("/api/ui/impressions")).items;
}

function renderImpressions() {
  renderShell(`
    ${pageHead("People", "印象")}
    <section class="card">
      <div class="list">
        ${state.impressions.map((item) => `<div class="row"><span>${escapeHtml(item.updated_at || "")}</span><strong>${escapeHtml(item.name)}</strong><em>${escapeHtml(item.summary)}</em><div class="chips">${[...(item.traits || []), ...(item.interests || [])].map((tag) => `<span class="chip">${escapeHtml(tag)}</span>`).join("")}</div></div>`).join("") || `<div class="card-body muted">还没有人物印象。</div>`}
      </div>
    </section>
  `);
}

async function loadMedia() {
  state.media = (await api("/api/ui/media")).items;
}

function renderMedia() {
  renderShell(`
    ${pageHead("Media", "媒体")}
    <section class="grid">
      ${state.media.map((manifest) => `<article class="card"><div class="card-head"><h2>${escapeHtml(manifest.date)}</h2><span class="meta">${manifest.assets?.length || 0} 个文件</span></div><div class="card-body">${(manifest.assets || []).map((asset) => `<p><a href="${asset.url}" target="_blank">${escapeHtml(asset.original_name || asset.sha256)}</a></p>`).join("")}</div></article>`).join("") || `<article class="card"><div class="card-body muted">还没有媒体归档。</div></article>`}
    </section>
  `);
}

async function loadSettings() {
  state.settings = await api("/api/ui/settings");
}

function renderSettings() {
  const payload = state.settings;
  const settings = payload.settings;
  renderShell(`
    ${pageHead("Config", "设置")}
    <section class="settings-sections">
      <article class="card">
        <div class="card-head"><h2>检索与主动回忆</h2><span class="meta">${escapeHtml(payload.search.backend)}</span></div>
        <form class="card-body form" data-action="save-settings">
          <div class="form-grid">
            <label>默认检索条数<input name="search_default_top_k" type="number" min="1" max="20" value="${settings.search_default_top_k}"></label>
            <label>片段长度<input name="search_snippet_chars" type="number" min="80" max="360" value="${settings.search_snippet_chars}"></label>
            <label>主动回忆策略<select name="memory_recall_policy"><option value="conservative" ${settings.memory_recall_policy === "conservative" ? "selected" : ""}>谨慎</option><option value="active" ${settings.memory_recall_policy === "active" ? "selected" : ""}>积极</option></select></label>
            <label>前端样式<select name="active_frontend_style">${payload.frontend_styles.map((style) => `<option value="${escapeHtml(style.id)}" ${settings.active_frontend_style === style.id ? "selected" : ""}>${escapeHtml(style.name)} · ${escapeHtml(style.kind)}</option>`).join("")}</select></label>
            <label>自定义前端目录<input name="custom_webui_dir" value="${escapeHtml(settings.custom_webui_dir || "")}"></label>
            <label>归档粒度<select name="diary_archive_granularity"><option value="day" ${settings.diary_archive_granularity === "day" ? "selected" : ""}>年月日</option><option value="month" ${settings.diary_archive_granularity === "month" ? "selected" : ""}>年月</option><option value="year" ${settings.diary_archive_granularity === "year" ? "selected" : ""}>年</option></select></label>
          </div>
          ${check("enable_diary_module", "启用日记模块", settings.enable_diary_module)}
          ${check("memory_recall_enabled", "启用 bot 主动回忆规则", settings.memory_recall_enabled)}
          ${check("allow_media_refs", "允许媒体引用", settings.allow_media_refs)}
          ${check("show_impression_prompt", "显示人物印象提示", settings.show_impression_prompt)}
          ${check("backup_custom_before_update", "更新前备份自定义内容", settings.backup_custom_before_update)}
          <label>人物印象提示词<textarea name="impression_prompt">${escapeHtml(settings.impression_prompt || "")}</textarea></label>
          <div class="module-grid">
            <div>${moduleChecks("官方模块", payload.module_catalog.official, settings.enabled_official_modules, "enabled_official_modules")}</div>
            <div>${moduleChecks("自定义模块", payload.module_catalog.custom, settings.enabled_custom_modules, "enabled_custom_modules")}</div>
          </div>
          <div class="actions"><button class="primary">保存设置</button></div>
        </form>
      </article>
      <article class="card">
        <div class="card-head"><h2>访问密钥</h2><span class="meta">插件内部工具不依赖 API Key</span></div>
        <form class="card-body form" data-action="save-security">
          <div class="form-grid">
            <label>新管理员密码<input name="admin_password" type="password" placeholder="留空则不修改"></label>
            <label>外部 API Key<input name="bot_api_token" value="${escapeHtml(payload.security.bot_api_token || "")}"></label>
          </div>
          ${check("generate_bot_api_token", "保存时生成新的外部 API Key", false)}
          ${check("external_api_enabled", "启用外部 API", payload.security.external_api_enabled)}
          <div class="actions"><button class="primary">保存访问密钥</button><a class="button" href="/settings/export">导出备份</a></div>
        </form>
      </article>
    </section>
  `);
  document.querySelector('[data-action="save-settings"]').addEventListener("submit", saveSettings);
  document.querySelector('[data-action="save-security"]').addEventListener("submit", saveSecurity);
}

function check(name, label, checked) {
  return `<label class="check"><input name="${name}" type="checkbox" ${checked ? "checked" : ""}>${label}</label>`;
}

function moduleChecks(title, modules, enabled, name) {
  return `<h3>${title}</h3>${modules.length ? modules.map((module) => `<label class="check"><input name="${name}" value="${escapeHtml(module.id)}" type="checkbox" ${enabled.includes(module.id) ? "checked" : ""}>${escapeHtml(module.name)} <span class="muted">${escapeHtml(module.description || module.path || "")}</span></label>`).join("") : `<p class="muted">暂无。</p>`}`;
}

async function saveSettings(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = {
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
    custom_webui_dir: form.get("custom_webui_dir"),
    backup_custom_before_update: form.has("backup_custom_before_update"),
    impression_prompt: form.get("impression_prompt"),
  };
  await api("/api/ui/settings", { method: "POST", body: JSON.stringify(payload) });
  state.notice = "设置已保存。";
  state.bootstrap = null;
  await loadSettings();
  renderSettings();
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
  await loadSettings();
  renderSettings();
}

renderShell(`<div class="loading">正在进入小窝...</div>`);
loadRoute();
