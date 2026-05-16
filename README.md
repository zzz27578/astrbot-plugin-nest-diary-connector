# AstrBot 小窝日记连接插件

仓库地址：<https://github.com/zzz27578/astrbot-plugin-nest-diary-connector>

这是小窝日记系统的 AstrBot 连接插件。它只负责给 bot 提供工具、skills 和小窝服务地址，不保存大量日记、图片或索引数据。

对应服务端项目：<https://github.com/zzz27578/nest-diary-service>

## 它是干什么的

这个插件不是日记本本体，而是 AstrBot 和小窝服务之间的连接层。

你可以把它理解成：

```text
AstrBot 插件 = bot 的门牌号和遥控器
Nest Diary 服务 = bot 真正的小窝
```

bot 不需要登录网页，也不需要模仿人类点按钮。插件会把 bot 的意图转成 API 请求，交给小窝服务完成写入、读取、搜索和媒体归档。

## 职责

- 保存小窝服务地址。
- 保存 bot 专属 API token。
- 提供 `/小窝状态` 连接检查指令。
- 封装写日记、搜日记、读日记、上传媒体、维护人物印象等工具客户端。
- 提供官方插件内置 `nest-diary` Skill，规范 bot 使用小窝。
- 不保存大量日记和图片。

## 当前功能

当前版本已经具备：

- 连接独立小窝服务。
- 通过 token 访问 bot 专属 API。
- 检查小窝服务在线状态。
- 注册 bot 可直接调用的日记写入工具。
- 注册 bot 可直接调用的日记读取工具。
- 注册 bot 可直接调用的日记搜索工具。
- 注册 bot 可直接调用的媒体归档工具。
- 注册 bot 可直接调用的人物印象工具。
- 内置 `nest-diary` Skill，会由 AstrBot 自动纳入 Skill Manager。

## AstrBot 插件结构

本仓库按 AstrBot 标准插件形态组织：

```text
main.py
metadata.yaml
_conf_schema.json
requirements.txt
logo.png
skills/
  nest-diary/
    SKILL.md
```

`logo.png` 为 1:1，256x256。

说明：`main.py` 是 AstrBot 官方插件入口文件名，本插件会保持这个文件。不要把插件入口改成 `nest_plugin.py`，否则 AstrBot 可能无法按标准方式发现插件。为了避免路径冲突，本仓库现在把实际逻辑也放在根目录 `main.py` 中，不再让入口文件反向导入同名 Python 包。

## 安装

按 AstrBot 标准插件安装方式安装本仓库。

推荐插件仓库地址：

```text
https://github.com/zzz27578/astrbot-plugin-nest-diary-connector
```

插件配置：

```text
service_url = http://nest-diary:28080
bot_api_token = 与小窝服务 NEST_BOT_API_TOKEN 相同
request_timeout_seconds = 30
```

如果 AstrBot 和小窝服务不在同一个 Docker 网络，`service_url` 可以改成：

```text
http://服务器IP:28080
```

或你的反代域名：

```text
https://nest.example.com
```

## 当前指令

```text
/小窝状态
```

用于检查 AstrBot 是否能连到小窝服务。

成功时类似：

```text
小窝在线：ok
```

失败时会返回连接错误，通常需要检查：

- `service_url` 是否能从 AstrBot 容器访问。
- `bot_api_token` 是否和服务端一致。
- 小窝服务是否已经启动。
- 防火墙或 Docker 网络是否拦截。

## Bot 可直接调用的工具

插件已经通过 AstrBot 的 LLM 工具机制注册以下工具，bot 可以在需要时直接调用，而不是自己写 Python 脚本或登录网页：

```text
nest_status
write_diary
read_diary
search_diary
attach_media
list_impressions
read_impression
write_impression
```

### `write_diary`

写入或更新某一天的小窝日记。

参数：

```text
date: YYYY-MM-DD
body: 日记正文，必须包含 bot 自己的评价、情绪和判断
mood: 情绪词，多个用逗号分隔，可空
tags: 标签，多个用逗号分隔，可空
people: 相关人物，多个用逗号分隔，可空
reason: 写入原因，例如 nightly_archive、manual_update
```

### `search_diary`

按关键词、日期、人名、事件或情绪线索搜索日记。默认返回 8 条，适合“想起某件事”时先查索引，不要全量读取。

参数：

```text
query: 搜索词
top_k: 返回条数，默认 8
```

### `read_diary`

读取指定日期日记。

参数：

```text
date: YYYY-MM-DD
```

### `attach_media`

把 AstrBot 容器内可访问的图片、语音或附件归档到某一天。

参数：

```text
source_path: 文件绝对路径
date: YYYY-MM-DD
original_name: 原始文件名，可空
```

### `list_impressions`

列出已经记录的人物印象摘要。

### `read_impression`

读取指定人物的长期印象。

参数：

```text
name: 人物名
```

### `write_impression`

写入或更新指定人物的长期印象。建议只在日记或对话提供稳定证据时调用，不要每次写日记都强制更新。

参数：

```text
name: 人物名
summary: 对这个人的稳定总结
traits: 性格特征，多个用逗号分隔，可空
interests: 兴趣爱好，多个用逗号分隔，可空
preferences: 偏好或相处方式，多个用逗号分隔，可空
relationship: 与 bot 或项目的关系，可空
evidence_dates: 支撑这次更新的日记日期，多个用逗号分隔，可空
confidence: 可信度，1 到 5
notes: 额外备注，可空
```

## 内置 Skill

插件根目录提供官方支持的插件内置 Skill：

```text
skills/nest-diary/SKILL.md
```

AstrBot 官方文档说明：插件可以提供 `skills/` 目录。插件加载后，里面合法的 Skill 会自动纳入 Skill Manager，并在 WebUI Skills 页面显示来源为插件。

```text
data/plugins/astrbot_plugin_nest_diary_connector/skills/nest-diary/SKILL.md
```

这个 Skill 用于约束 bot：

- 写日记不能写成流水账。
- 查日记不能默认全量读取。
- 归档必须保留来源日期。
- 修改内容应通过小窝服务保留修订历史。
- 人物印象必须基于稳定证据，可选更新，不要制造噪音记忆。

注意：本插件的 Skill 不会禁用 LLM Tools。Skill 负责告诉 bot “什么时候、怎样使用小窝”，真正读写仍然调用 `write_diary`、`search_diary`、`read_diary`、`attach_media`、`write_impression` 等工具。是否启用这个 Skill，请在 AstrBot 的 Skills 页面里管理。

## 推荐部署顺序

1. 先部署 `nest-diary-service`。
2. 确认服务端网页可通过密码登录。
3. 在 AstrBot 中安装本插件。
4. 填入服务地址和 `bot_api_token`。
5. 发送 `/小窝状态` 检查连接。
6. 让 bot 试着调用 `nest_status` 或 `search_diary`，确认原生工具可用。

## 和服务端如何绑定

服务端 `.env` 里设置：

```text
NEST_BOT_API_TOKEN=一串很长的token
```

插件配置里填同一串：

```text
bot_api_token=同一串token
```

服务端地址填入插件：

```text
service_url=http://nest-diary:28080
```

绑定成功的标准是 `/小窝状态` 能返回在线。

## 数据在哪里

插件不保存小窝数据。真正的数据在服务端：

```text
nest-diary-service/data/
```

包括：

```text
diary/       Markdown 日记
media/       图片、语音、附件
index/       SQLite 搜索索引
revisions/   修订快照
```
