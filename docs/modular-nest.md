# 小窝模块化框架约定

小窝以 AstrBot 插件为统一入口。插件负责启动框架、注册工具、提供 WebUI、加载 skills，并管理官方模块。日记只是一个模块，不是小窝本体。

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

模块之间不能直接互相改文件。需要协作时，通过工具、API、稳定 ID 或引用字段连接。

## 框架配置与插件配置

插件配置负责 AstrBot 侧能力：

- 运行模式：`embedded` 或 `standalone`
- 是否启用 WebUI
- WebUI 监听地址和端口
- 数据根目录
- 定时提示发送到哪个会话
- 日记模块是否启用

小窝 WebUI 设置负责小窝自身：

- 管理员密码
- 可选外部 API Key
- 前端主题
- 自定义模块显示
- 导入、导出、备份
- 版本检测和更新

## 模块规范

每个模块建议提供：

```text
modules/<module-id>/
  module.json
  data/
  index/
  snapshots/
```

`module.json` 声明：

- 模块 id、名称、版本
- 数据目录
- 暴露工具
- Web 路由
- 依赖模块
- schema 版本

## 自定义前端

用户或 bot 自己改的小窝外观放在：

```text
framework/user_custom/webui/
```

推荐结构：

```text
framework/user_custom/webui/themes/<theme-id>/style.css
framework/user_custom/webui/modules/<module-id>/
framework/user_custom/webui/static/
framework/user_custom/webui/templates/
```

官方更新只更新插件默认文件，不覆盖 `framework/user_custom/webui/`。

如果自定义前端或模块对其他人也有价值，建议整理成 PR 提交到项目仓库。PR 应该聚焦，不要一次提交过多无关改动。

## API Key

embedded 模式下，插件内部工具不需要 API Key。

API Key 只用于外部扩展，例如 MCP、脚本、第三方网页、其他 bot 或 standalone 兼容模式。
