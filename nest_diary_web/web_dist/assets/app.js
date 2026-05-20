const APP_VERSION = "0.5.7";

const DIARY_T2I_TEMPLATES = [
  {
    id: "plain_note",
    name: "清简便签",
    tone: "浅色、易读、适合日常推送",
    template: `<div style="width:760px;padding:44px;font-family:'Microsoft YaHei',sans-serif;background:#fffdf8;color:#242830;border:2px solid #242830;">
  <p style="margin:0 0 12px;color:#176f66;font-size:18px;font-weight:800;">{{ date }} · {{ notebook_name }}</p>
  <h1 style="margin:0 0 22px;font-size:34px;line-height:1.2;">{{ title }}</h1>
  <div style="white-space:pre-wrap;font-size:20px;line-height:1.75;">{{ body }}</div>
</div>`,
  },
  {
    id: "terminal_report",
    name: "终端报告",
    tone: "冷灰信息卡，适合群聊日报",
    template: `<div style="width:820px;padding:38px;font-family:'Microsoft YaHei',sans-serif;background:#f1f4f2;color:#1f2527;border:1px solid #2c3b3b;">
  <div style="display:flex;justify-content:space-between;gap:18px;border-bottom:3px solid #2c3b3b;padding-bottom:14px;margin-bottom:24px;">
    <strong style="font-size:18px;">小窝日记</strong><span style="color:#58706b;font-weight:800;">{{ date }} / {{ notebook_name }}</span>
  </div>
  <h1 style="margin:0 0 20px;font-size:32px;line-height:1.18;">{{ title }}</h1>
  <div style="white-space:pre-wrap;font-size:19px;line-height:1.72;">{{ body }}</div>
</div>`,
  },
  {
    id: "magazine_page",
    name: "杂志页",
    tone: "留白更大，适合私聊推送",
    template: `<div style="width:760px;padding:52px 48px;font-family:'Microsoft YaHei',sans-serif;background:#fbfaf5;color:#202124;">
  <div style="width:64px;height:5px;background:#d25f45;margin-bottom:28px;"></div>
  <p style="margin:0 0 16px;color:#6a756f;font-size:17px;font-weight:800;">{{ date }} · {{ notebook_name }}</p>
  <h1 style="margin:0 0 26px;font-size:38px;line-height:1.16;">{{ title }}</h1>
  <div style="white-space:pre-wrap;font-size:20px;line-height:1.86;">{{ body }}</div>
</div>`,
  },
];

const app = document.getElementById("app");
const state = {
  view: initialViewFromLocation(),
  selectedDate: initialDateFromLocation(),
  editingDate: initialEditDateFromLocation(),
  selectedImpressionName: initialImpressionFromLocation(),
  bootstrap: null,
  notebooks: [],
  diary: {
    items: [],
    archive: [],
    selected: null,
    loaded: false,
    composerOpen: initialComposerFromLocation(),
    composerDate: initialComposeDateFromLocation(),
    filters: initialDiaryFilters(),
  },
  search: { query: initialSearchFromLocation(), notebook_id: initialNotebookFromLocation(), results: [], backend: "" },
  impressions: [],
  selectedImpression: null,
  media: [],
  mediaStorage: { bytes: 0, count: 0, label: "0 B" },
  mediaOrganization: { folders: [], asset_locations: {}, trash: [] },
  selectedMedia: null,
  mediaFloating: false,
  mediaFloatPreferred: false,
  mediaFloatResumePending: false,
  mediaMode: "main",
  activeMediaFolderId: "",
  expandedMediaFolderIds: [],
  mediaSuppressClickUntil: 0,
  mediaFloatPositions: {},
  mediaFolderModalOpen: false,
  mediaFolderEditingId: "",
  mediaNoteEditing: false,
  settings: null,
  notice: "",
  toast: "",
  error: "",
  rendered: new Set(),
  settingsMenuOpen: initialViewFromLocation() === "settings",
  settingsSection: "modules",
  settingsModuleDetail: "",
  moduleFilter: "all",
  t2iTemplateDialogOpen: false,
  t2iCustomOpen: false,
  notebookDeleteIds: [],
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
  const notebook_id = initialNotebookFromLocation();
  return date ? { notebook_id, year: date.slice(0, 4), month: date.slice(0, 7), date } : { notebook_id, year: "", month: "", date: "" };
}

function initialNotebookFromLocation() {
  return new URLSearchParams(window.location.search).get("notebook_id") || "";
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
      <div id="global-dialog-root"></div>
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

function refreshThemeStylesheet() {
  const link = document.getElementById("theme-stylesheet") || document.querySelector('link[rel="stylesheet"][href*="/theme.css"]');
  if (!link) return;
  const href = new URL(link.getAttribute("href") || "/theme.css", window.location.origin);
  href.searchParams.set("v", String(Date.now()));
  link.setAttribute("href", `${href.pathname}${href.search}`);
}

function activeT2iTemplate(settings = {}) {
  const custom = String(settings.diary_t2i_template || "").trim();
  const name = settings.diary_t2i_template_name || "";
  const customItem = customT2iTemplates(settings).find((item) => item.id === name);
  if (customItem) return customItem;
  const builtin = DIARY_T2I_TEMPLATES.find((item) => item.id === name);
  if (name === "custom" && custom && !custom.startsWith("{")) return { id: "custom", name: "自定义模板", tone: "使用你添加的模板", template: custom };
  if (builtin) return builtin;
  return DIARY_T2I_TEMPLATES[0];
}

function t2iTemplateById(id) {
  return DIARY_T2I_TEMPLATES.find((item) => item.id === id) || DIARY_T2I_TEMPLATES[0];
}

function customT2iTemplates(settings = {}) {
  const raw = String(settings.diary_t2i_template || "").trim();
  if (!raw) return [];
  if (!raw.startsWith("{")) {
    return settings.diary_t2i_template_name === "custom"
      ? [{ id: "custom", name: "自定义模板", tone: "你添加的模板", template: raw }]
      : [];
  }
  try {
    const parsed = JSON.parse(raw);
    const templates = Array.isArray(parsed.templates) ? parsed.templates : [];
    return templates
      .map((item) => ({
        id: String(item.id || `custom_${Date.now()}`).trim(),
        name: String(item.name || "自定义模板").trim(),
        tone: String(item.tone || "自定义").trim(),
        template: String(item.template || "").trim(),
      }))
      .filter((item) => item.id && item.template);
  } catch (_) {
    return [];
  }
}

function t2iTemplateStore(templates = []) {
  return JSON.stringify({ templates: templates.map((item) => ({ id: item.id, name: item.name, tone: item.tone, template: item.template })) });
}

function t2iPreviewHtml(template) {
  return String(template || "")
    .replaceAll("{{ date }}", "2026-05-20")
    .replaceAll("{{ notebook_name }}", "主群日记本")
    .replaceAll("{{ title }}", "今天的小窝被认真整理了一遍")
    .replaceAll("{{ body }}", "今天把日记本、推送和权限重新分清了。重要的是，群聊和私聊不会混在一起，写日记也会先看证据，再决定要不要记录。");
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
  state.notebooks = state.bootstrap?.notebooks || state.notebooks || [];
}

async function setView(view, options = {}) {
  if (view !== "media") {
    if (state.view === "media" && state.mediaFloating) {
      state.mediaFloatPreferred = true;
      state.mediaFloating = false;
      state.mediaFloatResumePending = true;
    }
    stopMediaFloat();
    if (state.view === "media") state.mediaFloatPositions = {};
    state.selectedMedia = null;
    state.mediaFolderModalOpen = false;
    state.mediaFolderEditingId = "";
    state.t2iTemplateDialogOpen = false;
    state.t2iCustomOpen = false;
    renderGlobalDialogs();
  }
  state.view = view;
  state.notice = options.keepNotice ? state.notice : "";
  state.error = "";
  if (Object.prototype.hasOwnProperty.call(options, "date")) state.selectedDate = options.date || "";
  if (Object.prototype.hasOwnProperty.call(options, "notebook_id")) {
    state.diary.filters.notebook_id = options.notebook_id || "";
    state.search.notebook_id = options.notebook_id || "";
  }
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
    const target = event.target.closest("[data-view], [data-date], [data-open-write], [data-close-write], [data-edit-date], [data-search-query], [data-impression-name], [data-new-impression], [data-media-open], [data-media-close], [data-media-note-edit], [data-media-folder-create], [data-media-folder-edit], [data-media-folder-modal-close], [data-media-trash], [data-media-restore], [data-media-delete], [data-media-open-original], [data-media-toggle-float], [data-media-mode], [data-media-folder-collapse], [data-media-folder-expand], [data-media-folder-open], [data-media-folder-close], [data-media-dropdown], [data-settings-section], [data-module-settings], [data-settings-back], [data-module-filter], [data-notebook-add], [data-notebook-delete], [data-t2i-open], [data-t2i-close], [data-t2i-select], [data-t2i-custom-toggle], [data-t2i-custom-save]");
    if (!target) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (
      target.classList?.contains("media-dialog-backdrop") &&
      event.target !== target &&
      (target.dataset.mediaClose !== undefined || target.dataset.mediaFolderModalClose !== undefined)
    ) {
      return;
    }
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
      selectDiary(target.dataset.date, target.dataset.notebookId || "");
      return;
    }
    if (target.dataset.editDate) {
      openDiaryComposer(target.dataset.editDate, target.dataset.notebookId || "");
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
      if (Date.now() < state.mediaSuppressClickUntil && !target.closest("button, .button")) return;
      openMediaDetail(target.dataset.mediaOpen);
      return;
    }
    if (target.dataset.mediaClose !== undefined) {
      closeMediaDetail();
      return;
    }
    if (target.dataset.mediaNoteEdit !== undefined) {
      state.mediaNoteEditing = true;
      state.toast = "备注可以编辑了，写好后点保存备注";
      renderGlobalDialogs();
      updateShell();
      clearToastSoon();
      return;
    }
    if (target.dataset.mediaFolderCreate !== undefined) {
      openMediaFolderModal();
      return;
    }
    if (target.dataset.mediaFolderEdit) {
      openMediaFolderModal(target.dataset.mediaFolderEdit);
      return;
    }
    if (target.dataset.mediaFolderModalClose !== undefined) {
      closeMediaFolderModal();
      return;
    }
    if (target.dataset.mediaTrash) {
      trashMediaItem(target.dataset.mediaTrash, target.dataset.mediaId || target.dataset.mediaTrashId || "");
      return;
    }
    if (target.dataset.mediaRestore) {
      restoreMediaItem(target.dataset.mediaRestore, target.dataset.mediaId || target.dataset.mediaRestoreId || "");
      return;
    }
    if (target.dataset.mediaDelete) {
      deleteMediaItem(target.dataset.mediaDelete, target.dataset.mediaId || "");
      return;
    }
    if (target.dataset.mediaOpenOriginal !== undefined) {
      openMediaOriginal();
      return;
    }
    if (target.dataset.mediaToggleFloat !== undefined) {
      toggleMediaFloat();
      return;
    }
    if (target.dataset.mediaMode) {
      state.mediaMode = target.dataset.mediaMode;
      state.activeMediaFolderId = "";
      clearExpandedMediaFolders();
      renderMedia();
      return;
    }
    if (target.dataset.mediaFolderCollapse) {
      if (Date.now() < state.mediaSuppressClickUntil) return;
      captureMediaFloatPositions();
      collapseExpandedMediaFolder(target.dataset.mediaFolderCollapse);
      renderMedia();
      return;
    }
    if (target.dataset.mediaFolderExpand) {
      if (Date.now() < state.mediaSuppressClickUntil) return;
      captureMediaFloatPositions();
      toggleExpandedMediaFolder(target.dataset.mediaFolderExpand);
      renderMedia();
      return;
    }
    if (target.dataset.mediaFolderOpen) {
      if (Date.now() < state.mediaSuppressClickUntil) return;
      if (state.mediaFloating && !isMediaFolderExpanded(target.dataset.mediaFolderOpen)) {
        captureMediaFloatPositions();
        expandMediaFolder(target.dataset.mediaFolderOpen);
        renderMedia();
        return;
      }
      openMediaFolder(target.dataset.mediaFolderOpen);
      return;
    }
    if (target.dataset.mediaFolderClose !== undefined) {
      closeMediaFolder();
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
    if (target.dataset.notebookAdd !== undefined) {
      addNotebookDraft();
      return;
    }
    if (target.dataset.notebookDelete) {
      deleteNotebookRow(target.dataset.notebookDelete);
      return;
    }
    if (target.dataset.t2iOpen !== undefined) {
      openT2iTemplateDialog();
      return;
    }
    if (target.dataset.t2iClose !== undefined) {
      closeT2iTemplateDialog();
      return;
    }
    if (target.dataset.t2iSelect) {
      selectT2iTemplate(target.dataset.t2iSelect);
      return;
    }
    if (target.dataset.t2iCustomToggle !== undefined) {
      state.t2iCustomOpen = !state.t2iCustomOpen;
      renderGlobalDialogs();
      return;
    }
    if (target.dataset.t2iCustomSave !== undefined) {
      saveCustomT2iTemplate();
      return;
    }
    if (target.dataset.settingsBack !== undefined) {
      closeModuleSettings();
    }
  },
  true
);

document.addEventListener("change", (event) => {
  const moduleTarget = event.target.closest("[data-module-toggle]");
  if (moduleTarget) {
    saveModuleToggle(moduleTarget);
    return;
  }
  const exportTarget = event.target.closest('input[name="package_type"]');
  if (exportTarget) {
    syncExportChoices(exportTarget);
  }
});

document.addEventListener("submit", (event) => {
  const form = event.target.closest('[data-action="create-media-folder"], [data-action="save-media-note"]');
  if (!form) return;
  if (form.dataset.action === "create-media-folder") createMediaFolder(event);
  if (form.dataset.action === "save-media-note") saveMediaNote(event);
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

function notebookOptions() {
  const items = state.notebooks?.length ? state.notebooks : state.bootstrap?.notebooks || [];
  return items.map((item) => ({ ...item, id: item.id || item.notebook_id || "default", name: item.name || item.id || "默认日记本" }));
}

function notebookLabel(notebookId = "") {
  const id = notebookId || "default";
  return notebookOptions().find((item) => item.id === id)?.name || (id === "default" ? "默认日记本" : id);
}

function findDiaryEntry(date, notebookId = "") {
  return state.diary.items.find((entry) => entry.date === date && (!notebookId || (entry.notebook_id || "default") === notebookId));
}

function entryRow(entry) {
  const notebookId = entry.notebook_id || "default";
  const active = state.diary.selected?.date === entry.date && (state.diary.selected?.notebook_id || "default") === notebookId;
  return `
    <button class="row ${active ? "active" : ""}" data-date="${escapeHtml(entry.date)}" data-notebook-id="${escapeHtml(notebookId)}" type="button">
      <span>${escapeHtml(entry.date)} · ${escapeHtml(notebookLabel(notebookId))}</span>
      <strong>${escapeHtml(entry.title || entry.date)}</strong>
    </button>
  `;
}

async function ensureDiaryList(force = false) {
  if (state.diary.loaded && !force) return;
  const notebookId = state.diary.filters.notebook_id || "";
  const payload = await api(`/api/ui/diary${notebookId ? `?notebook_id=${encodeURIComponent(notebookId)}` : ""}`);
  state.diary.items = payload.items;
  state.diary.archive = payload.archive;
  state.notebooks = payload.notebooks || state.notebooks || [];
  state.diary.loaded = true;
}

async function loadDiaryEntry(date, notebookId = "") {
  await ensureDiaryList();
  const visibleItems = filteredDiaryItems();
  const candidateDate = date || state.diary.selected?.date || state.selectedDate;
  const candidateNotebook = notebookId || state.diary.selected?.notebook_id || state.diary.filters.notebook_id || "";
  const selectedEntry = candidateDate
    ? visibleItems.find((entry) => entry.date === candidateDate && (!candidateNotebook || (entry.notebook_id || "default") === candidateNotebook))
    : visibleItems[0];
  const selectedDate = selectedEntry?.date || "";
  const selectedNotebook = selectedEntry?.notebook_id || candidateNotebook || "default";
  state.selectedDate = selectedDate || "";
  state.diary.selected = selectedDate ? await api(`/api/ui/diary/${encodeURIComponent(selectedDate)}?notebook_id=${encodeURIComponent(selectedNotebook)}`) : null;
}

function filteredDiaryItems() {
  const filters = state.diary.filters;
  return state.diary.items.filter((entry) => {
    if (filters.notebook_id && (entry.notebook_id || "default") !== filters.notebook_id) return false;
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
  return filters.date || filters.month || filters.year || filters.notebook_id || "";
}

function clearDiaryFilters() {
  state.diary.filters = { notebook_id: "", year: "", month: "", date: "" };
}

async function renderDiary() {
  await ensureDiaryList();
  if (state.diary.composerOpen) {
    const composeDate = state.diary.composerDate || state.editingDate || new Date().toISOString().slice(0, 10);
    const existing = findDiaryEntry(composeDate, state.diary.filters.notebook_id || "default");
    if (existing && !state.editingDate) {
      state.editingDate = composeDate;
      state.notice = state.notice || "这天已有日记，已切换为编辑。";
    }
    if (state.editingDate) {
      await loadDiaryEntry(state.editingDate, existing?.notebook_id || state.diary.filters.notebook_id || "default");
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

async function selectDiary(date, notebookId = "") {
  if (state.view !== "diary") {
    clearDiaryFilters();
    await setView("diary", { date, notebook_id: notebookId });
    return;
  }
  state.error = "";
  state.notice = "";
  const article = document.getElementById("diary-article");
  const previousScroll = article ? article.scrollTop : 0;
  await loadDiaryEntry(date, notebookId);
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
  const notebooks = notebookOptions();
  const years = [...new Set(dates.map((date) => date.slice(0, 4)))];
  const months = [...new Set(dates.filter((date) => !filters.year || date.startsWith(filters.year)).map((date) => date.slice(0, 7)))];
  const dateOptions = dates.filter((date) => {
    if (filters.month) return date.startsWith(filters.month);
    if (filters.year) return date.startsWith(filters.year);
    return true;
  });
  const notebookSelect = notebooks.map((item) => `<option value="${escapeHtml(item.id)}" ${filters.notebook_id === item.id ? "selected" : ""}>${escapeHtml(item.name)}</option>`).join("");
  const yearSelect = years.map((year) => `<option value="${year}" ${filters.year === year ? "selected" : ""}>${year}</option>`).join("");
  const monthSelect = months.map((month) => `<option value="${month}" ${filters.month === month ? "selected" : ""}>${month}</option>`).join("");
  const dateSelect = dateOptions.map((date) => `<option value="${date}" ${filters.date === date ? "selected" : ""}>${date}</option>`).join("");
  target.innerHTML = `
    <div class="archive-picker">
      <label class="archive-field archive-book-field"><span>日记本 / 群组</span><select data-filter-level="notebook"><option value="">全部日记本</option>${notebookSelect}</select></label>
      <div class="archive-date-strip">
        <label class="archive-field"><span>年</span><select data-filter-level="year"><option value="">全部</option>${yearSelect}</select></label>
        <label class="archive-field"><span>月</span><select data-filter-level="month"><option value="">全部</option>${monthSelect}</select></label>
        <label class="archive-field"><span>日期</span><select data-filter-level="date"><option value="">全部</option>${dateSelect}</select></label>
      </div>
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
  if (level === "notebook") {
    filters.notebook_id = value;
    filters.date = "";
    state.diary.loaded = false;
  }
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
  await ensureDiaryList(true);
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
        <div><p class="eyebrow">${escapeHtml(selected.date)} · ${escapeHtml(notebookLabel(selected.notebook_id))}</p><h2>${escapeHtml(selected.title)}</h2></div>
        <div class="actions"><button class="button" data-edit-date="${escapeHtml(selected.date)}" data-notebook-id="${escapeHtml(selected.notebook_id || "default")}" type="button">编辑</button><button class="danger" data-delete="${escapeHtml(selected.date)}" data-notebook-id="${escapeHtml(selected.notebook_id || "default")}">删除</button></div>
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

async function openDiaryComposer(date = "", notebookId = "") {
  await ensureDiaryList();
  const targetDate = date || new Date().toISOString().slice(0, 10);
  const targetNotebook = notebookId || state.diary.selected?.notebook_id || state.diary.filters.notebook_id || "default";
  const existing = findDiaryEntry(targetDate, targetNotebook);
  state.view = "diary";
  state.diary.composerOpen = true;
  state.diary.composerDate = targetDate;
  state.diary.filters.notebook_id = targetNotebook;
  state.editingDate = existing ? targetDate : date || "";
  if (existing) {
    state.diary.filters = { notebook_id: targetNotebook, year: targetDate.slice(0, 4), month: targetDate.slice(0, 7), date: targetDate };
    await loadDiaryEntry(targetDate, targetNotebook);
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
  const selectedNotebook = state.diary.selected?.notebook_id || state.diary.filters.notebook_id || "default";
  const selected = state.editingDate && state.diary.selected?.date === state.editingDate && (state.diary.selected?.notebook_id || "default") === selectedNotebook ? state.diary.selected : null;
  const notebookSelect = notebookOptions().map((item) => `<option value="${escapeHtml(item.id)}" ${(selected?.notebook_id || selectedNotebook) === item.id ? "selected" : ""}>${escapeHtml(item.name)}</option>`).join("");
  target.innerHTML = `
    <div class="card-head compact-head">
      <div><h2>${selected ? "编辑日记" : "写一篇"}</h2></div>
      <button class="text-button" data-close-write type="button">收起</button>
    </div>
    <form class="card-body form diary-compose-form" data-action="write-diary">
      <div class="form-grid compact">
        <label>日记本/群组<select name="notebook_id">${notebookSelect}</select></label>
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
  target.querySelector('select[name="notebook_id"]')?.addEventListener("change", handleDiaryComposeDateChange);
}

async function handleDiaryComposeDateChange(event) {
  const form = event.currentTarget.closest("form");
  const data = new FormData(form);
  const nextDate = data.get("date");
  const nextNotebook = data.get("notebook_id") || "default";
  state.diary.composerDate = nextDate;
  state.diary.filters.notebook_id = nextNotebook;
  const existing = findDiaryEntry(nextDate, nextNotebook);
  if (existing) {
    state.diary.filters = { notebook_id: nextNotebook, year: nextDate.slice(0, 4), month: nextDate.slice(0, 7), date: nextDate };
    state.editingDate = nextDate;
    await loadDiaryEntry(nextDate, nextNotebook);
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
    const notebookId = event.currentTarget.dataset.notebookId || state.diary.selected?.notebook_id || "default";
    if (!confirm(`删除 ${date} 的日记？`)) return;
    await api(`/api/ui/diary/${encodeURIComponent(date)}?notebook_id=${encodeURIComponent(notebookId)}`, { method: "DELETE" });
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
    notebook_id: form.get("notebook_id") || state.diary.filters.notebook_id || "default",
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
  state.diary.filters = { notebook_id: result.entry.notebook_id || payload.notebook_id || "default", year: result.entry.date.slice(0, 4), month: result.entry.date.slice(0, 7), date: result.entry.date };
  state.editingDate = "";
  state.notice = "日记已保存。";
  await setView("diary", { date: result.entry.date, notebook_id: result.entry.notebook_id || payload.notebook_id || "default", keepNotice: true });
}

async function loadSearch(query = "") {
  state.search.query = query || "";
  if (!state.search.query) {
    state.search.results = [];
    return;
  }
  const notebookId = state.search.notebook_id || "";
  const payload = await api(`/api/ui/search?q=${encodeURIComponent(state.search.query)}&top_k=8&notebook_id=${encodeURIComponent(notebookId)}`);
  state.search.results = payload.results;
  state.search.backend = payload.search.backend;
  state.notebooks = payload.notebooks || state.notebooks || [];
}

async function renderSearch() {
  await loadSearch(state.search.query);
  const scopeOptions = notebookOptions().map((item) => `<option value="${escapeHtml(item.id)}" ${state.search.notebook_id === item.id ? "selected" : ""}>${escapeHtml(item.name)}</option>`).join("");
  panel("search").innerHTML = `
    ${pageHead("", "搜索")}
    <section class="card">
      <div class="card-body">
        <form class="searchbar" data-action="search">
          <label class="search-scope">范围<select name="notebook_id"><option value="">全部日记本</option>${scopeOptions}</select></label>
          <input name="q" value="${escapeHtml(state.search.query)}" placeholder="关键词、人物、事件或情绪" />
          <button class="primary">搜索</button>
        </form>
      </div>
      <div class="list">
        ${
          state.search.results.length
            ? state.search.results.map((item) => `<button class="row" data-date="${escapeHtml(item.date)}" data-notebook-id="${escapeHtml(item.notebook_id || "default")}" type="button"><span>${escapeHtml(item.date)} · ${escapeHtml(item.notebook_name || notebookLabel(item.notebook_id))}</span><strong>${escapeHtml(item.title)}</strong><em>${escapeHtml(item.snippet || "")}</em></button>`).join("")
            : `<div class="card-body muted">暂无结果。</div>`
        }
      </div>
    </section>
  `;
  panel("search").querySelector('[data-action="search"]').addEventListener("submit", (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const q = form.get("q");
    state.search.notebook_id = form.get("notebook_id") || "";
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
  state.mediaOrganization = payload.organization || { folders: [], asset_locations: {}, trash: [] };
  const folders = visibleMediaFolders();
  const visibleFolderIds = new Set(folders.map((folder) => folder.id));
  state.expandedMediaFolderIds = (state.expandedMediaFolderIds || []).filter((id) => visibleFolderIds.has(id));
  const currentFolder = activeMediaFolder();
  if (state.mediaMode === "folder" && !currentFolder) {
    state.mediaMode = "main";
    state.activeMediaFolderId = "";
  }
  const assets = currentMediaAssets();
  const trashed = trashedMediaItems();
  const itemCount = state.mediaMode === "trash" ? trashed.length : assets.length + (state.mediaMode === "main" ? folders.length : 0);
  panel("media").innerHTML = `
    ${mediaHead(assets, folders, trashed)}
    ${state.mediaMode === "folder" ? mediaFolderHeader(currentFolder) : ""}
    <section class="media-workspace ${state.mediaFloating ? "floating" : ""} ${state.mediaMode === "folder" ? "folder-mode" : ""} ${state.mediaMode === "trash" ? "trash-mode" : ""}" data-media-workspace>
      <div class="media-gallery ${state.mediaFloating ? "floating" : ""}" data-media-gallery style="${state.mediaFloating ? `min-height:${mediaFloatHeight(itemCount)}px` : ""}">
        ${state.mediaMode === "trash" ? trashed.map(mediaTrashCard).join("") : ""}
        ${state.mediaMode === "main" ? folders.map(mediaFolderCard).join("") : ""}
        ${state.mediaMode !== "trash" ? assets.map(mediaCard).join("") : ""}
        ${mediaEmptyState(assets, folders)}
      </div>
    </section>
  `;
  renderGlobalDialogs();
  bindMediaInteractions();
  if (state.mediaFloating) startMediaFloat();
  else stopMediaFloat();
  if (state.mediaFloatPreferred && state.mediaFloatResumePending && !state.mediaFloating) {
    state.mediaFloatResumePending = false;
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        if (state.view !== "media" || !state.mediaFloatPreferred || state.mediaFloating) return;
        state.mediaFloatPositions = {};
        state.mediaFloating = true;
        renderMedia();
      });
    });
  }
}

async function toggleMediaFloat() {
  if (state.mediaFloating) {
    state.mediaFloatPreferred = false;
    state.mediaFloatResumePending = false;
    await animateFloatToGrid();
    state.mediaFloating = false;
  } else {
    state.mediaFloatPreferred = true;
    state.mediaFloatResumePending = false;
    state.mediaFloatPositions = {};
    state.mediaFloating = true;
  }
  renderMedia();
}

function allMediaAssets() {
  return state.media.flatMap((manifest) =>
    (manifest.assets || []).map((asset) => ({ ...asset, date: asset.date || manifest.date }))
  );
}

function visibleMediaAssets() {
  return allMediaAssets().filter((asset) => !asset.trashed);
}

function rootMediaAssets() {
  return visibleMediaAssets().filter((asset) => !asset.folder_id);
}

function folderMediaAssets(folderId) {
  return visibleMediaAssets().filter((asset) => asset.folder_id === folderId);
}

function currentMediaAssets() {
  if (state.mediaMode === "folder") return folderMediaAssets(state.activeMediaFolderId);
  if (state.mediaMode === "trash") return [];
  return rootMediaAssets();
}

function visibleMediaFolders() {
  return (state.mediaOrganization.folders || []).filter((folder) => !folder.trashed);
}

function activeMediaFolder() {
  return visibleMediaFolders().find((folder) => folder.id === state.activeMediaFolderId) || null;
}

function mediaPageTitle() {
  if (state.mediaMode === "trash") return "回收站";
  if (state.mediaMode === "folder") return activeMediaFolder()?.name || "文件夹";
  return "媒体";
}

function trashedMediaItems() {
  const trash = state.mediaOrganization.trash || [];
  const assets = allMediaAssets();
  const folders = state.mediaOrganization.folders || [];
  return trash.map((item) => {
    if (item.type === "asset") {
      const asset = assets.find((candidate) => candidate.sha256 === item.id);
      return asset ? { ...item, name: asset.original_name || asset.sha256 } : { ...item, name: item.id };
    }
    const folder = folders.find((candidate) => candidate.id === item.id);
    return { ...item, name: folder?.name || item.id };
  });
}

function mediaHead(assets, folders, trashed) {
  return `
    <header class="topbar media-topbar">
      <div class="page-title media-title">
        <h1>${escapeHtml(mediaPageTitle())}</h1>
        <span class="media-storage-inline">${escapeHtml(state.mediaStorage.label || formatBytes(state.mediaStorage.bytes || 0))} · 回收站 ${trashed.length}</span>
      </div>
      <div class="actions">${mediaToolbar(assets, folders, trashed)}</div>
    </header>
  `;
}

function mediaToolbar(assets, folders, trashed) {
  return `
    <div class="media-toolbar">
      <button class="media-float-toggle ${state.mediaFloating ? "active" : ""}" data-media-toggle-float type="button">
        ${iconImg("appearance", "漂浮模式")}<span>${state.mediaFloating ? "关闭漂浮" : "漂浮模式"}</span>
      </button>
      <div class="media-organize-tools">
        ${state.mediaMode === "main" ? `<button class="button ghost media-folder-create-button" data-media-folder-create type="button"><span class="folder-create-glyph" aria-hidden="true"><span></span></span><span>新建文件夹</span></button>` : `<button class="button ghost media-folder-create-button" data-media-mode="main" type="button">返回媒体</button>`}
        <button class="media-trash-drop ${state.mediaMode === "trash" ? "active" : ""}" data-media-trash-zone data-media-mode="trash" type="button" title="拖到这里回收">
          <span class="trash-symbol" aria-hidden="true"></span>
          <span>回收站 ${trashed.length}</span>
        </button>
      </div>
    </div>
  `;
}

function mediaStorageSubtitle(assets, folders, trashed) {
  if (state.mediaMode === "trash") return `${trashed.length} 个回收项目`;
  if (state.mediaMode === "folder") return `${assets.length} 个文件`;
  return `${assets.length} 个未归类文件 · ${folders.length} 个文件夹`;
}

function mediaCard(asset) {
  const id = asset.sha256 || asset.url || asset.path || asset.original_name;
  const name = asset.original_name || asset.sha256 || "未命名媒体";
  return `
    <article class="media-card" draggable="true" data-media-item="asset" data-media-id="${escapeHtml(asset.sha256)}" data-media-open="${escapeHtml(id)}">
      <span class="media-thumb ${asset.is_image ? "" : "file-thumb"}">
        ${asset.is_image ? `<img src="${escapeHtml(asset.url)}" alt="${escapeHtml(name)}" loading="lazy" draggable="false">` : iconImg("media", name)}
      </span>
      <span class="media-card-info">
        <strong>${escapeHtml(name)}</strong>
        <em>${escapeHtml(asset.folder_id && state.mediaMode !== "folder" ? folderName(asset.folder_id) : asset.date || "未归入文件夹")} · ${escapeHtml(formatBytes(asset.size_bytes || 0))}</em>
      </span>
    </article>
  `;
}

function mediaFolderCard(folder) {
  const count = visibleMediaAssets().filter((asset) => asset.folder_id === folder.id).length;
  const expanded = isMediaFolderExpanded(folder.id);
  const tags = Array.isArray(folder.tags) ? folder.tags.filter(Boolean) : [];
  return `
    <article class="media-card folder-card ${expanded ? "expanded" : ""}" draggable="true" data-media-item="folder" data-media-id="${escapeHtml(folder.id)}" data-media-folder-drop="${escapeHtml(folder.id)}" data-media-folder-expand="${escapeHtml(folder.id)}">
      <button class="media-thumb folder-thumb" data-media-folder-open="${escapeHtml(folder.id)}" type="button">
        ${iconImg("modules", folder.name)}
        <span class="folder-mouth">${expanded ? "打开文件夹，把图片拖到这里" : count ? "打开" : "空"}</span>
      </button>
      <span class="media-card-info">
        <strong>${escapeHtml(folder.name)}</strong>
        <em>${escapeHtml(folder.note || `${count} 个文件`)}</em>
      </span>
      ${tags.length ? `<span class="folder-tags">${tags.map((tag) => `<b>${escapeHtml(tag)}</b>`).join("")}</span>` : ""}
      ${expanded ? `<button class="folder-drop-mouth folder-collapse-button" data-media-folder-collapse="${escapeHtml(folder.id)}" type="button">取消</button>` : ""}
    </article>
  `;
}

function mediaTrashCard(item) {
  return `
    <article class="media-card trash-card" draggable="true" data-media-item="${escapeHtml(item.type)}" data-media-id="${escapeHtml(item.id)}">
      <span class="media-thumb file-thumb">${item.type === "folder" ? iconImg("modules", item.name || "文件夹") : iconImg("media", item.name || "图片")}</span>
      <span class="media-card-info">
        <strong>${escapeHtml(item.name || item.id)}</strong>
        <em>${escapeHtml(item.type === "folder" ? "文件夹" : "图片")} · 已回收</em>
      </span>
      <div class="trash-card-actions">
        <button class="button ghost" data-media-restore="${escapeHtml(item.type)}" data-media-id="${escapeHtml(item.id)}" type="button">恢复</button>
        <button class="button danger" data-media-delete="${escapeHtml(item.type)}" data-media-id="${escapeHtml(item.id)}" type="button">彻底删除</button>
      </div>
    </article>
  `;
}

function mediaFolderHeader(folder) {
  if (!folder) return "";
  return `
    <section class="media-folder-shell" data-folder-shell>
      <button class="button ghost" data-media-folder-close type="button">返回媒体</button>
      <div>
        <h2>${escapeHtml(folder.name)}</h2>
        <p class="muted">把图片拖出这个区域即可移出文件夹。</p>
      </div>
      <button class="button ghost folder-header-edit" data-media-folder-edit="${escapeHtml(folder.id)}" type="button">编辑文件夹</button>
    </section>
  `;
}

function mediaEmptyState(assets, folders) {
  if (state.mediaMode === "trash") {
    return trashedMediaItems().length ? "" : `<article class="card"><div class="card-body muted">回收站是空的。</div></article>`;
  }
  if (state.mediaMode === "folder") {
    return assets.length ? "" : `<article class="card"><div class="card-body muted">这个文件夹还没有图片。</div></article>`;
  }
  return !folders.length && !assets.length ? `<article class="card"><div class="card-body muted">还没有媒体归档。</div></article>` : "";
}

function mediaFloatHeight(count) {
  const rows = Math.max(2, Math.ceil(Math.max(1, count) / 3));
  return Math.max(window.innerHeight * 1.35, rows * 240 + 260);
}

function openMediaDetail(id) {
  state.selectedMedia = allMediaAssets().find((asset) => [asset.sha256, asset.url, asset.path, asset.original_name].includes(id)) || null;
  state.mediaNoteEditing = false;
  renderGlobalDialogs();
}

function closeMediaDetail() {
  state.selectedMedia = null;
  state.mediaNoteEditing = false;
  renderGlobalDialogs();
}

function renderGlobalDialogs() {
  const root = document.getElementById("global-dialog-root");
  if (!root) return;
  root.innerHTML = `
    ${state.selectedMedia ? mediaDialog(state.selectedMedia) : ""}
    ${state.mediaFolderModalOpen ? mediaFolderCreateDialog() : ""}
    ${state.t2iTemplateDialogOpen ? t2iTemplateDialog() : ""}
  `;
}

function t2iTemplateDialog() {
  const form = document.querySelector('[data-action="save-settings"]');
  const currentName = form?.querySelector('[name="diary_t2i_template_name"]')?.value || state.settings?.settings?.diary_t2i_template_name || "plain_note";
  const customValue = form?.querySelector('[name="diary_t2i_template"]')?.value || state.settings?.settings?.diary_t2i_template || "";
  const customSettings = { diary_t2i_template_name: currentName, diary_t2i_template: customValue };
  const customTemplates = customT2iTemplates(customSettings);
  const customCurrent = customTemplates.find((item) => item.id === currentName);
  const current = customCurrent || (currentName === "custom" && customValue && !customValue.startsWith("{") ? { id: "custom", template: customValue } : t2iTemplateById(currentName));
  const cards = [...DIARY_T2I_TEMPLATES, ...customTemplates];
  return `
    <div class="media-dialog-backdrop soft" data-t2i-close>
      <article class="nest-dialog t2i-dialog" role="dialog" aria-modal="true" aria-label="图片推送模板" onclick="event.stopPropagation()">
        <button class="media-dialog-close" data-t2i-close type="button" aria-label="关闭">×</button>
        <div class="settings-mini-head t2i-head"><strong>图片推送模板</strong><span>选择后会保存到日记模块设置</span></div>
        <div class="t2i-template-grid">
          ${cards.map((item) => `
            <button class="t2i-template-card ${currentName === item.id ? "active" : ""}" data-t2i-select="${escapeHtml(item.id)}" type="button">
              <span class="t2i-preview">${t2iPreviewHtml(item.template)}</span>
              <strong>${escapeHtml(item.name)}</strong>
              <em>${escapeHtml(item.tone)}</em>
            </button>
          `).join("")}
        </div>
        <button class="button ghost" data-t2i-custom-toggle type="button">${state.t2iCustomOpen ? "收起新增模板" : "新增自定义模板"}</button>
        <div class="t2i-custom ${state.t2iCustomOpen ? "open" : ""}">
          <div class="form-grid compact">
            <label>模板名称<input data-t2i-custom-name placeholder="例如：群聊日报"></label>
            <label>模板风格<input data-t2i-custom-tone placeholder="例如：轻量、适合长文"></label>
          </div>
          <label>模板内容<textarea data-t2i-custom-value rows="7" placeholder="粘贴 HTML 模板，支持 {{ date }}、{{ notebook_name }}、{{ title }}、{{ body }}"></textarea></label>
          <button class="primary" data-t2i-custom-save type="button">保存并使用这个模板</button>
        </div>
        <div class="t2i-current-preview">
          <strong>当前预览</strong>
          <div>${t2iPreviewHtml(current.template)}</div>
        </div>
      </article>
    </div>
  `;
}

function openT2iTemplateDialog() {
  state.t2iTemplateDialogOpen = true;
  renderGlobalDialogs();
}

function closeT2iTemplateDialog() {
  state.t2iTemplateDialogOpen = false;
  state.t2iCustomOpen = false;
  renderGlobalDialogs();
}

function selectT2iTemplate(id) {
  const form = document.querySelector('[data-action="save-settings"]');
  if (!form) return;
  const nameInput = form.querySelector('[name="diary_t2i_template_name"]');
  const templateInput = form.querySelector('[name="diary_t2i_template"]');
  if (!nameInput || !templateInput) return;
  const customTemplates = customT2iTemplates({ diary_t2i_template_name: nameInput.value, diary_t2i_template: templateInput.value });
  const customItem = customTemplates.find((item) => item.id === id);
  if (customItem) {
    nameInput.value = customItem.id;
    templateInput.value = t2iTemplateStore(customTemplates);
  } else {
    const item = t2iTemplateById(id);
    nameInput.value = item.id;
    templateInput.value = templateInput.value.startsWith("{") ? templateInput.value : "";
  }
  state.toast = "图片模板已选择，记得保存设置";
  closeT2iTemplateDialog();
  updateShell();
  clearToastSoon();
}

function saveCustomT2iTemplate() {
  const form = document.querySelector('[data-action="save-settings"]');
  const nameInput = form?.querySelector('[name="diary_t2i_template_name"]');
  const templateInput = form?.querySelector('[name="diary_t2i_template"]');
  if (!nameInput || !templateInput) return;
  const template = document.querySelector("[data-t2i-custom-value]")?.value.trim() || "";
  if (!template) {
    state.toast = "先填写模板内容";
    updateShell();
    clearToastSoon();
    return;
  }
  const templates = customT2iTemplates({ diary_t2i_template_name: nameInput.value, diary_t2i_template: templateInput.value });
  const id = `custom_${Date.now()}`;
  const item = {
    id,
    name: document.querySelector("[data-t2i-custom-name]")?.value.trim() || "自定义模板",
    tone: document.querySelector("[data-t2i-custom-tone]")?.value.trim() || "自定义",
    template,
  };
  templates.push(item);
  nameInput.value = id;
  templateInput.value = t2iTemplateStore(templates);
  state.toast = "自定义模板已保存，记得保存设置";
  closeT2iTemplateDialog();
  updateShell();
  clearToastSoon();
}

function mediaDialog(asset) {
  const wide = Number(asset.width || 0) >= Number(asset.height || 0);
  const layout = wide ? "landscape" : "portrait";
  const name = asset.original_name || asset.sha256 || "未命名媒体";
  const savedAt = formatDateTime(asset.saved_at) || asset.date || "";
  const note = asset.note || "";
  const noteEditing = Boolean(state.mediaNoteEditing);
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
          </dl>
          <form class="media-note-form ${noteEditing ? "editing" : ""}" data-action="save-media-note">
            <input type="hidden" name="sha256" value="${escapeHtml(asset.sha256 || "")}">
            <label>备注<textarea name="note" rows="3" placeholder="给这张图片补充备注" ${noteEditing ? "" : "readonly"}>${escapeHtml(note)}</textarea></label>
            <div class="actions dialog-actions">
              <button class="button ghost" data-media-open-original type="button">打开原图</button>
              ${noteEditing ? `<button class="primary" type="submit">保存备注</button>` : `<button class="primary" data-media-note-edit type="button">修改备注</button>`}
            </div>
          </form>
        </div>
      </article>
    </div>
  `;
}

function folderName(folderId) {
  return (state.mediaOrganization.folders || []).find((folder) => folder.id === folderId)?.name || "文件夹";
}

function expandedMediaFolderSet() {
  return new Set((state.expandedMediaFolderIds || []).filter(Boolean));
}

function isMediaFolderExpanded(folderId) {
  return expandedMediaFolderSet().has(folderId);
}

function expandMediaFolder(folderId) {
  if (!folderId) return;
  const folders = expandedMediaFolderSet();
  folders.add(folderId);
  state.expandedMediaFolderIds = Array.from(folders);
}

function collapseExpandedMediaFolder(folderId) {
  const folders = expandedMediaFolderSet();
  folders.delete(folderId);
  state.expandedMediaFolderIds = Array.from(folders);
}

function toggleExpandedMediaFolder(folderId) {
  if (isMediaFolderExpanded(folderId)) collapseExpandedMediaFolder(folderId);
  else expandMediaFolder(folderId);
}

function clearExpandedMediaFolders() {
  state.expandedMediaFolderIds = [];
}

function openMediaFolder(folderId) {
  state.mediaMode = "folder";
  state.activeMediaFolderId = folderId;
  clearExpandedMediaFolders();
  renderMedia();
}

function closeMediaFolder() {
  state.mediaMode = "main";
  state.activeMediaFolderId = "";
  clearExpandedMediaFolders();
  renderMedia();
}

function openMediaFolderModal(folderId = "") {
  state.mediaFolderEditingId = folderId || "";
  state.mediaFolderModalOpen = true;
  renderGlobalDialogs();
}

function closeMediaFolderModal() {
  state.mediaFolderModalOpen = false;
  state.mediaFolderEditingId = "";
  renderGlobalDialogs();
}

function mediaFolderCreateDialog() {
  const folder = state.mediaFolderEditingId
    ? (state.mediaOrganization.folders || []).find((item) => item.id === state.mediaFolderEditingId)
    : null;
  const tags = Array.isArray(folder?.tags) ? folder.tags.join("，") : "";
  const title = folder ? "编辑文件夹" : "新建文件夹";
  return `
    <div class="media-dialog-backdrop soft" data-media-folder-modal-close>
      <article class="nest-dialog folder-create-dialog" role="dialog" aria-modal="true" aria-label="${escapeHtml(title)}" onclick="event.stopPropagation()">
        <button class="media-dialog-close" data-media-folder-modal-close type="button" aria-label="关闭">×</button>
        <h2>${escapeHtml(title)}</h2>
        <form class="form" data-action="create-media-folder">
          <input type="hidden" name="folder_id" value="${escapeHtml(folder?.id || "")}">
          <label>文件夹名称<input name="name" value="${escapeHtml(folder?.name || "新建文件夹")}" maxlength="40" required></label>
          <label>标签<input name="tags" value="${escapeHtml(tags)}" placeholder="用逗号分开，例如：旅行，头像"></label>
          <label>备注 / 副标题<textarea name="note" rows="3" placeholder="给这个文件夹写一句说明">${escapeHtml(folder?.note || "")}</textarea></label>
          <div class="actions dialog-actions">
            <button class="button ghost" data-media-folder-modal-close type="button">取消</button>
            <button class="primary" type="submit">${folder ? "保存" : "创建"}</button>
          </div>
        </form>
      </article>
    </div>
  `;
}

async function createMediaFolder(event) {
  event.preventDefault();
  const formElement = event.target.closest('[data-action="create-media-folder"]');
  if (!formElement) return;
  const form = new FormData(formElement);
  const folderId = String(form.get("folder_id") || "");
  const payload = {
    name: form.get("name") || "新建文件夹",
    tags: splitWords(form.get("tags") || ""),
    note: form.get("note") || "",
  };
  try {
    if (folderId) {
      await api("/api/ui/media/folders/update", { method: "POST", body: JSON.stringify({ ...payload, folder_id: folderId }) });
    } else {
      await api("/api/ui/media/folders", { method: "POST", body: JSON.stringify(payload) });
    }
    state.mediaFolderModalOpen = false;
    state.mediaFolderEditingId = "";
    state.toast = folderId ? "文件夹已保存" : "文件夹已创建";
    await renderMedia();
    updateShell();
    clearToastSoon();
  } catch (err) {
    state.toast = `保存失败：${err.message}`;
    updateShell();
    clearToastSoon();
  }
}

async function saveMediaNote(event) {
  event.preventDefault();
  const formElement = event.target.closest('[data-action="save-media-note"]');
  if (!formElement) return;
  const form = new FormData(formElement);
  const sha256 = String(form.get("sha256") || "");
  const note = String(form.get("note") || "");
  try {
    const result = await api("/api/ui/media/note", { method: "POST", body: JSON.stringify({ sha256, note }) });
    const savedNote = result.asset.note ?? note;
    if (state.selectedMedia?.sha256 === sha256) state.selectedMedia = { ...state.selectedMedia, note: savedNote };
    state.media = state.media.map((manifest) => ({
      ...manifest,
      assets: (manifest.assets || []).map((asset) => asset.sha256 === sha256 ? { ...asset, note: savedNote } : asset),
    }));
    state.mediaNoteEditing = false;
    state.toast = "备注已保存";
    renderGlobalDialogs();
    updateShell();
    clearToastSoon();
  } catch (err) {
    state.toast = `保存失败：${err.message}`;
    updateShell();
    clearToastSoon();
  }
}

async function moveMediaToFolder(sha256, folderId) {
  await api("/api/ui/media/move", { method: "POST", body: JSON.stringify({ sha256, folder_id: folderId }) });
  state.toast = "已放入文件夹";
  await renderMedia();
  updateShell();
  clearToastSoon();
}

async function trashMediaItem(type, id, sourceNode = null) {
  if (!id) return;
  if (sourceNode) await animateTrashDrop(sourceNode);
  await api("/api/ui/media/trash", { method: "POST", body: JSON.stringify({ item_type: type, item_id: id }) });
  state.toast = "已放入回收站";
  if (state.mediaMode === "folder" && type === "folder") closeMediaFolder();
  await renderMedia();
  updateShell();
  clearToastSoon();
}

async function restoreMediaItem(type, id) {
  await api("/api/ui/media/restore", { method: "POST", body: JSON.stringify({ item_type: type, item_id: id }) });
  state.toast = "已恢复";
  await renderMedia();
  updateShell();
  clearToastSoon();
}

async function deleteMediaItem(type, id) {
  if (!id) return;
  const label = type === "folder" ? "这个文件夹和里面的图片" : "这张图片";
  if (!confirm(`彻底删除${label}？这个操作不能恢复。`)) return;
  await api("/api/ui/media/delete", { method: "POST", body: JSON.stringify({ item_type: type, item_id: id }) });
  state.toast = "已彻底删除";
  await renderMedia();
  updateShell();
  clearToastSoon();
}

function openMediaOriginal() {
  if (!state.selectedMedia?.url) return;
  window.open(state.selectedMedia.url, "_blank", "noopener,noreferrer");
}

function animateTrashDrop(sourceNode) {
  const trash = document.querySelector("[data-media-trash-zone]");
  if (!trash || !sourceNode) return Promise.resolve();
  const from = sourceNode.getBoundingClientRect();
  const to = trash.getBoundingClientRect();
  const clone = sourceNode.cloneNode(true);
  clone.classList.add("trash-fly-clone");
  clone.style.left = `${from.left}px`;
  clone.style.top = `${from.top}px`;
  clone.style.width = `${from.width}px`;
  clone.style.height = `${from.height}px`;
  document.body.appendChild(clone);
  const dx = to.left + to.width / 2 - (from.left + from.width / 2);
  const dy = to.top + to.height / 2 - (from.top + from.height / 2);
  return new Promise((resolve) => {
    clone.animate(
      [
        { transform: "translate(0, 0) scale(1)", opacity: 0.92 },
        { transform: `translate(${dx}px, ${dy}px) scale(0.12) rotate(12deg)`, opacity: 0.18 },
      ],
      { duration: 360, easing: "cubic-bezier(.2,.8,.2,1)" }
    ).addEventListener("finish", () => {
      clone.remove();
      resolve();
    });
  });
}

function clearToastSoon() {
  window.setTimeout(() => {
    state.toast = "";
    updateShell();
  }, 1800);
}

function bindMediaInteractions() {
  const workspace = panel("media");
  let dragPayload = null;
  workspace.querySelectorAll("[data-media-item]").forEach((node) => {
    node.draggable = !state.mediaFloating;
    node.querySelectorAll("img").forEach((img) => {
      img.draggable = false;
    });
    node.addEventListener("dragstart", (event) => {
      if (state.mediaFloating) {
        event.preventDefault();
        return;
      }
      dragPayload = { type: node.dataset.mediaItem, id: node.dataset.mediaId };
      event.dataTransfer.setData("application/json", JSON.stringify(dragPayload));
      event.dataTransfer.effectAllowed = "move";
      state.mediaSuppressClickUntil = Date.now() + 800;
      node.classList.add("dragging");
    });
    node.addEventListener("dragend", () => {
      state.mediaSuppressClickUntil = Date.now() + 450;
      node.classList.remove("dragging");
      clearMediaDropHighlights();
    });
  });
  workspace.querySelectorAll("[data-media-folder-drop]").forEach((folder) => {
    folder.addEventListener("dragover", (event) => {
      const payload = mediaDragPayload(event, dragPayload);
      if (payload?.type !== "asset" || !folder.classList.contains("expanded")) return;
      event.preventDefault();
      folder.classList.add("drop-ready");
    });
    folder.addEventListener("dragleave", () => folder.classList.remove("drop-ready"));
    folder.addEventListener("drop", async (event) => {
      const payload = mediaDragPayload(event, dragPayload);
      if (payload?.type !== "asset" || !folder.classList.contains("expanded")) return;
      event.preventDefault();
      event.stopPropagation();
      folder.classList.remove("drop-ready");
      await moveMediaToFolder(payload.id, folder.dataset.mediaFolderDrop);
    });
  });
  workspace.addEventListener("dragover", (event) => {
    const payload = mediaDragPayload(event, dragPayload);
    if (!payload) return;
    updateMediaDropHighlights({
      x: event.clientX,
      y: event.clientY,
      type: payload.type || "",
    });
    if (pointInsideTrashZone({ x: event.clientX, y: event.clientY })) event.preventDefault();
  });
  workspace.addEventListener("dragleave", (event) => {
    if (!event.relatedTarget || !workspace.contains(event.relatedTarget)) clearMediaDropHighlights();
  });
  workspace.addEventListener("drop", async (event) => {
    if (event.defaultPrevented) return;
    const payload = mediaDragPayload(event, dragPayload);
    if (!payload) return;
    const point = { x: event.clientX, y: event.clientY };
    if (!pointInsideTrashZone(point)) return;
    event.preventDefault();
    clearMediaDropHighlights();
    const sourceNode = workspace.querySelector(`[data-media-item="${CSS.escape(payload.type || "")}"][data-media-id="${CSS.escape(payload.id || "")}"]`);
    await trashMediaItem(payload.type, payload.id, sourceNode);
  });
  workspace.querySelector("[data-media-trash-zone]")?.addEventListener("dragover", (event) => {
    event.preventDefault();
    event.currentTarget.classList.add("drop-ready");
  });
  workspace.querySelector("[data-media-trash-zone]")?.addEventListener("dragleave", (event) => {
    event.currentTarget.classList.remove("drop-ready");
  });
  workspace.querySelector("[data-media-trash-zone]")?.addEventListener("drop", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.classList.remove("drop-ready");
    const payload = mediaDragPayload(event, dragPayload);
    const sourceNode = workspace.querySelector(`[data-media-item="${CSS.escape(payload?.type || "")}"][data-media-id="${CSS.escape(payload?.id || "")}"]`);
    if (payload) await trashMediaItem(payload.type, payload.id, sourceNode);
  });
  const mediaWorkspace = workspace.querySelector("[data-media-workspace]");
  mediaWorkspace?.addEventListener("dragover", (event) => {
    if (state.mediaMode !== "folder") return;
    event.preventDefault();
    maybeAutoLeaveFolder(event, dragPayload);
  });
  mediaWorkspace?.addEventListener("drop", async (event) => {
    if (state.mediaMode !== "folder") return;
    const shell = event.target.closest("[data-media-gallery]");
    const payload = mediaDragPayload(event, dragPayload);
    if (!payload || payload.type !== "asset") return;
    if (!shell || !shell.contains(event.target) || event.target === mediaWorkspace) {
      event.preventDefault();
      await moveMediaToFolder(payload.id, "");
      closeMediaFolder();
    }
  });
}

function mediaDragPayload(event, fallback) {
  try {
    return JSON.parse(event.dataTransfer.getData("application/json"));
  } catch (_) {
    return fallback;
  }
}

let mediaFolderLeaveTimer = 0;

function maybeAutoLeaveFolder(event, payload = null) {
  const gallery = document.querySelector("[data-media-gallery]");
  if (!gallery) return;
  const rect = gallery.getBoundingClientRect();
  const nearEdge =
    event.clientX < rect.left + 20 ||
    event.clientX > rect.right - 20 ||
    event.clientY < rect.top + 20 ||
    event.clientY > rect.bottom - 20;
  if (!nearEdge) {
    window.clearTimeout(mediaFolderLeaveTimer);
    mediaFolderLeaveTimer = 0;
    return;
  }
  if (mediaFolderLeaveTimer) return;
  mediaFolderLeaveTimer = window.setTimeout(async () => {
    if (state.mediaMode === "folder" && payload?.type === "asset") {
      await moveMediaToFolder(payload.id, "");
      closeMediaFolder();
    } else if (state.mediaMode === "folder") {
      closeMediaFolder();
    }
    mediaFolderLeaveTimer = 0;
  }, 650);
}

let mediaFloatFrame = 0;
let mediaFloatItems = [];
let mediaFloatDrag = null;
let mediaFloatRetry = 0;

function startMediaFloat() {
  stopMediaFloat();
  const gallery = document.querySelector("[data-media-gallery]");
  if (!gallery) return;
  const bounds = gallery.getBoundingClientRect();
  if (bounds.width < 80 || bounds.height < 80) {
    mediaFloatRetry = requestAnimationFrame(startMediaFloat);
    return;
  }
  mediaFloatItems = Array.from(gallery.querySelectorAll("[data-media-item]"))
    .filter((node) => !node.classList.contains("expanded"))
    .map((node, index) => {
    const rect = node.getBoundingClientRect();
    const key = mediaFloatKey(node);
    const saved = state.mediaFloatPositions[key] || null;
    const gridX = Math.max(0, rect.left - bounds.left);
    const gridY = Math.max(0, rect.top - bounds.top);
    const x = saved ? Number(saved.x || 0) : gridX;
    const y = saved ? Number(saved.y || 0) : gridY;
    const item = {
      node,
      key,
      x,
      y,
      vx: saved ? Number(saved.vx || 0.12) : (index % 2 ? 0.12 : -0.1),
      vy: saved ? Number(saved.vy || 0.1) : (index % 3 ? 0.09 : -0.08),
      w: rect.width || 210,
      h: rect.height || 180,
      locked: false,
    };
    item.x = Math.max(0, Math.min(item.x, Math.max(0, bounds.width - item.w)));
    item.y = Math.max(0, Math.min(item.y, Math.max(0, bounds.height - item.h)));
    node.dataset.floatReady = "true";
    node.style.transform = `translate(${item.x}px, ${item.y}px)`;
    node.addEventListener("pointerdown", startFloatDrag);
    return item;
  });
  gallery.querySelectorAll("[data-media-item].expanded").forEach((node) => {
    const key = mediaFloatKey(node);
    const saved = state.mediaFloatPositions[key] || null;
    const rect = node.getBoundingClientRect();
    const x = saved ? Number(saved.x || 0) : Math.max(0, rect.left - bounds.left);
    const y = saved ? Number(saved.y || 0) : Math.max(0, rect.top - bounds.top);
    node.dataset.floatReady = "locked";
    node.style.transform = `translate(${Math.max(0, Math.min(x, Math.max(0, bounds.width - rect.width)))}px, ${Math.max(0, y)}px)`;
  });
  mediaFloatFrame = requestAnimationFrame(tickMediaFloat);
}

function stopMediaFloat() {
  if (mediaFloatFrame) cancelAnimationFrame(mediaFloatFrame);
  if (mediaFloatRetry) cancelAnimationFrame(mediaFloatRetry);
  mediaFloatFrame = 0;
  mediaFloatRetry = 0;
  mediaFloatDrag = null;
  mediaFloatItems.forEach((item) => {
    item.node.removeEventListener("pointerdown", startFloatDrag);
    item.node.style.transform = "";
    item.node.dataset.floatReady = "false";
  });
  mediaFloatItems = [];
}

function tickMediaFloat() {
  const gallery = document.querySelector("[data-media-gallery]");
  if (!gallery) return;
  const bounds = gallery.getBoundingClientRect();
  if (bounds.width < 80 || bounds.height < 80) {
    mediaFloatFrame = requestAnimationFrame(tickMediaFloat);
    return;
  }
  for (const item of mediaFloatItems) {
    if (mediaFloatDrag?.item === item || item.locked) continue;
    item.x += item.vx;
    item.y += item.vy;
    item.vx *= 0.996;
    item.vy *= 0.996;
    if (Math.abs(item.vx) < 0.035) item.vx += item.vx >= 0 ? 0.008 : -0.008;
    if (Math.abs(item.vy) < 0.03) item.vy += item.vy >= 0 ? 0.007 : -0.007;
    if (item.x < 0 || item.x + item.w > bounds.width) {
      item.vx *= -0.88;
      item.x = Math.max(0, Math.min(item.x, bounds.width - item.w));
    }
    if (item.y < 0 || item.y + item.h > bounds.height) {
      item.vy *= -0.88;
      item.y = Math.max(0, Math.min(item.y, bounds.height - item.h));
    }
  }
  for (let i = 0; i < mediaFloatItems.length; i += 1) {
    for (let j = i + 1; j < mediaFloatItems.length; j += 1) {
      if (mediaFloatItems[i].locked || mediaFloatItems[j].locked) continue;
      collideFloatItems(mediaFloatItems[i], mediaFloatItems[j]);
    }
  }
  mediaFloatItems.forEach((item) => {
    item.node.dataset.floatX = String(item.x);
    item.node.dataset.floatY = String(item.y);
    state.mediaFloatPositions[item.key] = { x: item.x, y: item.y, vx: item.vx, vy: item.vy };
    item.node.style.transform = `translate(${item.x}px, ${item.y}px)`;
  });
  mediaFloatFrame = requestAnimationFrame(tickMediaFloat);
}

function mediaFloatKey(node) {
  return `${node.dataset.mediaItem || "item"}:${node.dataset.mediaId || ""}`;
}

function collideFloatItems(a, b) {
  const overlapX = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
  const overlapY = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
  if (overlapX <= 0 || overlapY <= 0) return;
  const pushX = overlapX / 2 + 0.5;
  const pushY = overlapY / 2 + 0.5;
  if (overlapX < overlapY) {
    const dir = a.x < b.x ? -1 : 1;
    a.x += dir * pushX;
    b.x -= dir * pushX;
    const av = a.vx;
    a.vx = b.vx * 0.9;
    b.vx = av * 0.9;
  } else {
    const dir = a.y < b.y ? -1 : 1;
    a.y += dir * pushY;
    b.y -= dir * pushY;
    const av = a.vy;
    a.vy = b.vy * 0.9;
    b.vy = av * 0.9;
  }
}

function startFloatDrag(event) {
  if (!state.mediaFloating) return;
  if (event.target.closest("a, input, textarea, select, [data-media-restore], [data-media-delete]")) return;
  const item = mediaFloatItems.find((candidate) => candidate.node === event.currentTarget);
  if (!item) return;
  event.preventDefault();
  event.currentTarget.setPointerCapture(event.pointerId);
  mediaFloatDrag = {
    item,
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    itemX: item.x,
    itemY: item.y,
    lastX: event.clientX,
    lastY: event.clientY,
    lastTime: performance.now(),
    moved: false,
  };
  item.vx = 0;
  item.vy = 0;
  event.currentTarget.classList.add("dragging");
  event.currentTarget.addEventListener("pointermove", moveFloatDrag);
  event.currentTarget.addEventListener("pointerup", endFloatDrag, { once: true });
  event.currentTarget.addEventListener("pointercancel", endFloatDrag, { once: true });
}

function moveFloatDrag(event) {
  if (!mediaFloatDrag) return;
  const drag = mediaFloatDrag;
  const now = performance.now();
  drag.item.x = drag.itemX + event.clientX - drag.startX;
  drag.item.y = drag.itemY + event.clientY - drag.startY;
  drag.item.vx = ((event.clientX - drag.lastX) / Math.max(16, now - drag.lastTime)) * 12;
  drag.item.vy = ((event.clientY - drag.lastY) / Math.max(16, now - drag.lastTime)) * 12;
  if (Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) > 6) {
    drag.moved = true;
    state.mediaSuppressClickUntil = Date.now() + 700;
  }
  if (state.mediaMode === "folder") {
    maybeAutoLeaveFolder(event, {
      type: drag.item.node.dataset.mediaItem || "",
      id: drag.item.node.dataset.mediaId || "",
    });
  }
  drag.overTrash = pointInsideAnyTrashZonePoint(
    { x: event.clientX, y: event.clientY },
    floatItemCenter(drag.item)
  ) || floatItemIntersectsTrashZone(drag.item);
  updateMediaDropHighlights({
    x: event.clientX,
    y: event.clientY,
    altX: floatItemCenter(drag.item)?.x,
    altY: floatItemCenter(drag.item)?.y,
    trashReady: drag.overTrash,
    type: drag.item.node.dataset.mediaItem || "",
  });
  drag.lastX = event.clientX;
  drag.lastY = event.clientY;
  drag.lastTime = now;
}

async function endFloatDrag(event) {
  event.currentTarget.removeEventListener("pointermove", moveFloatDrag);
  const drag = mediaFloatDrag;
  if (!drag?.item) {
    mediaFloatDrag = null;
    return;
  }
  event.currentTarget.classList.remove("dragging");
  try {
    event.currentTarget.releasePointerCapture(drag.pointerId);
  } catch (_) {}
  drag.item.vx = Math.max(-0.55, Math.min(0.55, drag.item.vx));
  drag.item.vy = Math.max(-0.48, Math.min(0.48, drag.item.vy));
  if (drag.moved) state.mediaSuppressClickUntil = Date.now() + 900;
  const node = drag.item.node;
  const type = node.dataset.mediaItem || "";
  const id = node.dataset.mediaId || "";
  const point = { x: event.clientX, y: event.clientY };
  mediaFloatDrag = null;
  if (!drag.moved) {
    state.mediaSuppressClickUntil = Date.now() + 450;
    if (type === "asset") openMediaDetail(id);
    if (type === "folder" && state.mediaFloating) {
      captureMediaFloatPositions();
      toggleExpandedMediaFolder(id);
      renderMedia();
    }
    return;
  }
  clearMediaDropHighlights();
  const itemCenter = floatItemCenter(drag.item);
  const lastPoint = { x: drag.lastX, y: drag.lastY };
  if (drag.overTrash || pointInsideAnyTrashZonePoint(point, lastPoint, itemCenter) || floatItemIntersectsTrashZone(drag.item)) {
    await trashMediaItem(type, id, node);
    return;
  }
  if (type === "asset") {
    const folderDrop = Array.from(document.querySelectorAll("[data-media-folder-drop].expanded")).find((folder) =>
      pointInsideElement(point, folder)
    );
    if (folderDrop?.dataset.mediaFolderDrop) {
      await moveMediaToFolder(id, folderDrop.dataset.mediaFolderDrop);
      return;
    }
    if (state.mediaMode === "folder") {
      const folderSpace = document.querySelector("[data-media-workspace]");
      if (folderSpace && !pointInsideElement(point, folderSpace)) {
        await moveMediaToFolder(id, "");
        closeMediaFolder();
      }
    }
  }
}

function pointInsideElement(point, element) {
  if (!element) return false;
  const rect = element.getBoundingClientRect();
  return point.x >= rect.left && point.x <= rect.right && point.y >= rect.top && point.y <= rect.bottom;
}

function pointInsideTrashZone(point) {
  const rect = trashZoneRect();
  if (!rect) return false;
  return point.x >= rect.left && point.x <= rect.right && point.y >= rect.top && point.y <= rect.bottom;
}

function trashZoneRect() {
  const zone = document.querySelector("[data-media-trash-zone]");
  if (!zone) return null;
  const bounds = zone.getBoundingClientRect();
  const pad = 26;
  return {
    left: bounds.left - pad,
    right: bounds.right + pad,
    top: bounds.top - pad,
    bottom: bounds.bottom + pad,
  };
}

function pointInsideAnyTrashZonePoint(...points) {
  return points.filter(Boolean).some((point) => pointInsideTrashZone(point));
}

function floatItemIntersectsTrashZone(item) {
  const trash = trashZoneRect();
  const itemRect = floatItemRect(item);
  if (!trash || !itemRect) return false;
  return itemRect.left <= trash.right && itemRect.right >= trash.left && itemRect.top <= trash.bottom && itemRect.bottom >= trash.top;
}

function floatItemRect(item) {
  const gallery = document.querySelector("[data-media-gallery]");
  if (!item || !gallery) return null;
  const rect = gallery.getBoundingClientRect();
  return {
    left: rect.left + item.x,
    right: rect.left + item.x + item.w,
    top: rect.top + item.y,
    bottom: rect.top + item.y + item.h,
  };
}

function floatItemCenter(item) {
  const gallery = document.querySelector("[data-media-gallery]");
  if (!item || !gallery) return null;
  const rect = gallery.getBoundingClientRect();
  return {
    x: rect.left + item.x + item.w / 2,
    y: rect.top + item.y + item.h / 2,
  };
}

function clearMediaDropHighlights() {
  document.querySelector("[data-media-trash-zone]")?.classList.remove("drop-ready");
  document.querySelectorAll("[data-media-folder-drop].drop-ready").forEach((node) => node.classList.remove("drop-ready"));
}

function updateMediaDropHighlights(point) {
  const trash = document.querySelector("[data-media-trash-zone]");
  const altPoint = Number.isFinite(point.altX) && Number.isFinite(point.altY) ? { x: point.altX, y: point.altY } : null;
  trash?.classList.toggle("drop-ready", Boolean(point.trashReady) || pointInsideAnyTrashZonePoint(point, altPoint));
  document.querySelectorAll("[data-media-folder-drop]").forEach((folder) => {
    const ready = point.type === "asset" && folder.classList.contains("expanded") && pointInsideElement(point, folder);
    folder.classList.toggle("drop-ready", ready);
  });
}

function captureMediaFloatPositions() {
  if (!state.mediaFloating) return;
  const gallery = document.querySelector("[data-media-gallery]");
  if (gallery) {
    const galleryRect = gallery.getBoundingClientRect();
    if (galleryRect.width < 80 || galleryRect.height < 80) return;
  }
  if (mediaFloatItems.length) {
    mediaFloatItems.forEach((item) => {
      state.mediaFloatPositions[item.key] = {
        x: item.x,
        y: item.y,
        vx: 0,
        vy: 0,
      };
    });
    return;
  }
  if (!gallery) return;
  const galleryRect = gallery.getBoundingClientRect();
  gallery.querySelectorAll("[data-media-item]").forEach((node) => {
    const key = mediaFloatKey(node);
    const rect = node.getBoundingClientRect();
    state.mediaFloatPositions[key] = {
      x: rect.left - galleryRect.left,
      y: rect.top - galleryRect.top,
      vx: 0,
      vy: 0,
    };
  });
}

async function animateFloatToGrid() {
  const gallery = document.querySelector("[data-media-gallery]");
  if (!gallery) return;
  const cards = Array.from(gallery.querySelectorAll("[data-media-item]"));
  if (!cards.length) return;
  if (mediaFloatFrame) cancelAnimationFrame(mediaFloatFrame);
  mediaFloatFrame = 0;
  const floating = cards.map((node) => ({ node, rect: node.getBoundingClientRect() }));
  gallery.classList.add("settling");
  gallery.classList.remove("floating");
  gallery.style.minHeight = "";
  cards.forEach((node) => {
    node.removeEventListener("pointerdown", startFloatDrag);
    node.style.transform = "";
    node.dataset.floatReady = "false";
  });
  const settled = new Map(cards.map((node) => [node, node.getBoundingClientRect()]));
  await Promise.all(
    floating.map(({ node, rect }) => {
      const target = settled.get(node);
      if (!target) return Promise.resolve();
      const dx = rect.left - target.left;
      const dy = rect.top - target.top;
      return node
        .animate(
          [
            { transform: `translate(${dx}px, ${dy}px)`, opacity: 0.96 },
            { transform: "translate(0, 0)", opacity: 1 },
          ],
          { duration: 320, easing: "cubic-bezier(.2,.8,.2,1)" }
        )
        .finished.catch(() => {});
    })
  );
  gallery.classList.remove("settling");
  mediaFloatDrag = null;
  mediaFloatItems = [];
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
  state.notebooks = payload.notebooks || state.notebooks || [];
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
              <form class="backup-export-form" data-action="export-backup">
                <div>
                  <h3>导出范围</h3>
                  <div class="choice-grid choice-grid-export">
                    ${exportOptions(payload.module_catalog)}
                  </div>
                </div>
                <div class="form-grid compact backup-inline-fields">
                  <label>模块 ID<input name="module_id" placeholder="导出自定义模块或拓展包时填写"></label>
                </div>
                ${check("include_security", "包含管理员密码和接口密钥", false)}
                <div class="actions"><button class="primary">导出所选范围</button></div>
              </form>
              <form class="upload-zone" data-action="import-backup">
                <input name="backup_file" type="file" accept=".zip" required>
                <label class="compact-select-label">导入策略<select name="strategy"><option value="safe">安全合并：已有文件跳过</option><option value="overwrite">覆盖合并：先备份再覆盖</option></select></label>
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
  state.notebookDeleteIds = [];
  state.t2iTemplateDialogOpen = false;
  state.t2iCustomOpen = false;
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
        <button class="button module-detail-back" data-settings-back type="button">返回模块管理</button>
        <div>
          <h2>${escapeHtml(title)}</h2>
          ${description ? `<p class="muted">${escapeHtml(description)}</p>` : ""}
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

function notebookOriginParts(item = {}) {
  const origin = String(item.origin_umo || "");
  const parts = origin.split(":");
  return {
    platform_id: item.platform_id || parts[0] || "aiocqhttp",
    message_type: item.message_type || parts[1] || "group",
    session_id: item.session_id || parts.slice(2).join(":") || "",
  };
}

function notebookRow(item, options = {}) {
  const id = item.id || item.notebook_id || options.id || `notebook_${Date.now()}`;
  const origin = notebookOriginParts(item);
  const isDefault = id === "default";
  return `
    <div class="notebook-row" data-notebook-row="${escapeHtml(id)}">
      <input name="notebook_id" value="${escapeHtml(id)}" type="hidden">
      <input name="notebook_platform_${escapeHtml(id)}" value="${escapeHtml(origin.platform_id)}" type="hidden">
      <label>名称<input name="notebook_name_${escapeHtml(id)}" value="${escapeHtml(item.name || (options.draft ? "新日记本" : id))}" placeholder="例如：主群日记本"></label>
      <label>会话类型<select name="notebook_message_type_${escapeHtml(id)}"><option value="group" ${origin.message_type !== "private" ? "selected" : ""}>群聊</option><option value="private" ${origin.message_type === "private" ? "selected" : ""}>私聊</option></select></label>
      <label>QQ号或群号<input name="notebook_session_${escapeHtml(id)}" value="${escapeHtml(origin.session_id)}" placeholder="私聊填 QQ 号，群聊填群号"></label>
      <label>写日记时间<input name="notebook_archive_time_${escapeHtml(id)}" type="time" value="${escapeHtml(item.archive_time || "03:00")}"></label>
      <label>推送目标<select name="notebook_push_target_${escapeHtml(id)}"><option value="none" ${item.push_target === "none" ? "selected" : ""}>不推送</option><option value="admin_private" ${item.push_target === "admin_private" ? "selected" : ""}>管理员私聊</option><option value="source" ${item.push_target === "source" ? "selected" : ""}>原会话</option><option value="both" ${item.push_target === "both" ? "selected" : ""}>两边都推送</option></select></label>
      <label class="check"><input name="notebook_enabled_${escapeHtml(id)}" type="checkbox" ${item.enabled !== false ? "checked" : ""}>启用</label>
      <label class="check"><input name="notebook_auto_archive_${escapeHtml(id)}" type="checkbox" ${item.auto_archive_enabled !== false ? "checked" : ""}>自动写日记</label>
      <button class="button danger notebook-delete" data-notebook-delete="${escapeHtml(id)}" ${isDefault ? "disabled" : ""} type="button">${isDefault ? "默认" : "删除"}</button>
    </div>
  `;
}

function notebookManagement(notebooks = []) {
  const items = notebooks.length ? notebooks : notebookOptions();
  const rows = items.map((raw) => notebookRow({ ...raw, id: raw.id || raw.notebook_id || "default" })).join("");
  return `
    <div class="notebook-settings">
      <div class="settings-mini-head notebook-head">
        <div><strong>日记本管理</strong><span>私聊填 QQ 号，群聊填群号；页面显示使用你写的名称。</span></div>
        <button class="button primary" data-notebook-add type="button">新增日记本</button>
      </div>
      <div class="notebook-list" data-notebook-list>
        ${rows || `<div class="notice soft">还没有日记本。</div>`}
      </div>
    </div>
  `;
}

function permissionSettings(settings) {
  const selected = settings.non_admin_permissions || [];
  const item = (value, label) => `<label class="choice-card permission-choice"><input name="non_admin_permissions" value="${value}" type="checkbox" ${selected.includes(value) ? "checked" : ""}><span><strong>${label}</strong></span></label>`;
  return `
    <details class="permission-subpage">
      <summary>非管理员权限设置</summary>
      <div class="permission-grid">
        ${item("diary_read", "查看日记")}
        ${item("diary_search", "搜索日记")}
        ${item("diary_write", "写入日记")}
        ${item("diary_delete", "删除日记")}
        ${item("media_read", "查看媒体")}
        ${item("media_write", "保存媒体")}
        ${item("media_send", "发送媒体")}
        ${item("impression_read", "查看人物印象")}
        ${item("impression_write", "修改人物印象")}
      </div>
    </details>
  `;
}

function addNotebookDraft() {
  const list = document.querySelector("[data-notebook-list]");
  if (!list) return;
  list.querySelector(".notice.soft")?.remove();
  const id = `notebook_${Date.now()}`;
  const wrapper = document.createElement("div");
  wrapper.innerHTML = notebookRow({ id, name: "新日记本", enabled: true, auto_archive_enabled: true, push_target: "none" }, { draft: true }).trim();
  list.appendChild(wrapper.firstElementChild);
}

function deleteNotebookRow(id) {
  if (!id || id === "default") return;
  const row = document.querySelector(`[data-notebook-row="${CSS.escape(id)}"]`);
  if (!row) return;
  const form = row.closest("form");
  if (form) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = "notebook_delete_id";
    input.value = id;
    input.dataset.notebookDeleteInput = id;
    form.appendChild(input);
  }
  state.notebookDeleteIds = Array.from(new Set([...(state.notebookDeleteIds || []), id]));
  state.notebooks = (state.notebooks || []).filter((item) => (item.id || item.notebook_id) !== id);
  state.toast = "日记本已标记删除，保存后生效";
  row.remove();
  updateShell();
  clearToastSoon();
}

function notebookOriginFromForm(form, id) {
  const session = String(form.get(`notebook_session_${id}`) || "").trim();
  if (!session) return "";
  const platform = String(form.get(`notebook_platform_${id}`) || "aiocqhttp").trim() || "aiocqhttp";
  const messageType = String(form.get(`notebook_message_type_${id}`) || "group").trim() || "group";
  return `${platform}:${messageType}:${session}`;
}

function moduleSettingsBody(payload, detailKey) {
  const settings = payload.settings;
  if (detailKey === "diary") {
    const t2iTemplate = activeT2iTemplate(settings);
    return `
      <div class="setting-line"><div><strong>日记模块</strong><p class="muted">开启后可以记录和查看日记。</p></div>${switchControl("enable_diary_module", settings.enable_diary_module)}</div>
      <div class="setting-line"><div><strong>自动回想</strong><p class="muted">需要时让 bot 参考以前的日记。</p></div>${switchControl("memory_recall_enabled", settings.memory_recall_enabled)}</div>
      <div class="setting-line"><div><strong>自然语言管理员权限</strong><p class="muted">允许管理员用自然语言调整日记和小窝配置。</p></div>${switchControl("permissions_allow_admin_natural_language", settings.permissions_allow_admin_natural_language)}</div>
      <div class="form-grid compact">
        <label>回想方式<select name="memory_recall_policy"><option value="conservative" ${settings.memory_recall_policy === "conservative" ? "selected" : ""}>只在需要时</option><option value="active" ${settings.memory_recall_policy === "active" ? "selected" : ""}>更主动</option></select></label>
        <label>每次参考数量<input name="search_default_top_k" type="number" min="1" max="20" value="${settings.search_default_top_k}"></label>
        <label>摘要长度<input name="search_snippet_chars" type="number" min="80" max="360" value="${settings.search_snippet_chars}"></label>
        <label>推送格式<select name="diary_push_format"><option value="text" ${settings.diary_push_format !== "image" ? "selected" : ""}>文字</option><option value="image" ${settings.diary_push_format === "image" ? "selected" : ""}>图片</option></select></label>
        <label>小窝管理员 QQ<input name="nest_admin_ids" value="${escapeHtml((settings.nest_admin_ids || "").split(/\s+/)[0] || "")}" placeholder="只填一个管理员 QQ"></label>
        <label class="wide-field">写日记要求规范<textarea name="diary_write_prompt">${escapeHtml(settings.diary_write_prompt || "")}</textarea></label>
      </div>
      <input name="diary_t2i_template_name" type="hidden" value="${escapeHtml(settings.diary_t2i_template_name || t2iTemplate.id)}">
      <textarea name="diary_t2i_template" hidden>${escapeHtml(settings.diary_t2i_template || t2iTemplate.template)}</textarea>
      <div class="t2i-template-summary">
        <div><strong>图片推送模板</strong><span>${escapeHtml(t2iTemplate.name)} · ${escapeHtml(t2iTemplate.tone)}</span></div>
        <button class="button" data-t2i-open type="button">选择模板</button>
      </div>
      ${permissionSettings(settings)}
      ${notebookManagement(payload.notebooks || state.notebooks || [])}
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
      <div class="form-grid compact">
        <label>每天最多保存<input name="media_max_items_per_day" type="number" min="1" max="500" value="${settings.media_max_items_per_day || 80}"></label>
        <label>12小时图片上限<input name="media_auto_save_limit_12h" type="number" min="1" max="200" value="${settings.media_auto_save_limit_12h || 10}"></label>
        <label>写入限制策略<select name="media_auto_save_policy">
          <option value="admin_only" ${settings.media_auto_save_policy !== "bot_curated" ? "selected" : ""}>只允许管理员保存</option>
          <option value="bot_curated" ${settings.media_auto_save_policy === "bot_curated" ? "selected" : ""}>允许 bot 自主挑选</option>
        </select></label>
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
        <button class="button" data-module-settings="${escapeHtml(detailKey)}" type="button">设置</button>
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
  const appearanceLabel = isAppearance ? (module.entry_label || (module.appearance_mode === "global" ? "全局模块" : "外观模块")) : "";
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
  return options
    .map(([value, label], index) => {
      const descriptions = {
        full: "框架、模块、导入记录",
        diary: "日记正文、快照和草稿",
        impressions: "人物印象资料",
        media: "图片、附件和相册",
        webui_custom: "标题、头像和自定义页面",
        security: "管理员密码和接口密钥",
        custom_module: "填写模块 ID 后导出",
        extension: "填写拓展包 ID 后导出",
      };
      return `
        <label class="choice-card">
          <input name="package_type" value="${value}" type="checkbox" ${index === 0 ? "checked" : ""}>
          <span>
            <strong>${escapeHtml(label)}</strong>
            <em>${escapeHtml(descriptions[value] || "")}</em>
          </span>
        </label>
      `;
    })
    .join("");
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
    diary_archive_granularity: "day",
    diary_display_mode: valueField("diary_display_mode", current.diary_display_mode || "grouped"),
    admin_private_diary_enabled: false,
    admin_private_push_enabled: false,
    diary_push_format: valueField("diary_push_format", current.diary_push_format || "text"),
    diary_push_target: "none",
    diary_t2i_template_name: valueField("diary_t2i_template_name", current.diary_t2i_template_name || "plain_note"),
    permissions_allow_admin_natural_language: boolField("permissions_allow_admin_natural_language", current.permissions_allow_admin_natural_language ?? true),
    non_admin_permissions: form.getAll("non_admin_permissions"),
    nest_admin_ids: valueField("nest_admin_ids", current.nest_admin_ids || ""),
    diary_write_prompt: valueField("diary_write_prompt", current.diary_write_prompt || ""),
    diary_t2i_template: valueField("diary_t2i_template", current.diary_t2i_template || ""),
    enable_media_module: boolField("enable_media_module", current.enable_media_module),
    allow_media_refs: boolField("allow_media_refs", current.allow_media_refs),
    media_max_items_per_day: numberField("media_max_items_per_day", current.media_max_items_per_day || 80),
    media_auto_save_policy: valueField("media_auto_save_policy", current.media_auto_save_policy || "admin_only"),
    media_auto_save_limit_12h: numberField("media_auto_save_limit_12h", current.media_auto_save_limit_12h || 10),
    media_auto_album_strategy: valueField("media_auto_album_strategy", current.media_auto_album_strategy || "confirm"),
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
    appearance_modules_initialized: true,
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
  await saveNotebookSettings(formEl, form);
  refreshThemeStylesheet();
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

async function saveNotebookSettings(formEl, form) {
  const ids = Array.from(new Set(form.getAll("notebook_id").map((item) => String(item || "").trim()).filter(Boolean)));
  const deleteIds = Array.from(
    new Set([
      ...(state.notebookDeleteIds || []),
      ...form.getAll("notebook_delete_id").map((item) => String(item || "").trim()),
    ])
  ).filter((id) => id && id !== "default");
  if (!ids.length && !deleteIds.length) return;
  const current = state.notebooks || [];
  const notebooks = ids.map((id) => {
    const existing = current.find((item) => (item.id || item.notebook_id) === id) || {};
    const origin_umo = notebookOriginFromForm(form, id);
    return {
      ...existing,
      id,
      name: form.get(`notebook_name_${id}`) || existing.name || id,
      origin_umo,
      platform_id: origin_umo ? origin_umo.split(":")[0] : "",
      message_type: origin_umo ? origin_umo.split(":")[1] : "",
      session_id: origin_umo ? origin_umo.split(":").slice(2).join(":") : "",
      enabled: form.has(`notebook_enabled_${id}`),
      auto_archive_enabled: form.has(`notebook_auto_archive_${id}`),
      archive_time: form.get(`notebook_archive_time_${id}`) || existing.archive_time || "03:00",
      push_enabled: (form.get(`notebook_push_target_${id}`) || existing.push_target || "none") !== "none",
      push_target: form.get(`notebook_push_target_${id}`) || existing.push_target || "none",
      push_format: form.get("diary_push_format") || existing.push_format || "text",
    };
  });
  const payload = await api("/api/ui/notebooks", { method: "POST", body: JSON.stringify({ notebooks, delete_ids: deleteIds, replace: true }) });
  state.notebooks = payload.items || notebooks;
  state.notebookDeleteIds = [];
  formEl.querySelectorAll('[name="notebook_delete_id"]').forEach((input) => input.remove());
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
  const selected = form.getAll("package_type");
  const params = new URLSearchParams({
    package_type: (selected.length ? selected : ["full"]).join(","),
    module_id: form.get("module_id") || "",
    include_security: form.has("include_security") ? "true" : "false",
  });
  window.location.href = `/api/ui/export?${params.toString()}`;
}

function syncExportChoices(target) {
  const form = target.closest("form");
  if (!form) return;
  const choices = Array.from(form.querySelectorAll('input[name="package_type"]'));
  const full = choices.find((item) => item.value === "full");
  if (!full) return;
  if (target.value === "full" && target.checked) {
    choices.forEach((item) => {
      if (item !== full) item.checked = false;
    });
    return;
  }
  if (target.value !== "full" && target.checked) {
    full.checked = false;
  }
  if (!choices.some((item) => item.checked)) {
    full.checked = true;
  }
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
