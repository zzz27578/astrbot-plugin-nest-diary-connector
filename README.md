# AstrBot 小窝插件

版本：`0.3.8`

小窝是给 bot 使用的私有空间框架。日记只是第一个官方模块，不再把整个插件定义成“小窝日记”。

默认 embedded 模式下，插件自己提供：

- 小窝 WebUI
- bot 原生工具
- 框架级设置和管理员密码
- 小窝标题与左上角头像个性化
- 模块化数据目录
- 日记、媒体、人物印象等官方模块
- 自定义前端和自定义模块目录
- 内置 skills
- 定时提示，让 bot 自主调用工具

## 默认运行方式

插件配置保持：

```text
nest_mode=embedded
enable_webui=true
web_port=28080
admin_password=12345678
```

启动后访问：

```text
http://服务器IP:28080
```

默认数据根目录：

```text
/AstrBot/data/plugin_data/astrbot_plugin_nest_diary_connector
```

本地开发时，如果没有 `/AstrBot`，会回退到插件目录下的 `data/`。

## 正式数据结构

```text
data/
  framework/
    settings/
      security.json
      service-ui.json
    cache/
    logs/
    user_custom/
      webui/
        themes/
        modules/
        static/
        templates/
  modules/
    diary/
      entries/
      index/
      snapshots/
      drafts/
    impressions/
      people/
      topics/
      events/
    media/
      blobs/
      variants/
      by-date/
  imports/
```

规则：

- `framework/` 是小窝框架本体的数据区，放管理员密码、WebUI 设置、个性化前端、框架缓存等。
- `modules/<module-id>/` 是功能模块自己的数据区。日记、媒体、人物印象都按模块隔离。
- `framework/user_custom/webui/` 是用户或 bot 自定义小窝外观、主题和前端模块的位置，官方更新不应覆盖这里。
- 旧目录 `system/settings/`、`user_custom/`、`diary/`、`memory/`、`media/` 会在启动时复制到新布局中，保持兼容。

## WebUI

默认 App Shell 位于：

```text
nest_diary_web/web_dist/
```

兼容模板仍保留在：

```text
nest_diary_web/web/templates/
nest_diary_web/web/static/
```

个性化前端请放到数据目录：

```text
framework/user_custom/webui/
```

主题建议：

```text
framework/user_custom/webui/themes/<theme-id>/style.css
```

自定义模块建议：

```text
framework/user_custom/webui/modules/<module-id>/
  module.json
  templates/
  static/
  notes.md
```

拓展包建议：

```text
framework/user_custom/webui/extensions/<extension-id>/
modules/extensions/<extension-id>/
```

如果个性化内容做得通用，建议整理成 PR 提交到本项目，而不是长期只保存在本地。

## 模块规范

小窝把扩展分成两类：

- 完整模块：提供一整套功能，例如 `diary-plus`、`memory-map`。
- 拓展包：挂在某个模块旁边增强能力，例如 `diary-emotion-chart`。

每个完整功能模块都应该有独立目录：

```text
modules/<module-id>/
  module.json
  data/
  index/
  snapshots/
```

每个拓展包使用独立目录：

```text
modules/extensions/<extension-id>/
framework/user_custom/webui/extensions/<extension-id>/
```

`module.json` 应声明：

```json
{
  "id": "diary-plus",
  "type": "module",
  "feature_tags": ["diary-core"],
  "replaces": ["diary"],
  "conflicts_with": ["diary"]
}
```

拓展包示例：

```json
{
  "id": "diary-emotion-chart",
  "type": "extension",
  "target_modules": ["diary"],
  "feature_tags": ["diary-visualization"],
  "conflicts_with": []
}
```

模块约束：

- 模块只读写自己的数据目录。
- 跨模块引用使用稳定 ID、日期、URL 或工具返回值，不直接偷改别的模块文件。
- 需要被 bot 调用的能力必须注册为工具。
- 需要被网页使用的能力必须提供真实 API 或真实前端脚本，不做假按钮。
- 重要数据写入前尽量保留快照或可追溯记录。
- 不建议直接修改官方模块代码。若要替代官方日记模块，请创建 `diary-plus` 这类完整模块并声明 `replaces` / `conflicts_with`。
- 优先做拓展包；只有需要重构整套功能时才做完整模块。

## 模块控制台

设置页的模块控制台会展示：

- 官方模块
- 自定义完整模块
- 拓展包
- 功能标签 `feature_tags`
- 替代关系 `replaces`
- 显式冲突 `conflicts_with`

如果两个已启用包具有相同功能标签，或声明互相替代/冲突，小窝只提示风险，不强制禁用。用户可以同时启用，但需要知道可能出现入口重复、工具重复或数据口径不一致。

## 分层导入导出

导出支持选择范围：

- 完整备份
- 日记模块
- 人物印象
- 媒体归档
- 个性化前端
- 安全配置
- 指定自定义模块
- 指定拓展包

导出包包含 `manifest.json`，用于声明 `package_type`、`module_id`、版本和创建时间。导入时会读取 manifest 并按位置合并。

导入策略：

- 安全合并：已有文件跳过。
- 覆盖合并：已有文件先备份到 `imports/import-backups/`，再覆盖。

默认不导出 `framework/settings/security.json`。只有用户勾选“包含管理员密码/API Key”或选择“安全配置”时才导出敏感配置。

## 日记模块

日记数据路径：

```text
modules/diary/entries/YYYY/MM/YYYY-MM-DD.md
modules/diary/index/
modules/diary/snapshots/
```

检索机制：

- 默认使用本地 SQLite 索引，不需要外部 API。
- 优先使用 SQLite FTS5 + BM25 排序。
- 环境不支持 FTS5 时自动降级为本地 LIKE 检索。
- `search_diary` 只返回日期、标题、命中片段、标签、人物和检索后端，避免整本日记滚入上下文。
- `read_diary` 只在需要读取某一天全文时使用。

## LLM 工具

- `nest_status`
- `write_diary`
- `search_diary`
- `read_diary`
- `attach_media`
- `list_impressions`
- `read_impression`
- `write_impression`
- `delete_impression`

`write_diary` 必须提供 bot 自拟标题：

```text
title: 用一句话概括当天记忆，不要直接使用日期。
```

## 常用命令

```text
/小窝状态
```

查看小窝模式、日记模块状态、WebUI 地址和数据目录。

```text
/小窝绑定提醒
```

在目标会话发送，复制返回的 `unified_msg_origin`，填入插件配置 `daily_target_origin`。

## API Key

embedded 模式下，插件内部工具不需要 API Key。

WebUI 设置里的外部 API Key 只给这些场景使用：

- MCP
- 外部脚本
- 第三方网页
- 其他 bot
- 兼容 standalone 模式

## Skills

内置 skills：

```text
skills/nest-diary/SKILL.md
skills/nest-webui-customization/SKILL.md
```

`nest-diary` 约束 bot 使用工具操作日记模块：先搜索再读取，写日记要有标题、主观评价、情绪和检索线索；人物印象支持名字、身份、爱好、兴趣、喜爱程度、总结评价、特殊点评和备注，只在有稳定证据时更新。

`nest-webui-customization` 约束 bot 做小窝个性化：区分框架前端和模块前端，只改 `framework/user_custom/webui/` 或对应模块目录；按钮、路由、表单必须对应真实功能；通用改进建议提交 PR。

## Plugin Page

AstrBot Dashboard 内的插件页面位于：

```text
pages/nest/
```

它只作为状态入口和门牌号。真正的小窝 WebUI 由内置服务提供，并使用独立管理员密码登录。
