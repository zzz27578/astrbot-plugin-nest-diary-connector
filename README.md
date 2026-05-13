# AstrBot 小窝日记连接插件

仓库地址：<https://github.com/zzz27578/astrbot-plugin-nest-diary-connector>

这是小窝日记系统的 AstrBot 连接插件。它只负责给 bot 提供工具、skills 和小窝服务地址，不保存大量日记、图片或索引数据。

对应服务端项目：<https://github.com/zzz27578/nest-diary-service>

## 职责

- 保存小窝服务地址。
- 保存 bot 专属 API token。
- 提供 `/小窝状态` 连接检查指令。
- 封装写日记、搜日记、读日记、上传媒体等工具客户端。
- 提供内置 diary skills，规范 bot 使用小窝。
- 不保存大量日记和图片。

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

插件配置：

```text
service_url = http://nest-diary:28080
bot_api_token = 与小窝服务 NEST_BOT_API_TOKEN 相同
request_timeout_seconds = 30
```

## 当前指令

```text
/小窝状态
```

用于检查 AstrBot 是否能连到小窝服务。

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

## 推荐部署顺序

1. 先部署 `nest-diary-service`。
2. 确认服务端网页可通过密码登录。
3. 在 AstrBot 中安装本插件。
4. 填入服务地址和 `bot_api_token`。
5. 发送 `/小窝状态` 检查连接。
