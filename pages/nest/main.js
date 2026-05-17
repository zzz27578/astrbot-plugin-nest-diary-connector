(async () => {
  const setText = (id, text) => {
    const node = document.getElementById(id);
    if (node) node.textContent = text;
  };

  const error = document.getElementById("error");
  const defaultWebuiUrl = `http://${window.location.hostname}:28080`;
  const link = document.getElementById("open-webui");
  if (link) link.href = defaultWebuiUrl;

  const readStatus = async () => {
    if (window.AstrBotPluginPage?.apiGet) {
      const routes = ["status", "nest-diary/status"];
      let lastError;
      for (const route of routes) {
        try {
          return await window.AstrBotPluginPage.apiGet(route);
        } catch (err) {
          lastError = err;
        }
      }
      throw lastError || new Error("Plugin Page API unavailable");
    }

    const urls = [
      "/api/plugin/astrbot_plugin_nest_diary_connector/status",
      "/api/plugin/astrbot_plugin_nest_diary_connector/nest-diary/status",
      "/api/plugin/nest-diary/status",
      "/api/plugin/status",
    ];
    let lastError;
    for (const url of urls) {
      try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
      } catch (err) {
        lastError = err;
      }
    }
    throw lastError || new Error("status unavailable");
  };

  try {
    const payload = await readStatus();
    const status = payload?.data || payload;
    const host = status.web_host === "0.0.0.0" ? window.location.hostname : status.web_host;
    const webuiUrl = `http://${host}:${status.web_port}`;

    setText("mode", `${status.mode} / v${status.version}`);
    setText("webui", status.webui_started ? webuiUrl : status.webui_error || "未启动");
    setText("data-dir", status.data_dir);
    setText("custom-dir", status.custom_webui_dir);

    if (link) link.href = webuiUrl;
  } catch (err) {
    setText("webui", defaultWebuiUrl);
    if (error) {
      error.hidden = false;
      error.textContent = `无法读取插件状态，已使用默认 WebUI 地址：${err.message}`;
    }
  }
})();
