# 小窝模块化框架约定

小窝以插件为统一入口。插件提供 bot 原生工具、模块注册、默认 WebUI 和内置 Skill；网页和数据是插件能力的一部分，不再需要单独维护一个服务仓库。

## 配置边界

插件配置负责 AstrBot 侧能力：

- 运行模式：`embedded` 或 `standalone`。
- 是否启用日记模块。
- 是否启用插件内置 WebUI。
- WebUI 监听地址和端口。
- 数据根目录。
- 自定义前端目录。
- 定时提示发送到哪个会话。

小窝 WebUI 设置负责小窝自身：

- 管理员密码。
- 可选的外部 API Key。
- 前端主题管理。
- 模块显示和行为开关。
- 导入、导出、备份。
- 版本检测。

## API Key

embedded 模式下，插件内部调用小窝核心模块时不需要 API Key。API Key 只用于外部扩展，例如 MCP、脚本、第三方网页、其他 bot 或 future clients。

`service_url` 和 `bot_api_token` 仅用于 `standalone` 兼容模式。

## 模块清单

每个模块必须提供 `module.json`，声明：

- 模块 id、名称、版本。
- 数据目录。
- 暴露的工具。
- Web 路由。
- 依赖模块。
- 数据 schema 版本。

官方更新只更新插件代码和默认模块，不直接覆盖用户自定义目录。

## 自定义前端

用户或 bot 自己改的页面放在数据目录下：

```text
user_custom/webui/themes/
user_custom/webui/modules/
user_custom/webui/templates/
user_custom/webui/static/
```

默认渲染规则：

```text
先找 user_custom/webui/templates 里的同名页面
没有 -> 回退到插件内置官方默认页面
```

自定义模板可以通过 `/custom-static/...` 引用 `user_custom/webui/static/` 里的资源。更新前应备份 `user_custom/`，避免覆盖个性化设计。
