(async () => {
  const setText = (id, text) => {
    const node = document.getElementById(id);
    if (node) node.textContent = text;
  };

  const error = document.getElementById("error");

  try {
    let status;
    if (window.AstrBotPluginPage?.apiGet) {
      status = await window.AstrBotPluginPage.apiGet("nest-diary/status");
    } else {
      const response = await fetch("/api/plugin/nest-diary/status");
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      status = await response.json();
    }
    const host = status.web_host === "0.0.0.0" ? window.location.hostname : status.web_host;
    const webuiUrl = `http://${host}:${status.web_port}`;

    setText("mode", `${status.mode} / v${status.version}`);
    setText("webui", status.webui_started ? webuiUrl : status.webui_error || "未启动");
    setText("data-dir", status.data_dir);
    setText("custom-dir", status.custom_webui_dir);

    const link = document.getElementById("open-webui");
    if (link) link.href = webuiUrl;
  } catch (err) {
    if (error) {
      error.hidden = false;
      error.textContent = `无法读取插件状态：${err.message}`;
    }
  }
})();
