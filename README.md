# AstrBot 小窝日记连接插件

这是小窝日记系统的 AstrBot 连接插件。

它只负责给 bot 提供工具、skills 和小窝服务地址，不保存大量日记、图片或索引数据。

## 职责

- 保存小窝服务地址。
- 保存 bot 专属 API token。
- 提供小窝状态检查指令。
- 后续封装写日记、搜日记、读日记、上传媒体、归档等工具。
- 提供内置 diary skills，规范 bot 使用小窝。

## 配套服务

需要单独部署 `nest-diary-service`。插件通过 HTTP API 调用服务。

## 安装

把 `astrbot_plugin_nest_diary_connector` 放入 AstrBot 插件目录，或按 AstrBot 标准插件安装方式安装本仓库。

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

## 图片规范

插件图标位于：

```text
astrbot_plugin_nest_diary_connector/logo.png
```

规格：1:1，256x256。

## 设计边界

插件不保存日记正文、图片、语音、附件、搜索索引和归档结果。  
这些数据全部属于 `nest-diary-service`。
