# 小窝模块化框架约定

小窝以 AstrBot 插件为统一入口。插件负责启动框架、注册工具、提供 WebUI、加载 skills，并管理官方模块。日记只是一个模块，不是小窝本体。

小窝支持内置 UI：在 AstrBot 插件页里打开小窝，加载的就是完整界面，登录态由插件页桥接。所有数据请求经桥接转发到 `/api/ui/*`，自定义模块的资源与存储接口也收在这个前缀下，因此第三方模块在内置 UI 和浏览器里表现一致。独立端口只是进阶直连方式，不是使用小窝的前提。

## 目录边界

```text
data/
  framework/
  modules/
  imports/
```

`framework/` 只放小窝框架级数据：

- 管理员密码和外部 API Key
- WebUI 设置
- 前端主题与用户自定义页面
- 框架缓存和日志

`modules/` 只放功能模块数据：

- `modules/diary/`
- `modules/impressions/`
- `modules/media/`
- 未来新增的 `modules/<module-id>/`
- 拓展包数据 `modules/extensions/<extension-id>/`

模块之间不能直接互相改文件。需要协作时，通过工具、API、稳定 ID 或引用字段连接。

## 框架配置与插件配置

插件配置负责 AstrBot 侧能力：

- 运行模式：`embedded` 或 `standalone`
- 是否启用 WebUI
- 数据根目录
- 后台定时任务使用哪个会话作为上下文
- 进阶：内置服务的监听地址和端口，只在需要从别的设备直连时才需要调整

小窝 WebUI 设置负责小窝自身：

- 管理员密码
- 可选外部 API Key
- 官方模块和日记模块开关
- 前端主题
- 自定义模块启用与侧边栏入口显示
- 人物印象模块、自动识别、写入程度和更新策略
- 备忘录模块、敏感内容默认隐藏和 bot 自主写入策略
- 外观设置页里的官方全局外观选择
- 导入、导出、备份
- 版本检测和更新
- 首次使用引导完成状态
- 从链接安装模块包，以及卸载自定义模块

## 模块规范

完整模块建议提供：

```text
modules/<module-id>/
  module.json
  page.js
  data/
  index/
  snapshots/
```

拓展包建议提供：

```text
modules/extensions/<extension-id>/
  module.json
  data/
  index/
```

`module.json` 的身份与关系字段：

- 模块 id、名称、版本
- 类型：`module` 或 `extension`
- 功能标签：`feature_tags`
- 目标模块：`target_modules`，拓展包使用
- 替代关系：`replaces`
- 冲突声明：`conflicts_with`
- 数据目录
- 暴露工具
- 依赖模块
- schema 版本

## 能力声明

身份字段只说明这是谁。模块参与哪些能力面，由能力声明决定；没有声明的能力面就不会开放。这样只提供工具或数据的模块不会被迫顶着一个空页面和一个空入口。

```json
{
  "runtime": "webui",
  "nav": { "label": "打卡", "icon": "modules", "order": 310 },
  "page": { "entry": "page.js", "export": "mount", "title": "习惯打卡" },
  "store": true
}
```

`runtime` 分两档。`webui` 是推荐档：模块只有 `module.json` 和 `page.js`，数据走小窝的通用存储，不需要自带后端，bot 自己就能产出。`python` 是逃生口：模块自带后端代码在插件进程里运行，因此安装后不会被自动启用，必须由用户手动开启。

`nav` 决定侧边栏入口。`label` 是文字，`icon` 取内置图标名（`home`、`diary`、`search`、`impressions`、`media`、`memos`、`modules`、`settings`、`appearance`、`access`、`backup`、`webui`）或模块自带的图片相对路径，`order` 决定位置——官方入口占 10 到 60，设置固定在 900，自定义模块默认 500。不想要入口就整个省掉 `nav`。

`page` 指向模块自带的 ES module，必须是模块目录内的相对 `.js` 或 `.mjs` 路径，`export` 默认取 `mount`。声明了 `nav` 却没有 `page` 会被拒绝并在模块卡片上说明原因，因为一个通向空白的入口比没有入口更糟。

`store` 打开框架提供的按模块隔离的 JSON 存储。写 `true`，或写成对象用 `max_bytes` 收紧默认的 1 MB 上限。

## 页面契约

`page.js` 导出 `mount(root, ctx)`。小窝交给它一块空面板和一个能力包，可以返回 `{ update, unmount }`。

`ctx.store` 提供 `keys()`、`get(key, fallback)`、`set(key, value)`、`remove(key)`，数据落在 `modules/<module-id>/data/store/<key>.json`。键名限字母数字下划线点连字符，最长 64 字符，单模块最多 64 个键，单文档 1 MB。

`ctx.request(path, options)` 调用模块自己的命名空间后端 `/api/ui/modules/<module-id>/…`，只对 `python` 档有意义。`ctx.assetUrl(relativePath)` 解析模块自带文件。`ctx.notify`、`ctx.reportError`、`ctx.confirm` 分别是提示、报错和确认弹窗——不要用 `window.confirm`，它在 AstrBot 插件页里不工作。`ctx.escapeHtml`、`ctx.icon`、`ctx.refresh`、`ctx.insidePluginPage` 是框架自己的辅助能力。

如果模块在 `root` 之外挂了定时器、全局监听或 observer，必须返回 `unmount` 回收。模块被停用、卸载或入口文件变化时，小窝会调用它。

模块资源由 `/api/ui/module-assets/<module-id>/` 提供，页面路由是 `/m/<module-id>`。收在 `/api/ui/` 前缀下是为了让 AstrBot 插件页的桥接白名单不必为第三方模块反复放开。允许的资源类型：`.js .mjs .css .json .svg .png .jpg .jpeg .webp .gif .woff2 .html .txt .md`，路径穿越一律拒绝。

## 内置 skill 与常见问题

小窝内置 `nest-module-development` skill。bot 创建、修改、安装或排查自定义模块时应遵循这份 skill，并在直接写入或修改模块文件后明确提醒用户：需要重启 AstrBot（或重载插件）再刷新页面，单独刷新浏览器不保证插件运行时会重新发现模块。

若侧边栏入口没有出现，依次检查：模块是否同时声明 `nav` 和 `page`，是否已在模块控制台启用且未隐藏入口，以及 `page.entry` 和自定义图标是否通过框架验真。模块详情页会展示校验失败原因。内置 UI 与独立 WebUI 都应能加载已验证的模块页面；更新后若仍显示旧内容，先重启 AstrBot，再刷新页面。

## 三层把关

入口和页面能不能出现，要同时过三层，任何一层没过都会在模块卡片上写明原因：

模块自己声明。没有 `nav` 就没有入口，没有 `page` 就没有页面。

用户在模块控制台启用。已安装但关闭的模块，其资源与存储接口一律 404；用户也可以让模块保持启用、只隐藏侧边栏入口。

框架验真。声明的 `page.entry` 和 nav 图标必须真实存在且类型允许，否则入口被收回。

推荐优先做拓展包。只有确实要替代整套能力时，才创建完整模块并声明 `replaces` / `conflicts_with`。例如重构日记模块时，不要直接修改官方 `diary`，而是创建 `diary-plus`。

模块控制台只提示完整模块冲突，不强制禁用。用户可以保留多个完整模块，但需要承担入口重复、工具重复或数据口径不一致的风险。拓展包用于补充增强，不因功能标签重叠被限制。

人物印象是独立官方模块。日记保存后不会直接因为 `people` 字段出现新称呼就自动建档；是否交给 bot 自动识别、是否允许新建候选档、写入程度和更新策略由 WebUI 的“模块控制台 → 人物印象”详情页控制。

备忘录是独立官方模块。短纸条数据保存在 `modules/memos/items.json`，适合账号提示、聊天片段、名言、待办和 bot 自主挑出的短记忆。模块关闭后左侧备忘录入口消失，bot 侧备忘录工具也应拒绝写入或读取。

## 自定义前端

用户或 bot 自己改的小窝外观放在：

```text
framework/user_custom/webui/
```

推荐结构：

```text
framework/user_custom/webui/themes/<theme-id>/style.css
framework/user_custom/webui/appearance/<appearance-id>/
framework/user_custom/webui/modules/<module-id>/
framework/user_custom/webui/extensions/<extension-id>/
framework/user_custom/webui/static/
```

`framework/user_custom/webui/modules/<module-id>/` 也会被当作模块前端根目录搜索，契约与 `modules/<module-id>/` 相同：`module.json` 加 `page.js`。注意模块目录里的 `templates/` 不会被 SPA 加载——服务端渲染的模块模板不在当前契约内，新页面请走 `page.js`。

官方更新只更新插件默认文件，不覆盖 `framework/user_custom/webui/`。

外观模块可以声明 `type: "appearance"` 和 `appearance_mode`。`appearance_mode: "global"` 表示全局替换小窝前端样式；官方全局外观收束在“设置 → 外观设置”里选择，不作为普通模块卡片散落展示。其他值按补充拓展处理，可以作为模块控制台里的外观拓展出现。

`0.5.15` 内置三套官方全局外观：

- `nest-paper-garden`：纸庭，偏纸感手账和长期阅读。
- `nest-glass-cabin`：玻璃小屋，偏轻玻璃、清爽管理界面。
- `nest-night-atelier`：夜间工作室，偏温柔深色和夜间维护。

用户自定义全局外观应放在 `framework/user_custom/webui/themes/<theme-id>/style.css` 或 `framework/user_custom/webui/appearance/<appearance-id>/`。官方更新只替换插件内置文件，不覆盖这些目录。

新页面应优先使用 `--paper`、`--panel`、`--wash`、`--ink`、`--muted` 等共享变量和通用组件类，让官方外观自然覆盖。不要为默认、纸庭、玻璃小屋和夜间工作室各写一套独立前端；只有新组件拥有独特视觉表面时，才给主题补少量覆盖。

如果自定义前端或模块对其他人也有价值，建议整理成 PR 提交到项目仓库。PR 应该聚焦，不要一次提交过多无关改动。

## 安装与卸载

从链接安装接受包含 `module.json` 的 zip 或 GitHub 仓库。官方模块 ID（`diary`、`impressions`、`media`、`memos`、`webui`）和官方外观 ID 一律拒绝。目标目录已存在时，会先备份到 `imports/module-install-backups/` 再覆盖。声明 `runtime: "python"` 的包不会被自动启用，即使用户勾了"安装后启用"，也必须由用户手动打开。

卸载会把整个模块目录备份到 `imports/module-uninstall-backups/` 后删除。"卸载并保留数据"会保住 `modules/<id>/data`，只摘掉前端文件和开关。官方模块不能卸载，只能关闭。

## 分层导入导出

导出包必须包含 `manifest.json`，用于说明：

- `package_type`
- `module_id`
- `created_at`
- `nest_version`
- `schema_version`

支持的导出范围：

- `full`
- `diary`
- `impressions`
- `media`
- `memos`
- `webui_custom`
- `custom_module`
- `extension`
- `security`

导入策略：

- `safe`：已有文件跳过。
- `overwrite`：已有文件先备份到 `imports/import-backups/`，再覆盖。

除 `security` 包或用户显式勾选外，默认不导出管理员密码和外部 API Key。

## API Key

embedded 模式下，插件内部工具不需要 API Key。

API Key 只用于外部扩展，例如 MCP、脚本、第三方网页、其他 bot 或 standalone 兼容模式。
