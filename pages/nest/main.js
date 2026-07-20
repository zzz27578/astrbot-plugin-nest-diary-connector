const PLUGIN_NAME = "astrbot_plugin_nest_diary_connector";
const DEFAULT_WEBUI_PORT = 28080;
const BRIDGE_WAIT_TIMEOUT = 5000;

const elements = {
  mode: document.getElementById("mode"),
  webui: document.getElementById("webui"),
  dataDir: document.getElementById("data-dir"),
  customDir: document.getElementById("custom-dir"),
  badge: document.getElementById("status-badge"),
  link: document.getElementById("open-webui"),
  retry: document.getElementById("retry"),
  error: document.getElementById("error"),
  errorMessage: document.getElementById("error-message"),
};

function setText(element, value, fallback = "—") {
  if (element) element.textContent = value === undefined || value === null || value === "" ? fallback : String(value);
}

function isLocalAddress(host) {
  const normalized = String(host || "").trim().toLowerCase().replace(/^\[|\]$/g, "");
  return !normalized || ["0.0.0.0", "::", "::0", "localhost", "127.0.0.1", "::1"].includes(normalized);
}

function formatHost(host) {
  const publicHost = isLocalAddress(host) ? window.location.hostname : String(host).trim();
  return publicHost.includes(":") && !publicHost.startsWith("[") ? `[${publicHost}]` : publicHost;
}

function webuiUrl(host = window.location.hostname, port = DEFAULT_WEBUI_PORT) {
  return `http://${formatHost(host)}:${Number(port) || DEFAULT_WEBUI_PORT}`;
}

function setLink(url, enabled = true) {
  if (!elements.link) return;
  elements.link.href = enabled ? url : "#";
  elements.link.classList.toggle("is-disabled", !enabled);
  elements.link.setAttribute("aria-disabled", String(!enabled));
  elements.link.tabIndex = enabled ? 0 : -1;
}

function setBadge(label, state) {
  setText(elements.badge, label);
  if (elements.badge) elements.badge.className = `status-badge is-${state}`;
}

function setLoading() {
  setText(elements.mode, "读取中");
  setText(elements.webui, "读取中");
  setText(elements.dataDir, "读取中");
  setText(elements.customDir, "读取中");
  setBadge("正在连接", "loading");
  if (elements.retry) elements.retry.hidden = true;
  if (elements.error) elements.error.hidden = true;
}

function waitForBridge(timeout = BRIDGE_WAIT_TIMEOUT) {
  if (window.AstrBotPluginPage) return Promise.resolve(window.AstrBotPluginPage);

  return new Promise((resolve, reject) => {
    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      if (window.AstrBotPluginPage) {
        window.clearInterval(timer);
        resolve(window.AstrBotPluginPage);
      } else if (Date.now() - startedAt >= timeout) {
        window.clearInterval(timer);
        reject(new Error("AstrBot 插件页面桥接未加载"));
      }
    }, 50);
  });
}

async function readStatus() {
  const bridge = await waitForBridge();
  if (typeof bridge.ready === "function") await bridge.ready();
  if (typeof bridge.apiGet !== "function") throw new Error("当前 AstrBot 版本不支持插件页面接口");
  return bridge.apiGet("status");
}

function normalizeStatus(payload) {
  const status = payload?.data ?? payload;
  if (!status || typeof status !== "object") throw new Error("插件状态接口返回了无效数据");
  return status;
}

function renderStatus(status) {
  const url = webuiUrl(status.web_host, status.web_port);
  const version = String(status.version || "").replace(/^v/i, "");
  const mode = status.mode || "unknown";

  setText(elements.mode, version ? `${mode} · v${version}` : mode);
  setText(elements.dataDir, status.data_dir);
  setText(elements.customDir, status.custom_webui_dir, "默认目录");

  if (!status.webui_enabled) {
    setText(elements.webui, "未启用");
    setBadge("WebUI 未启用", "muted");
    setLink(url, false);
  } else if (status.webui_started) {
    setText(elements.webui, url);
    setBadge("运行正常", "success");
    setLink(url, true);
  } else {
    setText(elements.webui, status.webui_error || "尚未启动");
    setBadge(status.webui_error ? "启动失败" : "等待启动", status.webui_error ? "error" : "warning");
    setLink(url, true);
  }

  if (elements.retry) elements.retry.hidden = true;
  if (elements.error) elements.error.hidden = true;
}

function renderError(error) {
  const fallbackUrl = webuiUrl();
  setText(elements.mode, "状态未知");
  setText(elements.webui, fallbackUrl);
  setText(elements.dataDir, "无法读取");
  setText(elements.customDir, "无法读取");
  setBadge("连接失败", "error");
  setLink(fallbackUrl, true);

  if (elements.retry) elements.retry.hidden = false;
  if (elements.error) elements.error.hidden = false;
  setText(
    elements.errorMessage,
    `${error?.message || "未知错误"}。你仍可尝试打开默认地址 ${fallbackUrl}。`,
  );
}

async function loadStatus() {
  setLoading();
  try {
    renderStatus(normalizeStatus(await readStatus()));
  } catch (error) {
    console.error(`[${PLUGIN_NAME}] failed to load plugin page status`, error);
    renderError(error);
  }
}

if (elements.retry) elements.retry.addEventListener("click", loadStatus);
if (elements.link) {
  elements.link.addEventListener("click", (event) => {
    if (elements.link?.getAttribute("aria-disabled") === "true") event.preventDefault();
  });
}

loadStatus();