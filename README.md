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
- 封装写日记、搜日记、读日记、上传媒体等工具客户端。
- 提供内置 diary skills，规范 bot 使用小窝。
- 不保存大量日记和图片。

## 当前功能

当前版本已经具备：

- 连接独立小窝服务。
- 通过 token 访问 bot 专属 API。
- 检查小窝服务在线状态。
- 封装日记写入客户端方法。
- 封装日记读取客户端方法。
- 封装日记搜索客户端方法。
- 封装媒体归档客户端方法。
- 内置日记写入、日记查找、日记归档 skills。

注意：当前插件已经有底层客户端和工具封装，但 AstrBot 的 LLM 工具注册层还会继续完善。现在最适合先测试连接和服务端能力。

## AstrBot 插件结构

本仓库按 AstrBot 标准插件形态组织：

```text
main.py
metadata.yaml
_conf_schema.json
requirements.txt
logo.png
skills/
  diary-write/SKILL.md
  diary-access/SKILL.md
  diary-archive/SKILL.md
astrbot_plugin_nest_diary_connector/
```

`logo.png` 为 1:1，256x256。

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

## 当前工具能力

插件已封装客户端方法：

```text
status
write_diary
read_diary
search_diary
attach_media
```

后续在 AstrBot 工具注册层接入后，bot 会通过这些工具操作小窝，而不是模仿人类登录网页。

## 内置 Skills

插件根目录提供：

```text
skills/diary-write/SKILL.md
skills/diary-access/SKILL.md
skills/diary-archive/SKILL.md
```

它们用于约束 bot：

- 写日记不能写成流水账。
- 查日记不能默认全量读取。
- 归档必须保留来源日期。
- 修改内容应通过小窝服务保留修订历史。

## 推荐部署顺序

1. 先部署 `nest-diary-service`。
2. 确认服务端网页可通过密码登录。
3. 在 AstrBot 中安装本插件。
4. 填入服务地址和 `bot_api_token`。
5. 发送 `/小窝状态` 检查连接。

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
