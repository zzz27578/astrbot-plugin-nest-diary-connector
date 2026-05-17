# AstrBot 小窝日记插件

版本：`0.1.9`

这是小窝系统的 AstrBot 插件入口。目标架构是：插件提供 bot 原生工具、模块注册、默认 WebUI、定时提示和内置 Skill；小窝网页是插件的 WebUI 端，而不是让 bot 模拟人操作网页。

当前版本仍兼容“插件 + 独立小窝服务”的部署方式，所以 `service_url` 和 `bot_api_token` 暂时保留。后续合并为插件内置 WebUI 后，外部 API Key 将只在小窝 WebUI 设置中管理。

## 本轮模块化方向

- 插件配置负责 AstrBot 侧能力：模块启用、WebUI 端口、数据目录、定时提示。
- 小窝 WebUI 设置负责小窝自身：管理员密码、外部 API Key、前端样式、模块管理、导入导出、备份。
- 官方更新不覆盖用户自定义前端和自定义模块。
- 每个模块都提供 `module.json`，声明工具、路由、数据目录和 schema 版本。

## 安装

把本仓库放入 AstrBot 插件目录：

```text
/AstrBot/data/plugins/astrbot_plugin_nest_diary_connector
```

然后在 AstrBot 插件管理页启用插件。

## 插件配置

核心配置：

```text
enable_diary_module: 是否启用日记模块
enable_webui: 是否启用小窝 WebUI
web_host: WebUI 监听地址
web_port: WebUI 监听端口
nest_data_dir: 小窝数据根目录，留空则使用插件数据目录
custom_webui_dir: 自定义前端目录，更新不会覆盖
backup_custom_before_update: 更新官方模块前备份自定义模块
daily_target_origin: 定时提示发送到哪个会话
```

兼容独立服务模式：

```text
service_url: 独立小窝服务地址，例如 http://nest-diary:28080
bot_api_token: 独立服务模式下的小窝 API token
```

`bot_api_token` 不是管理员网页密码。未来插件内置模式下，外部 API Key 只在小窝 WebUI 设置里管理。

## 命令

```text
/小窝状态
```

检查小窝连接状态，并显示日记模块是否启用。

```text
/小窝绑定提醒
```

在目标会话发送，复制返回的 `unified_msg_origin`，填入插件配置 `daily_target_origin`。

## LLM 工具

### `write_diary`

写入或更新某一天的小窝日记。日记模块关闭时不会执行。

```text
date: YYYY-MM-DD
title: bot 自拟标题，用一句话概括当天记忆；不要直接使用日期
body: 日记正文，包含事件、意义、主观评价、情绪、人物和未来线索
mood: 情绪词，多个用逗号分隔
tags: 检索标签，多个用逗号分隔
people: 相关人物，多个用逗号分隔
media_refs: 媒体引用，每行一个，可空
reason: 写入原因，例如 nightly_archive、manual_update
```

### `search_diary`

按关键词、日期、人名、事件或情绪线索搜索日记。用于回忆检索，避免一次性读取全部日记。

### `read_diary`

读取指定日期日记。只有日期明确或搜索结果指向某一天时使用。

### `attach_media`

把 AstrBot 容器内可访问的图片、语音或附件归档到小窝媒体库。

### `list_impressions` / `read_impression` / `write_impression`

管理人物印象。只有日记或对话提供稳定新证据时才调用 `write_impression`。

## 内置 Skill

插件内置：

```text
skills/nest-diary/SKILL.md
```

Skill 负责约束 bot：

- 查记忆先搜索，不全量读取。
- 写日记必须有自拟标题、主观评价、情绪和检索线索。
- 使用工具，不模拟人操作网页。
- 尊重模块开关。
- 媒体先归档，再把媒体引用写进日记。
- 人物印象只在有稳定证据时更新。

## 模块清单

当前已有模块清单：

```text
modules/diary/module.json
modules/webui/module.json
```

更多约定见：

```text
docs/modular-nest.md
```
