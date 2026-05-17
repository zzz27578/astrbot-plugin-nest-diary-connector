# AstrBot 小窝日记插件

版本：`0.2.0`

小窝现在已经合并进插件仓库。默认模式下，插件自己提供：

- bot 原生工具
- 日记、搜索、媒体、人物印象核心模块
- 密码保护 WebUI
- 模块化数据目录
- 内置 Skill
- 定时写日记提示

旧的独立小窝服务仍可兼容，但不再是默认路径。

## 默认运行方式

插件配置保持：

```text
nest_mode=embedded
enable_webui=true
web_port=28080
admin_password=12345678
```

启动插件后，小窝 WebUI 会由插件内置启动：

```text
http://服务器IP:28080
```

默认数据目录：

```text
/AstrBot/data/plugins_data/astrbot_plugin_nest_diary_connector
```

本地开发时，如果没有 `/AstrBot`，会落到插件目录下的 `data/`。

## 数据结构

```text
data/
  system/settings/
  modules/diary/entries/
  modules/diary/index/
  modules/diary/snapshots/
  modules/impressions/people/
  modules/media/blobs/
  modules/media/by-date/
  user_custom/webui/templates/
  user_custom/webui/static/
  user_custom/webui/themes/
  user_custom/webui/modules/
```

`user_custom/` 是用户或 bot 自己修改前端、主题、模块的地方。官方更新不应覆盖这里。

## 自定义 WebUI

默认页面在插件代码内：

```text
nest_diary_web/web/templates/
nest_diary_web/web/static/
```

个性化页面放到数据目录：

```text
user_custom/webui/templates/
user_custom/webui/static/
```

渲染时会先找 `user_custom/webui/templates` 中的同名模板，找不到再回退官方默认模板。自定义模板里的资源可以放在 `user_custom/webui/static`，并用 `/custom-static/文件名` 引用。

这样更新插件时只更新官方默认模块，不会覆盖 bot 自己改出来的小窝外观。

## API Key

embedded 模式下，插件内部工具不需要 API Key。

小窝 WebUI 设置中的外部 API Key 只给这些场景使用：

- MCP
- 外部脚本
- 第三方网页
- 其他 bot
- 兼容 standalone 模式

## 兼容独立服务模式

如果还想继续使用旧的小窝服务容器：

```text
nest_mode=standalone
service_url=http://nest-diary:28080
bot_api_token=独立服务里的外部 API Key
```

此时插件工具通过 HTTP 调用独立服务。

## 常用命令

```text
/小窝状态
```

查看小窝模式、日记模块状态、WebUI 地址和数据目录。

```text
/小窝绑定提醒
```

在目标会话发送，复制返回的 `unified_msg_origin`，填入插件配置 `daily_target_origin`。

## LLM 工具

- `nest_status`
- `write_diary`
- `search_diary`
- `read_diary`
- `attach_media`
- `list_impressions`
- `read_impression`
- `write_impression`

`write_diary` 必须提供 bot 自拟标题：

```text
title: 用一句话概括当天记忆，不要直接使用日期
```

## 模块清单

```text
modules/diary/module.json
modules/webui/module.json
```

模块化约定见：

```text
docs/modular-nest.md
```

## Skill

内置 Skill：

```text
skills/nest-diary/SKILL.md
skills/nest-webui-customization/SKILL.md
```

`nest-diary` 约束 bot 使用工具，不模拟人操作网页；查记忆先搜索；写日记要有标题、主观评价、情绪和检索线索；人物印象只在有稳定证据时更新。

`nest-webui-customization` 约束 bot 做小窝前端自定义时只改数据目录下的 `user_custom/webui/`，不直接改插件内置默认页面；同时要求按钮、路由、表单都必须对应真实功能，避免做出不能用的假界面。
