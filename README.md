# AstrBot 小窝日记连接插件

版本：`0.1.8`

这是小窝日记系统的 AstrBot 连接层。插件不保存大量日记、图片和索引，只负责给 bot 提供可调用工具、内置 Skill、定时提示和服务门牌号。

## 它解决什么

- 让 bot 通过工具直接写入、读取、搜索小窝日记。
- 让 bot 归档图片、语音或附件，并把媒体引用写进日记。
- 让 bot 维护人物印象，但只在有稳定证据时更新。
- 通过插件配置定时向指定会话发送“写日记提示”，由 bot 根据人设和当天上下文自主执行。

## 安装

把本仓库放入 AstrBot 插件目录：

```text
/AstrBot/data/plugins/astrbot_plugin_nest_diary_connector
```

然后在 AstrBot 插件管理页启用插件，并填写配置：

```text
service_url: 小窝本体服务地址，例如 http://nest-diary:28080
bot_api_token: 小窝设置页中的 Bot API Token
daily_target_origin: 定时提示要发送到的会话 origin
```

`bot_api_token` 必须和小窝本体设置页里的 Bot API Token 一致。管理员网页密码只用于登录网站，不是插件 token。

## 命令

```text
/小窝状态
```

检查小窝服务是否可用。

```text
/小窝绑定提醒
```

在目标会话发送，复制返回的 `unified_msg_origin`，填入插件配置 `daily_target_origin`。

## LLM 工具

### `nest_status`

检查服务是否在线。

### `write_diary`

写入或更新某一天的小窝日记。

参数：

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

参数：

```text
source_path: 文件绝对路径
date: YYYY-MM-DD
original_name: 原始文件名，可空
```

归档成功后，把返回的媒体地址写进 `write_diary.media_refs`。

### `list_impressions` / `read_impression` / `write_impression`

管理人物印象。只有日记或对话提供稳定新证据时才调用 `write_impression`，不要每次写日记都强制更新。

## 内置 Skill

插件内置：

```text
skills/nest-diary/SKILL.md
```

AstrBot 会把插件 `skills/` 目录中的合法 Skill 纳入 Skill Manager。这个 Skill 负责规范 bot：

- 查记忆先搜索，不全量读取。
- 写日记必须有自拟标题、主观评价、情绪和检索线索。
- 通过工具调用小窝服务，不模拟人操作网页。
- 媒体先归档，再把媒体引用写进日记。
- 人物印象只在有稳定证据时更新。

## 定时提示

插件侧定时不是直接写数据库，而是按配置时间向目标会话发送提示词。bot 收到提示后，根据自身人设、当天上下文和小窝工具自主写入。

常用配置：

```text
scheduled_prompt_enabled: 是否启用定时循环
daily_write_enabled: 是否启用每日写日记提示
daily_write_time: 每日提示时间
daily_write_prompt: 到点发给 bot 的写日记提示词
reminder_enabled: 是否启用普通提醒
reminder_time: 普通提醒时间
impression_after_diary_prompt: 写完日记后的人物印象自检提示
```

## 数据边界

插件只保存配置，不保存大量日记和图片。正式数据由小窝本体服务保存：

```text
diary/       Markdown 日记
memory/      人物印象
media/       媒体文件
indexes/     SQLite 检索索引
settings/    网站与 token 设置
```
