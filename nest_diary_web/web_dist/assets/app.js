const APP_VERSION = "0.4.4";

const app = document.getElementById("app");
const state = {
  view: initialViewFromLocation(),
  selectedDate: initialDateFromLocation(),
  editingDate: initialEditDateFromLocation(),
  selectedImpressionName: initialImpressionFromLocation(),
  bootstrap: null,
  diary: {
    items: [],
    archive: [],
    selected: null,
    loaded: false,
    composerOpen: initialComposerFromLocation(),
    composerDate: initialComposeDateFromLocation(),
    filters: initialDiaryFilters(),
  },
  search: { query: initialSearchFromLocation(), results: [], backend: "" },
  impressions: [],
  selectedImpression: null,
  media: [],
  mediaStorage: { bytes: 0, count: 0, label: "0 B" },
  selectedMedia: null,
  settings: null,
  notice: "",
  toast: "",
  error: "",
  rendered: new Set(),
  settingsMenuOpen: initialViewFromLocation() === "settings",
  settingsSection: "modules",
  settingsModuleDetail: "",
  moduleFilter: "all",
};

const navItems = [
  ["dashboard", "首页"],
  ["diary", "日记"],
  ["search", "查找"],
  ["impressions", "印象"],
  ["media", "媒体"],
  ["settings", "设置"],
];

function initialViewFromLocation() {
  const path = window.location.pathname;
  if (path.startsWith("/diary")) return "diary";
  if (path === "/write") return "diary";
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

function initialDiaryFilters() {
  const date = initialDateFromLocation();
  return date ? { year: date.slice(0, 4), month: date.slice(0, 7), date } : { year: "", month: "", date: "" };
}

function initialEditDateFromLocation() {
  if (window.location.pathname !== "/write") return "";
  return new URLSearchParams(window.location.search).get("date") || "";
}

function initialComposerFromLocation() {
  return window.location.pathname === "/write";
}

function initialComposeDateFromLocation() {
  if (window.location.pathname !== "/write") return new Date().toISOString().slice(0, 10);
  return new URLSearchParams(window.location.search).get("date") || new Date().toISOString().slice(0, 10);
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
          <span><strong id="brand-title">小窝</strong><small>私有空间</small></span>
        </button>
        <nav class="nav-links" id="nav-links">
          ${renderNavLinks()}
        </nav>
      </aside>
      <main class="main" id="view">
        <div id="notice-slot"></div>
        <section class="view-panel" id="view-dashboard" data-panel="dashboard"></section>
        <section class="view-panel" id="view-diary" data-panel="diary"></section>
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
  const navLinks = document.getElementById("nav-links");
  if (navLinks) navLinks.innerHTML = renderNavLinks();
  document.querySelectorAll("[data-nav]").forEach((node) => node.classList.toggle("active", node.dataset.nav === state.view));
  document.querySelectorAll("[data-settings-toggle]").forEach((node) => {
    node.classList.toggle("open", state.settingsMenuOpen);
    node.setAttribute("aria-expanded", String(state.settingsMenuOpen));
  });
  document.querySelectorAll("[data-panel]").forEach((node) => {
    node.hidden = node.dataset.panel !== state.view;
  });
  const notice = document.getElementById("notice-slot");
  notice.innerHTML = `
    ${state.notice ? `<div class="notice">${escapeHtml(state.notice)}</div>` : ""}
    ${state.error ? `<div class="notice error">${escapeHtml(state.error)}</div>` : ""}
    ${state.toast ? `<div class="toast">${escapeHtml(state.toast)}</div>` : ""}
  `;
}

function renderNavLinks() {
  return navItems
    .filter(([key]) => key !== "media" || isMediaEnabled())
    .map(([key, label]) => {
      const children =
        key === "settings" && state.settingsMenuOpen
          ? `<div class="nav-submenu">
              ${settingsTab("modules", "模块管理")}
              ${settingsTab("access", "访问密钥")}
              ${settingsTab("backup", "导入导出")}
            </div>`
          : "";
      const attrs = key === "settings" ? `data-settings-toggle aria-expanded="${state.settingsMenuOpen}"` : "";
      return `<div class="nav-link-group"><button class="nav-link" data-nav="${key}" data-view="${key}" ${attrs} type="button">${iconImg(navIcon(key), label)}<span>${label}</span></button>${children}</div>`;
    })
    .join("");
}

function iconImg(name, label = "") {
  return `<img class="ui-icon" src="/app-assets/icons/${escapeHtml(name)}.svg" alt="${escapeHtml(label)}" loading="lazy">`;
}

function navIcon(key) {
  return {
    dashboard: "home",
    diary: "diary",
    search: "search",
    impressions: "impressions",
    media: "media",
    settings: "settings",
  }[key] || "settings";
}

function isMediaEnabled() {
  const settings = state.bootstrap?.settings || state.settings?.settings || {};
  return settings.enable_media_module !== false && (settings.enabled_official_modules || []).includes("media");
}

function currentSiteTitle() {
  return state.bootstrap?.settings?.site_title || state.settings?.settings?.site_title || "小窝";
}

function currentSiteSubtitle() {
  return state.bootstrap?.settings?.site_subtitle || state.settings?.settings?.site_subtitle || "把今天安放好，旧事也能被轻轻找回来";
}

function currentAvatarUrl() {
  return state.bootstrap?.settings?.brand_avatar_url || state.settings?.settings?.brand_avatar_url || "";
}

function pageHead(eyebrow, title, actions = "") {
  return `
    <header class="topbar">
      <div class="page-title">${eyebrow ? `<p>${escapeHtml(eyebrow)}</p>` : ""}<h1>${escapeHtml(title)}</h1></div>
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
  if (Object.prototype.hasOwnProperty.call(options, "compose")) state.diary.composerOpen = Boolean(options.compose);
  if (Object.prototype.hasOwnProperty.call(options, "query")) state.search.query = options.query || "";
  if (view !== "diary") {
    state.diary.composerOpen = false;
    state.editingDate = "";
  }
  await loadView();
}

document.addEventListener(
  "click",
  (event) => {
    const target = event.target.closest("[data-view], [data-date], [data-open-write], [data-close-write], [data-edit-date], [data-search-query], [data-impression-name], [data-new-impression], [data-media-open], [data-media-close], [data-settings-section], [data-module-settings], [data-settings-back], [data-module-filter]");
    if (!target) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    event.stopPropagation();
    if (target.dataset.view) {
      if (target.dataset.view === "settings") {
        if (state.view === "settings" && state.settingsMenuOpen) {
          state.settingsMenuOpen = false;
          updateShell();
          return;
        }
        state.settingsMenuOpen = true;
      } else {
        state.settingsMenuOpen = false;
      }
      if (target.dataset.view === "write") {
        openDiaryComposer();
        return;
      }
      if (target.dataset.view === "diary") {
        setView("diary", { compose: false });
        return;
      }
      setView(target.dataset.view);
      return;
    }
    if (target.dataset.openWrite !== undefined) {
      openDiaryComposer();
      return;
    }
    if (target.dataset.closeWrite !== undefined) {
      closeDiaryComposer();
      return;
    }
    if (target.dataset.date) {
      selectDiary(target.dataset.date);
      return;
    }
    if (target.dataset.editDate) {
      openDiaryComposer(target.dataset.editDate);
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
      return;
    }
    if (target.dataset.mediaOpen) {
      openMediaDetail(target.dataset.mediaOpen);
      return;
    }
    if (target.dataset.mediaClose !== undefined) {
      closeMediaDetail();
      return;
    }
    if (target.dataset.settingsSection) {
      switchSettingsSection(target.dataset.settingsSection);
      return;
    }
    if (target.dataset.moduleFilter) {
      setModuleFilter(target.dataset.moduleFilter);
      return;
    }
    if (target.dataset.moduleSettings) {
      openModuleSettings(target.dataset.moduleSettings);
      return;
    }
    if (target.dataset.settingsBack !== undefined) {
      closeModuleSettings();
    }
  },
  true
);

document.addEventListener("change", (event) => {
  const target = event.target.closest("[data-module-toggle]");
  if (!target) return;
  saveModuleToggle(target);
});

async function loadView() {
  try {
    ensureShell();
    await loadBootstrap();
    if (state.view === "media" && !isMediaEnabled()) state.view = "dashboard";
    if (state.view === "dashboard") renderDashboard();
    if (state.view === "diary") await renderDiary();
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
  const siteSubtitle = currentSiteSubtitle();
  target.innerHTML = `
    <section class="home-hero">
      <div class="home-hero-copy">
        <h1>${escapeHtml(siteTitle)}</h1>
        <p class="home-lead">${escapeHtml(siteSubtitle)}</p>
        <div class="home-actions">
          <button class="button primary" data-open-write type="button">写日记</button>
          <button class="button" data-view="diary" type="button">看日记</button>
        </div>
      </div>
      <div class="home-status">
        <div class="home-stat"><span>日记</span><strong>${stats.entries}</strong></div>
        <div class="home-stat"><span>媒体</span><strong>${stats.media}</strong></div>
        <div class="home-stat"><span>人物印象</span><strong>${stats.people}</strong></div>
      </div>
    </section>
    <section class="home-grid">
      <article class="card">
        <div class="card-head"><h2>最近日记</h2><button class="text-button" data-view="diary" type="button">查看全部</button></div>
        <div class="list">${recent.map(entryRow).join("") || `<div class="card-body muted">还没有日记。</div>`}</div>
      </article>
      <article class="card home-side-card">
        <div class="card-head"><h2>小窝状态</h2></div>
        <div class="card-body home-quiet-list">
          <p><strong>归档</strong><span>日记按年月日保存，保留修订快照。</span></p>
          <p><strong>印象</strong><span>人物印象独立管理；日记后是否更新由策略和 bot 判断。</span></p>
          <p><strong>个性化</strong><span>外观、模块和拓展包都放在独立目录中。</span></p>
        </div>
      </article>
    </section>
  `;
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
  const visibleItems = filteredDiaryItems();
  const candidate = date || state.diary.selected?.date || state.selectedDate;
  const selectedDate = candidate && visibleItems.some((entry) => entry.date === candidate)
    ? candidate
    : visibleItems[0]?.date || "";
  state.selectedDate = selectedDate || "";
  state.diary.selected = selectedDate ? await api(`/api/ui/diary/${encodeURIComponent(selectedDate)}`) : null;
}

function filteredDiaryItems() {
  const filters = state.diary.filters;
  return state.diary.items.filter((entry) => {
    if (filters.date) return entry.date === filters.date;
    if (filters.month) return entry.date.startsWith(filters.month);
    if (filters.year) return entry.date.startsWith(filters.year);
    return true;
  });
}

function allDiaryDates() {
  return state.diary.items.map((entry) => entry.date).filter(Boolean);
}

function diaryFilterPrefix() {
  const filters = state.diary.filters;
  return filters.date || filters.month || filters.year || "";
}

function clearDiaryFilters() {
  state.diary.filters = { year: "", month: "", date: "" };
}

async function renderDiary() {
  await ensureDiaryList();
  if (state.diary.composerOpen) {
    const composeDate = state.diary.composerDate || state.editingDate || new Date().toISOString().slice(0, 10);
    const existing = state.diary.items.find((entry) => entry.date === composeDate);
    if (existing && !state.editingDate) {
      state.editingDate = composeDate;
      state.notice = state.notice || "这天已有日记，已切换为编辑。";
    }
    if (state.editingDate) {
      await loadDiaryEntry(state.editingDate);
    } else {
      await loadDiaryEntry(state.selectedDate);
    }
  } else {
    await loadDiaryEntry(state.selectedDate);
  }
  if (!state.rendered.has("diary")) {
    panel("diary").innerHTML = `
      ${pageHead("", "日记", `<button class="button primary" data-open-write type="button">写一篇</button>`)}
      <section class="diary-layout">
        <aside class="card diary-list">
          <div id="diary-archive"></div>
          <div class="list" id="diary-list"></div>
        </aside>
        <div class="diary-main">
          <section class="card diary-compose" id="diary-compose" hidden></section>
          <article class="card diary-article" id="diary-article"></article>
        </div>
      </section>
    `;
    state.rendered.add("diary");
  }
  updateDiaryArchive();
  updateDiaryList();
  await updateDiaryComposer();
  updateDiaryArticle({ preserveScroll: false });
}

async function selectDiary(date) {
  if (state.view !== "diary") {
    clearDiaryFilters();
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
  const filters = state.diary.filters;
  const dates = allDiaryDates();
  const years = [...new Set(dates.map((date) => date.slice(0, 4)))];
  const months = [...new Set(dates.filter((date) => !filters.year || date.startsWith(filters.year)).map((date) => date.slice(0, 7)))];
  const dateOptions = dates.filter((date) => {
    if (filters.month) return date.startsWith(filters.month);
    if (filters.year) return date.startsWith(filters.year);
    return true;
  });
  target.innerHTML = `
    <div class="archive-picker">
      <label class="archive-field"><span>年</span><select data-filter-level="year"><option value="">全部</option>${years.map((year) => `<option value="${year}" ${filters.year === year ? "selected" : ""}>${year}</option>`).join("")}</select></label>
      <label class="archive-field"><span>月</span><select data-filter-level="month"><option value="">全部</option>${months.map((month) => `<option value="${month}" ${filters.month === month ? "selected" : ""}>${month}</option>`).join("")}</select></label>
      <label class="archive-field archive-date-field"><span>日期</span><select data-filter-level="date"><option value="">全部</option>${dateOptions.map((date) => `<option value="${date}" ${filters.date === date ? "selected" : ""}>${date}</option>`).join("")}</select></label>
    </div>
  `;
  target.querySelectorAll("[data-filter-level]").forEach((node) => node.addEventListener("change", applyDiaryFilterChange));
}

function updateDiaryList() {
  const target = document.getElementById("diary-list");
  if (!target) return;
  const items = filteredDiaryItems();
  const prefix = diaryFilterPrefix();
  target.innerHTML = items.map(entryRow).join("") || `<div class="card-body muted">${prefix ? "这个范围里没有日记。" : "还没有日记。"}</div>`;
}

async function applyDiaryFilterChange(event) {
  const level = event.currentTarget.dataset.filterLevel;
  const value = event.currentTarget.value || "";
  const filters = state.diary.filters;
  if (level === "year") {
    filters.year = value;
    if (!value || !filters.month.startsWith(value)) filters.month = "";
    if (!value || !filters.date.startsWith(value)) filters.date = "";
  }
  if (level === "month") {
    filters.month = value;
    filters.year = value ? value.slice(0, 4) : filters.year;
    if (!value || !filters.date.startsWith(value)) filters.date = "";
  }
  if (level === "date") {
    filters.date = value;
    if (value) {
      filters.year = value.slice(0, 4);
      filters.month = value.slice(0, 7);
    }
  }
  await applyDiaryFilters();
}

async function applyDiaryFilters() {
  await loadDiaryEntry("");
  updateDiaryArchive();
  updateDiaryList();
  updateDiaryArticle({ preserveScroll: false });
  updateShell();
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

async function openDiaryComposer(date = "") {
  await ensureDiaryList();
  const targetDate = date || new Date().toISOString().slice(0, 10);
  const existing = state.diary.items.find((entry) => entry.date === targetDate);
  state.view = "diary";
  state.diary.composerOpen = true;
  state.diary.composerDate = targetDate;
  state.editingDate = existing ? targetDate : date || "";
  if (existing) {
    state.diary.filters = { year: targetDate.slice(0, 4), month: targetDate.slice(0, 7), date: targetDate };
    await loadDiaryEntry(targetDate);
    state.notice = date ? "" : "这天已有日记，已切换为编辑。";
  }
  await renderDiary();
  updateShell();
}

function closeDiaryComposer() {
  state.diary.composerOpen = false;
  state.editingDate = "";
  updateDiaryComposer();
  updateShell();
}

async function updateDiaryComposer() {
  const target = document.getElementById("diary-compose");
  if (!target) return;
  if (!state.diary.composerOpen) {
    target.hidden = true;
    target.innerHTML = "";
    return;
  }
  target.hidden = false;
  const date = state.diary.composerDate || state.editingDate || new Date().toISOString().slice(0, 10);
  const selected = state.editingDate && state.diary.selected?.date === state.editingDate ? state.diary.selected : null;
  target.innerHTML = `
    <div class="card-head compact-head">
      <div><h2>${selected ? "编辑日记" : "写一篇"}</h2></div>
      <button class="text-button" data-close-write type="button">收起</button>
    </div>
    <form class="card-body form diary-compose-form" data-action="write-diary">
      <div class="form-grid compact">
        <label>日期<input name="date" type="date" value="${escapeHtml(date)}" required></label>
        <label>标题<input name="title" value="${escapeHtml(selected?.title || "")}" placeholder="给这天起一个真正的标题"></label>
        <label>情绪<input name="mood" value="${escapeHtml((selected?.mood || []).join(","))}"></label>
        <label>标签<input name="tags" value="${escapeHtml((selected?.tags || []).join(","))}"></label>
        <label>人物<input name="people" value="${escapeHtml((selected?.people || []).join(","))}"></label>
        <label>重要度<input name="importance" type="number" min="1" max="5" value="${selected?.importance || 3}"></label>
      </div>
      <label>正文<textarea name="body" required>${escapeHtml(selected?.body || "")}</textarea></label>
      <label>媒体引用<textarea name="media_refs" placeholder="每行一个图片、语音或附件引用">${escapeHtml((selected?.media_refs || []).join("\n"))}</textarea></label>
      <div class="actions"><button class="primary">保存日记</button></div>
    </form>
  `;
  target.querySelector('[data-action="write-diary"]').addEventListener("submit", saveDiary);
  target.querySelector('input[name="date"]').addEventListener("change", handleDiaryComposeDateChange);
}

async function handleDiaryComposeDateChange(event) {
  const nextDate = event.currentTarget.value;
  state.diary.composerDate = nextDate;
  const existing = state.diary.items.find((entry) => entry.date === nextDate);
  if (existing) {
    state.diary.filters = { year: nextDate.slice(0, 4), month: nextDate.slice(0, 7), date: nextDate };
    state.editingDate = nextDate;
    await loadDiaryEntry(nextDate);
    state.notice = "这天已有日记，已切换为编辑。";
  } else {
    state.editingDate = "";
    state.notice = "";
  }
  await updateDiaryComposer();
  updateDiaryList();
  updateShell();
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
  state.diary.composerOpen = false;
  state.diary.composerDate = result.entry.date;
  state.diary.filters = { year: result.entry.date.slice(0, 4), month: result.entry.date.slice(0, 7), date: result.entry.date };
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
    ${pageHead("", "查找")}
    <section class="card">
      <div class="card-body">
        <form class="searchbar" data-action="search">
          <input name="q" value="${escapeHtml(state.search.query)}" placeholder="关键词、人物、事件或情绪" />
          <button class="primary">查找</button>
        </form>
      </div>
      <div class="list">
        ${
          state.search.results.length
            ? state.search.results.map((item) => `<button class="row" data-date="${escapeHtml(item.date)}" type="button"><span>${escapeHtml(item.date)}</span><strong>${escapeHtml(item.title)}</strong><em>${escapeHtml(item.snippet || "")}</em></button>`).join("")
            : `<div class="card-body muted">暂无结果。</div>`
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
    ${pageHead("", "人物印象", `<button class="button primary" data-new-impression type="button">新建人物</button>`)}
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
      <div><h2>${escapeHtml(item?.name || "新建人物印象")}</h2></div>
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
  const payload = await api("/api/ui/media");
  state.media = payload.items || [];
  state.mediaStorage = payload.storage || { bytes: 0, count: 0, label: "0 B" };
  const assets = allMediaAssets();
  panel("media").innerHTML = `
    ${pageHead("", "媒体", `<div class="media-storage"><strong>${escapeHtml(state.mediaStorage.label || formatBytes(state.mediaStorage.bytes || 0))}</strong><span>${assets.length} 个文件</span></div>`)}
    <section class="media-gallery">
      ${assets.map(mediaCard).join("") || `<article class="card"><div class="card-body muted">还没有媒体归档。</div></article>`}
    </section>
    <div id="media-dialog-root">${state.selectedMedia ? mediaDialog(state.selectedMedia) : ""}</div>
  `;
}

function allMediaAssets() {
  return state.media.flatMap((manifest) =>
    (manifest.assets || []).map((asset) => ({ ...asset, date: asset.date || manifest.date }))
  );
}

function mediaCard(asset) {
  const id = asset.sha256 || asset.url || asset.path || asset.original_name;
  const name = asset.original_name || asset.sha256 || "未命名媒体";
  return `
    <button class="media-card" data-media-open="${escapeHtml(id)}" type="button">
      <span class="media-thumb ${asset.is_image ? "" : "file-thumb"}">
        ${asset.is_image ? `<img src="${escapeHtml(asset.url)}" alt="${escapeHtml(name)}" loading="lazy">` : iconImg("media", name)}
      </span>
      <span class="media-card-info">
        <strong>${escapeHtml(name)}</strong>
        <em>${escapeHtml(asset.date || "")} · ${escapeHtml(formatBytes(asset.size_bytes || 0))}</em>
      </span>
    </button>
  `;
}

function openMediaDetail(id) {
  state.selectedMedia = allMediaAssets().find((asset) => [asset.sha256, asset.url, asset.path, asset.original_name].includes(id)) || null;
  renderMedia();
}

function closeMediaDetail() {
  state.selectedMedia = null;
  renderMedia();
}

function mediaDialog(asset) {
  const wide = Number(asset.width || 0) >= Number(asset.height || 0);
  const layout = wide ? "landscape" : "portrait";
  const name = asset.original_name || asset.sha256 || "未命名媒体";
  const savedAt = formatDateTime(asset.saved_at) || asset.date || "";
  return `
    <div class="media-dialog-backdrop" data-media-close>
      <article class="media-dialog ${layout}" role="dialog" aria-modal="true" aria-label="${escapeHtml(name)}" onclick="event.stopPropagation()">
        <button class="media-dialog-close" data-media-close type="button" aria-label="关闭">×</button>
        <div class="media-dialog-visual">
          ${asset.is_image ? `<img src="${escapeHtml(asset.url)}" alt="${escapeHtml(name)}">` : iconImg("media", name)}
        </div>
        <div class="media-dialog-meta">
          <h2>${escapeHtml(name)}</h2>
          <dl>
            <div><dt>保存日期</dt><dd>${escapeHtml(savedAt || "未记录")}</dd></div>
            <div><dt>文件大小</dt><dd>${escapeHtml(formatBytes(asset.size_bytes || 0))}</dd></div>
            ${asset.width && asset.height ? `<div><dt>图片尺寸</dt><dd>${escapeHtml(asset.width)} × ${escapeHtml(asset.height)}</dd></div>` : ""}
            <div><dt>备注</dt><dd>${escapeHtml(asset.note || "暂无备注")}</dd></div>
          </dl>
          <a class="button ghost" href="${escapeHtml(asset.url)}" target="_blank" rel="noreferrer">打开原图</a>
        </div>
      </article>
    </div>
  `;
}

function formatBytes(value = 0) {
  let size = Number(value) || 0;
  const units = ["B", "KB", "MB", "GB"];
  for (const unit of units) {
    if (size < 1024 || unit === "GB") return unit === "B" ? `${Math.round(size)} B` : `${size.toFixed(1)} ${unit}`;
    size /= 1024;
  }
  return `${value} B`;
}

function formatDateTime(value = "") {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

async function renderSettings() {
  const payload = await api("/api/ui/settings");
  state.settings = payload;
  const settings = payload.settings;
  if (!["modules", "access", "backup"].includes(state.settingsSection)) state.settingsSection = "modules";
  panel("settings").innerHTML = `
    <section class="settings-layout settings-layout-single">
      <div class="settings-content">
        <section class="settings-panel ${settingsPanelClass("modules")}" data-settings-panel="modules">
          <form data-action="save-settings">
            ${state.settingsModuleDetail ? moduleDetailPage(payload, state.settingsModuleDetail) : moduleManagerPage(payload)}
          </form>
        </section>
        <section class="settings-panel ${settingsPanelClass("access")}" data-settings-panel="access">
          <section class="settings-page">
            <div class="settings-page-head">
              <h2>访问密钥</h2>
            </div>
            <form class="settings-collapse form" data-action="save-security">
              <div class="form-grid compact">
                <label>新管理员密码<input name="admin_password" type="password" placeholder="留空则不修改"></label>
                <label>外部接口密钥<input name="bot_api_token" value="${escapeHtml(payload.security.bot_api_token || "")}"></label>
              </div>
              <details><summary>外部接口选项</summary>${check("generate_bot_api_token", "保存时生成新的外部接口密钥", false)}${check("external_api_enabled", "启用外部接口", payload.security.external_api_enabled)}</details>
              <div class="actions"><button class="primary">保存访问密钥</button></div>
            </form>
          </section>
        </section>
        <section class="settings-panel ${settingsPanelClass("backup")}" data-settings-panel="backup">
          <section class="settings-page">
            <div class="settings-page-head">
              <h2>导入导出</h2>
            </div>
            <div class="settings-collapse form">
              <form class="form-grid compact" data-action="export-backup">
                <label>导出范围<select name="package_type">${exportOptions(payload.module_catalog)}</select></label>
                <label>模块 ID<input name="module_id" placeholder="导出自定义模块或拓展包时填写"></label>
                ${check("include_security", "包含管理员密码和接口密钥", false)}
                <div class="actions"><button class="primary">导出所选范围</button></div>
              </form>
              <form class="upload-zone" data-action="import-backup">
                <input name="backup_file" type="file" accept=".zip" required>
                <label>导入策略<select name="strategy"><option value="safe">安全合并：已有文件跳过</option><option value="overwrite">覆盖合并：先备份再覆盖</option></select></label>
                <div class="actions"><button class="primary">导入备份包</button></div>
                <p class="muted">导入会读取清单，自动识别完整备份、日记、人物印象、媒体、个性化前端、自定义模块或拓展包。</p>
              </form>
            </div>
          </section>
        </section>
      </div>
    </section>
  `;
  panel("settings").querySelector('[data-action="save-settings"]').addEventListener("submit", saveSettings);
  panel("settings").querySelector('[data-action="save-security"]').addEventListener("submit", saveSecurity);
  panel("settings").querySelector('[data-action="export-backup"]').addEventListener("submit", exportBackup);
  panel("settings").querySelector('[data-action="import-backup"]').addEventListener("submit", importBackup);
}

function settingsTab(id, label) {
  return `
    <button class="settings-tab ${state.settingsSection === id ? "active" : ""}" data-settings-section="${id}" type="button">
      <span>${escapeHtml(label)}</span>
    </button>
  `;
}

function settingsPanelClass(id) {
  return state.settingsSection === id ? "active" : "";
}

async function switchSettingsSection(id) {
  state.view = "settings";
  state.settingsMenuOpen = true;
  state.settingsSection = id;
  state.settingsModuleDetail = "";
  await renderSettings();
  updateShell();
}

async function openModuleSettings(id) {
  state.settingsSection = "modules";
  state.settingsModuleDetail = id || "";
  await renderSettings();
  updateShell();
}

async function closeModuleSettings() {
  state.settingsModuleDetail = "";
  await renderSettings();
  updateShell();
}

async function setModuleFilter(filter) {
  state.moduleFilter = filter || "all";
  await renderSettings();
  updateShell();
}

function moduleManagerPage(payload) {
  const settings = payload.settings;
  const modules = moduleCatalogItems(payload, settings);
  const visibleModules = state.moduleFilter === "all" ? modules : modules.filter((module) => module.category === state.moduleFilter);
  return `
    <section class="module-manager-page">
      <div class="module-page-head">
        <div>
          <h2>模块管理</h2>
          <p class="muted">管理小窝里的功能、外观和拓展。</p>
        </div>
      </div>
      ${moduleWarnings(payload.module_catalog.conflicts || [])}
      ${moduleWarnings(payload.module_catalog.appearance_conflicts || [])}
      <div class="module-stats">
        ${moduleStat("全部模块", modules.length)}
        ${moduleStat("已启用", modules.filter((item) => item.enabled).length)}
        ${moduleStat("外观模块", modules.filter((item) => item.category === "appearance").length)}
      </div>
      <div class="module-filterbar">
        ${moduleFilterButton("all", "全部", modules.length)}
        ${moduleFilterButton("core", "功能模块", modules.filter((item) => item.category === "core").length)}
        ${moduleFilterButton("appearance", "外观模块", modules.filter((item) => item.category === "appearance").length)}
        ${moduleFilterButton("extension", "拓展模块", modules.filter((item) => item.category === "extension").length)}
      </div>
      <div class="module-card-grid module-card-grid-standalone">
        ${moduleHiddenInputs(modules)}
        ${visibleModules.length ? visibleModules.map((module) => moduleCard(module, module.enabled ? [module.id] : [], module.inputName, module.groupKind)).join("") : `<p class="muted module-empty">暂无模块。</p>`}
      </div>
    </section>
  `;
}

function moduleCatalogItems(payload, settings) {
  const official = payload.module_catalog.official || [];
  const officialCore = official.filter((module) => module.id !== "webui");
  const officialAppearance = official.filter((module) => module.id === "webui");
  return [
    ...decorateModules(officialCore, settings.enabled_official_modules, "enabled_official_modules", "official", "core"),
    ...decorateModules(payload.module_catalog.custom || [], settings.enabled_custom_modules, "enabled_custom_modules", "custom", "core"),
    ...decorateModules(payload.module_catalog.extensions || [], settings.enabled_custom_extensions, "enabled_custom_extensions", "extension", "extension"),
    ...decorateModules(officialAppearance, settings.enabled_official_modules, "enabled_official_modules", "official", "appearance"),
    ...decorateModules(payload.module_catalog.appearance || [], settings.enabled_appearance_modules || [], "enabled_appearance_modules", "appearance", "appearance"),
  ];
}

function decorateModules(modules, enabled = [], inputName, groupKind, category) {
  return modules.map((module) => ({ ...module, enabled: enabled.includes(module.id), inputName, groupKind, category }));
}

function moduleStat(label, value) {
  return `<div class="module-stat"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function moduleFilterButton(id, label, count) {
  return `
    <button class="module-filter ${state.moduleFilter === id ? "active" : ""}" data-module-filter="${escapeHtml(id)}" type="button">
      <span>${escapeHtml(label)}</span><strong>${escapeHtml(count)}</strong>
    </button>
  `;
}

function moduleHiddenInputs(modules) {
  const names = Array.from(new Set(modules.map((module) => module.inputName)));
  const enabledByName = {};
  const visibleByName = {};
  for (const module of modules) {
    if (!enabledByName[module.inputName]) enabledByName[module.inputName] = [];
    if (!visibleByName[module.inputName]) visibleByName[module.inputName] = new Set();
    if (module.enabled) enabledByName[module.inputName].push(module.id);
    if (state.moduleFilter === "all" || module.category === state.moduleFilter) visibleByName[module.inputName].add(module.id);
  }
  return names
    .map((name) => {
      const visibleName = state.moduleFilter === "all" || modules.some((module) => module.inputName === name && module.category === state.moduleFilter);
      const present = visibleName ? `<input name="__module_group_present" value="${escapeHtml(name)}" type="hidden">` : "";
      const preserved = (enabledByName[name] || [])
        .filter((id) => !visibleByName[name]?.has(id))
        .map((id) => `<input name="${escapeHtml(name)}" value="${escapeHtml(id)}" type="hidden" data-preserved-module="${escapeHtml(id)}">`)
        .join("");
      return present + preserved;
    })
    .join("");
}

function moduleDetailPage(payload, detailKey) {
  const settings = payload.settings;
  const module = findModuleByDetailKey(payload.module_catalog, detailKey);
  const title = module?.name || moduleDetailTitle(detailKey);
  const description = module?.description || moduleDetailDescription(detailKey);
  return `
    <article class="module-detail-card">
      <div class="module-detail-head">
        <button class="button module-detail-back" data-settings-back type="button">返回</button>
        <div>
          <h2>${escapeHtml(title)}</h2>
          ${description ? `<p class="muted">${escapeHtml(description)}</p>` : ""}
        </div>
        <div class="module-detail-tags">
          ${module ? moduleBadges(module, detailKey.startsWith("appearance:") ? "appearance" : module.kind).join("") : ""}
        </div>
      </div>
      <div class="module-detail-body form">
        ${moduleSettingsBody(payload, detailKey)}
      </div>
      <div class="module-detail-actions">
        <button class="button" data-settings-back type="button">取消</button>
        <button class="primary" data-save-close>保存并关闭</button>
      </div>
    </article>
  `;
}

function moduleSettingsBody(payload, detailKey) {
  const settings = payload.settings;
  if (detailKey === "diary") {
    return `
      <div class="setting-line"><div><strong>日记模块</strong><p class="muted">开启后可以记录和查看日记。</p></div>${switchControl("enable_diary_module", settings.enable_diary_module)}</div>
      <div class="setting-line"><div><strong>自动回想</strong><p class="muted">需要时让 bot 参考以前的日记。</p></div>${switchControl("memory_recall_enabled", settings.memory_recall_enabled)}</div>
      <div class="form-grid compact">
        <label>回想方式<select name="memory_recall_policy"><option value="conservative" ${settings.memory_recall_policy === "conservative" ? "selected" : ""}>只在需要时</option><option value="active" ${settings.memory_recall_policy === "active" ? "selected" : ""}>更主动</option></select></label>
        <label>每次参考数量<input name="search_default_top_k" type="number" min="1" max="20" value="${settings.search_default_top_k}"></label>
        <label>摘要长度<input name="search_snippet_chars" type="number" min="80" max="360" value="${settings.search_snippet_chars}"></label>
        <label>日记保存方式<select name="diary_archive_granularity"><option value="day" ${settings.diary_archive_granularity === "day" ? "selected" : ""}>按天</option><option value="month" ${settings.diary_archive_granularity === "month" ? "selected" : ""}>按月</option><option value="year" ${settings.diary_archive_granularity === "year" ? "selected" : ""}>按年</option></select></label>
      </div>
    `;
  }
  if (detailKey === "impressions") {
    return `
      <div class="setting-line"><div><strong>人物印象模块</strong><p class="muted">记录人物关系和长期印象。</p></div>${switchControl("enable_impressions_module", settings.enable_impressions_module)}</div>
      <div class="setting-line"><div><strong>日记后自动整理</strong><p class="muted">写完日记后，让 bot 判断是否需要更新人物印象。</p></div>${switchControl("auto_impression_from_diary", settings.auto_impression_from_diary)}</div>
      <div class="form-grid compact">
        <label>写入强度<select name="impression_write_level">
          <option value="off" ${settings.impression_write_level === "off" ? "selected" : ""}>关闭：不自动写印象</option>
          <option value="light" ${settings.impression_write_level === "light" ? "selected" : ""}>轻量：只记录明确变化</option>
          <option value="balanced" ${settings.impression_write_level === "balanced" ? "selected" : ""}>均衡：推荐</option>
          <option value="deep" ${settings.impression_write_level === "deep" ? "selected" : ""}>深入：补充更多细节</option>
        </select></label>
        <label>更新策略<select name="impression_update_strategy">
          <option value="manual" ${settings.impression_update_strategy === "manual" ? "selected" : ""}>手动</option>
          <option value="existing_only" ${settings.impression_update_strategy === "existing_only" ? "selected" : ""}>只更新已有人物</option>
          <option value="evidence_only" ${settings.impression_update_strategy === "evidence_only" ? "selected" : ""}>有证据才更新</option>
          <option value="aggressive" ${settings.impression_update_strategy === "aggressive" ? "selected" : ""}>允许新建人物</option>
        </select></label>
        <label>确认程度<input name="impression_min_confidence" type="number" min="1" max="5" value="${settings.impression_min_confidence || 3}"></label>
      </div>
      ${check("impression_allow_new_people", "允许自动新建人物", settings.impression_allow_new_people)}
      ${check("show_impression_prompt", "写日记时显示人物提示", settings.show_impression_prompt)}
      <label>印象写入规范<textarea name="impression_prompt">${escapeHtml(settings.impression_prompt || "")}</textarea></label>
    `;
  }
  if (detailKey === "webui") {
    return `
      <div class="brand-settings">
        <div class="brand-preview">${settings.brand_avatar_url ? `<img src="${escapeHtml(settings.brand_avatar_url)}" alt="${escapeHtml(settings.site_title || "小窝")}">` : `<span>${escapeHtml((settings.site_title || "小窝").slice(0, 1))}</span>`}</div>
        <div class="form-grid compact">
          <label>小窝标题<input name="site_title" value="${escapeHtml(settings.site_title || "小窝")}" placeholder="例如：小莫的小窝"></label>
          <label>小窝副标题<input name="site_subtitle" value="${escapeHtml(settings.site_subtitle || "把今天安放好，旧事也能被轻轻找回来")}" placeholder="显示在首页标题下面"></label>
          <label>头像地址<input name="brand_avatar_url" value="${escapeHtml(settings.brand_avatar_url || "")}" placeholder="可填写图片地址，也可上传"></label>
          <label>上传头像<input name="brand_avatar_file" type="file" accept="image/png,image/jpeg,image/webp,image/gif"></label>
          <label>当前样式<select name="active_frontend_style">${payload.frontend_styles.map((style) => `<option value="${escapeHtml(style.id)}" ${settings.active_frontend_style === style.id ? "selected" : ""}>${escapeHtml(style.name)} · ${escapeHtml(styleKindLabel(style.kind))}</option>`).join("")}</select></label>
          <label>自定义页面目录<input name="custom_webui_dir" value="${escapeHtml(settings.custom_webui_dir || "")}" placeholder="留空使用默认目录"></label>
        </div>
      </div>
      ${check("backup_custom_before_update", "更新前备份自定义内容", settings.backup_custom_before_update)}
    `;
  }
  if (detailKey === "media") {
    return `
      <div class="setting-line"><div><strong>媒体模块</strong><p class="muted">开启后可以保存图片、语音和附件。</p></div>${switchControl("enable_media_module", settings.enable_media_module)}</div>
      <div class="setting-line"><div><strong>日记里插入图片</strong><p class="muted">允许日记引用已保存的图片或附件。</p></div>${switchControl("allow_media_refs", settings.allow_media_refs)}</div>
      <div class="setting-line"><div><strong>bot 自动导入媒体</strong><p class="muted">允许 bot 把图片或附件放进小窝。</p></div>${switchControl("media_allow_bot_import", settings.media_allow_bot_import)}</div>
      <div class="setting-line"><div><strong>自动整理相册</strong><p class="muted">按日期自动整理媒体。</p></div>${switchControl("media_auto_album", settings.media_auto_album)}</div>
      <div class="form-grid compact">
        <label>每天最多保存<input name="media_max_items_per_day" type="number" min="1" max="500" value="${settings.media_max_items_per_day || 80}"></label>
        <label>图片保存方式<select name="media_storage_strategy">
          <option value="copy" ${settings.media_storage_strategy !== "move" ? "selected" : ""}>复制：保留原文件</option>
          <option value="move" ${settings.media_storage_strategy === "move" ? "selected" : ""}>剪切：移入小窝</option>
        </select></label>
      </div>
    `;
  }
  return `<div class="notice soft">这个模块暂时没有可调整的选项。</div>`;
}

function moduleDetailTitle(detailKey) {
  if (detailKey === "diary") return "日记模块";
  if (detailKey === "impressions") return "人物印象模块";
  if (detailKey === "media") return "媒体模块";
  if (detailKey === "webui") return "小窝 WebUI";
  return detailKey;
}

function moduleDetailDescription(detailKey) {
  if (detailKey === "webui") return "管理标题、头像和页面样式。";
  return "";
}

function findModuleByDetailKey(catalog, detailKey) {
  const all = [
    ...(catalog.official || []).map((item) => ({ ...item, detailKey: item.id })),
    ...(catalog.custom || []).map((item) => ({ ...item, detailKey: `custom:${item.id}` })),
    ...(catalog.extensions || []).map((item) => ({ ...item, detailKey: `extension:${item.id}` })),
    ...(catalog.appearance || []).map((item) => ({ ...item, detailKey: `appearance:${item.id}` })),
  ];
  return all.find((item) => item.detailKey === detailKey || item.id === detailKey);
}

function check(name, label, checked) {
  return `<label class="check"><input name="${name}" type="checkbox" ${checked ? "checked" : ""}>${escapeHtml(label)}</label>`;
}

function switchControl(name, checked) {
  return `<label class="switch"><input name="${name}" type="checkbox" ${checked ? "checked" : ""}><span></span></label>`;
}

function moduleWarnings(conflicts) {
  if (!conflicts.length) return "";
  return `<div class="module-warnings">${conflicts.map((item) => `<div class="notice ${item.level === "danger" ? "error" : "soft"}"><strong>${escapeHtml(item.title)}：</strong>${escapeHtml(item.message)}</div>`).join("")}</div>`;
}

function moduleCard(module, enabled = [], inputName, groupKind = "") {
  const detailKey = groupKind === "custom" ? `custom:${module.id}` : groupKind === "extension" ? `extension:${module.id}` : groupKind === "appearance" ? `appearance:${module.id}` : module.id;
  const checked = enabled.includes(module.id);
  return `
    <article class="module-card ${checked ? "enabled" : ""}">
      <div class="module-card-icon">${iconImg(moduleIcon(module, groupKind), module.name || module.id)}</div>
      <div class="module-card-main">
        <div class="module-card-title">
          <strong>${escapeHtml(module.name || module.id)}</strong>
          <span class="module-status ${checked ? "on" : "off"}">${checked ? "运行中" : "已停用"}</span>
        </div>
        <em>${escapeHtml(module.description || "没有说明。")}</em>
        <span class="chips small">${moduleBadges(module, groupKind).join("")}</span>
      </div>
      <div class="module-card-actions">
        <button class="button" data-module-settings="${escapeHtml(detailKey)}" type="button">配置</button>
        <label class="module-card-toggle ${checked ? "on" : "off"}">
          <input name="${inputName}" value="${escapeHtml(module.id)}" type="checkbox" data-module-toggle data-module-id="${escapeHtml(module.id)}" data-module-input="${escapeHtml(inputName)}" ${checked ? "checked" : ""}>
          <span>${checked ? "已开启" : "已关闭"}</span>
        </label>
      </div>
    </article>
  `;
}

function moduleIcon(module, groupKind = "") {
  if (module.id === "diary") return "diary";
  if (module.id === "impressions") return "impressions";
  if (module.id === "media") return "media";
  if (module.id === "webui") return "webui";
  if (groupKind === "appearance") return "appearance";
  if (groupKind === "extension") return "modules";
  return "modules";
}

function moduleBadges(module, groupKind = "") {
  const conflicts = module.conflicts_with || [];
  const isAppearance = groupKind === "appearance" || module.id === "webui";
  const appearanceLabel = isAppearance ? (module.entry_label || (module.appearance_mode === "global" ? "全局替换" : "外观模块")) : "";
  const badges = [
    `<span class="chip">${escapeHtml(moduleSourceLabel(module, groupKind))}</span>`,
    appearanceLabel ? `<span class="chip ${module.appearance_mode === "global" ? "danger-chip" : ""}">${escapeHtml(appearanceLabel)}</span>` : "",
    groupKind === "extension" ? `<span class="chip">拓展模块</span>` : "",
    conflicts.length ? `<span class="chip danger-chip">有冲突</span>` : "",
  ];
  return badges.filter(Boolean);
}

function moduleSourceLabel(module, groupKind = "") {
  if (groupKind === "extension") return "补充拓展";
  if (module.kind === "official") return "官方模块";
  if (groupKind === "appearance") return "外观模块";
  if (module.kind === "custom") return "自定义模块";
  return moduleTypeLabel(module.type);
}

function moduleTypeLabel(type = "") {
  if (type === "extension") return "拓展包";
  if (type === "module") return "完整模块";
  if (type === "appearance") return "外观模块";
  return type || "模块";
}

function styleKindLabel(kind = "") {
  if (kind === "official") return "官方";
  if (kind === "custom") return "自定义";
  if (kind === "missing") return "未找到";
  return kind || "样式";
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
  const shouldClose = event.submitter?.dataset.saveClose !== undefined;
  const formEl = event.currentTarget;
  const form = new FormData(formEl);
  const current = state.settings?.settings || {};
  const hasField = (name) => formEl.querySelector(`[name="${CSS.escape(name)}"]`) !== null;
  const valueField = (name, fallback = "") => (hasField(name) ? form.get(name) : fallback);
  const boolField = (name, fallback = false) => (hasField(name) ? form.has(name) : Boolean(fallback));
  const numberField = (name, fallback = 0) => Number(valueField(name, fallback) || fallback || 0);
  const listField = (name, fallback = []) => {
    if (form.getAll("__module_group_present").includes(name)) return form.getAll(name);
    return hasField(name) ? form.getAll(name) : fallback;
  };
  let avatarUrl = String(valueField("brand_avatar_url", current.brand_avatar_url || ""));
  const avatarFile = form.get("brand_avatar_file");
  if (avatarFile && avatarFile.size) {
    avatarUrl = await uploadAvatar(avatarFile);
  }
  const payload = {
    site_title: valueField("site_title", current.site_title || "小窝"),
    site_subtitle: valueField("site_subtitle", current.site_subtitle || "把今天安放好，旧事也能被轻轻找回来"),
    brand_avatar_url: avatarUrl,
    search_default_top_k: numberField("search_default_top_k", current.search_default_top_k || 5),
    search_snippet_chars: numberField("search_snippet_chars", current.search_snippet_chars || 180),
    memory_recall_enabled: boolField("memory_recall_enabled", current.memory_recall_enabled),
    memory_recall_policy: valueField("memory_recall_policy", current.memory_recall_policy || "conservative"),
    enable_diary_module: boolField("enable_diary_module", current.enable_diary_module),
    diary_archive_granularity: valueField("diary_archive_granularity", current.diary_archive_granularity || "day"),
    enable_media_module: boolField("enable_media_module", current.enable_media_module),
    allow_media_refs: boolField("allow_media_refs", current.allow_media_refs),
    media_max_items_per_day: numberField("media_max_items_per_day", current.media_max_items_per_day || 80),
    media_allow_bot_import: boolField("media_allow_bot_import", current.media_allow_bot_import),
    media_auto_album: boolField("media_auto_album", current.media_auto_album),
    media_storage_strategy: valueField("media_storage_strategy", current.media_storage_strategy || "copy"),
    enable_impressions_module: boolField("enable_impressions_module", current.enable_impressions_module),
    auto_impression_from_diary: boolField("auto_impression_from_diary", current.auto_impression_from_diary),
    impression_write_level: valueField("impression_write_level", current.impression_write_level || "balanced"),
    impression_update_strategy: valueField("impression_update_strategy", current.impression_update_strategy || "evidence_only"),
    impression_allow_new_people: boolField("impression_allow_new_people", current.impression_allow_new_people),
    impression_min_confidence: numberField("impression_min_confidence", current.impression_min_confidence || 3),
    show_impression_prompt: boolField("show_impression_prompt", current.show_impression_prompt),
    active_frontend_style: valueField("active_frontend_style", current.active_frontend_style || "default"),
    enabled_official_modules: listField("enabled_official_modules", current.enabled_official_modules || []),
    enabled_custom_modules: listField("enabled_custom_modules", current.enabled_custom_modules || []),
    enabled_custom_extensions: listField("enabled_custom_extensions", current.enabled_custom_extensions || []),
    enabled_appearance_modules: listField("enabled_appearance_modules", current.enabled_appearance_modules || []),
    custom_webui_dir: valueField("custom_webui_dir", current.custom_webui_dir || ""),
    backup_custom_before_update: boolField("backup_custom_before_update", current.backup_custom_before_update),
    impression_prompt: valueField("impression_prompt", current.impression_prompt || ""),
  };
  if (event.submitter?.dataset.moduleToggle !== undefined) {
    const moduleId = event.submitter.dataset.moduleId;
    const moduleInput = event.submitter.dataset.moduleInput;
    if (moduleInput === "enabled_official_modules") {
      payload.enabled_official_modules = syncEnabledModule(payload.enabled_official_modules, moduleId, event.submitter.checked);
      payload.enable_diary_module = payload.enabled_official_modules.includes("diary");
      payload.enable_media_module = payload.enabled_official_modules.includes("media");
      payload.enable_impressions_module = payload.enabled_official_modules.includes("impressions");
    } else if (moduleInput === "enabled_custom_modules") {
      payload.enabled_custom_modules = syncEnabledModule(payload.enabled_custom_modules, moduleId, event.submitter.checked);
    } else if (moduleInput === "enabled_custom_extensions") {
      payload.enabled_custom_extensions = syncEnabledModule(payload.enabled_custom_extensions, moduleId, event.submitter.checked);
    } else if (moduleInput === "enabled_appearance_modules") {
      payload.enabled_appearance_modules = syncEnabledModule(payload.enabled_appearance_modules, moduleId, event.submitter.checked);
    }
  }
  if (form.getAll("__module_group_present").includes("enabled_official_modules")) {
    payload.enabled_official_modules = Array.from(new Set(payload.enabled_official_modules));
    payload.enable_diary_module = payload.enabled_official_modules.includes("diary");
    payload.enable_media_module = payload.enabled_official_modules.includes("media");
    payload.enable_impressions_module = payload.enabled_official_modules.includes("impressions");
  } else {
    if (hasField("enable_diary_module")) {
      payload.enabled_official_modules = syncEnabledModule(payload.enabled_official_modules, "diary", payload.enable_diary_module);
    }
    if (hasField("enable_media_module")) {
      payload.enabled_official_modules = syncEnabledModule(payload.enabled_official_modules, "media", payload.enable_media_module);
    }
    if (hasField("enable_impressions_module")) {
      payload.enabled_official_modules = syncEnabledModule(payload.enabled_official_modules, "impressions", payload.enable_impressions_module);
    }
  }
  await api("/api/ui/settings", { method: "POST", body: JSON.stringify(payload) });
  state.toast = "设置已保存";
  state.error = "";
  state.bootstrap = null;
  if (shouldClose) state.settingsModuleDetail = "";
  await renderSettings();
  updateShell();
  window.setTimeout(() => {
    state.toast = "";
    updateShell();
  }, 2200);
}

async function saveModuleToggle(input) {
  const formEl = input.closest("form");
  if (!formEl) return;
  try {
    await saveSettings({ preventDefault() {}, currentTarget: formEl, submitter: input });
  } catch (err) {
    state.error = err.message || "保存失败";
    updateShell();
  }
}

function syncEnabledModule(items, moduleId, enabled) {
  const next = new Set(items || []);
  if (enabled) next.add(moduleId);
  else next.delete(moduleId);
  return Array.from(next);
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
