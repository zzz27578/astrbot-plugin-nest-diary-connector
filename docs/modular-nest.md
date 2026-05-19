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
- 拓展包数据 `modules/extensions/<extension-id>/`

模块之间不能直接互相改文件。需要协作时，通过工具、API、稳定 ID 或引用字段连接。

## 框架配置与插件配置

插件配置负责 AstrBot 侧能力：

- 运行模式：`embedded` 或 `standalone`
- 是否启用 WebUI
- WebUI 监听地址和端口
- 数据根目录
- 后台定时任务使用哪个会话作为上下文
- 日记模块是否启用

小窝 WebUI 设置负责小窝自身：

- 管理员密码
- 可选外部 API Key
- 前端主题
- 自定义模块显示
- 人物印象模块、自动识别、写入程度和更新策略
- 外观模块启用状态与冲突提示
- 导入、导出、备份
- 版本检测和更新

## 模块规范

完整模块建议提供：

```text
modules/<module-id>/
  module.json
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

`module.json` 声明：

- 模块 id、名称、版本
- 类型：`module` 或 `extension`
- 功能标签：`feature_tags`
- 目标模块：`target_modules`，拓展包使用
- 替代关系：`replaces`
- 冲突声明：`conflicts_with`
- 数据目录
- 暴露工具
- Web 路由
- 依赖模块
- schema 版本

推荐优先做拓展包。只有确实要替代整套能力时，才创建完整模块并声明 `replaces` / `conflicts_with`。例如重构日记模块时，不要直接修改官方 `diary`，而是创建 `diary-plus`。

模块控制台只提示完整模块冲突，不强制禁用。用户可以保留多个完整模块，但需要承担入口重复、工具重复或数据口径不一致的风险。拓展包用于补充增强，不因功能标签重叠被限制。

人物印象是独立官方模块。日记保存后不会直接因为 `people` 字段出现新称呼就自动建档；是否交给 bot 自动识别、是否允许新建候选档、写入程度和更新策略由 WebUI 的“模块管理 → 人物印象”详情页控制。

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
framework/user_custom/webui/templates/
```

官方更新只更新插件默认文件，不覆盖 `framework/user_custom/webui/`。

外观模块可以声明 `type: "appearance"` 和 `appearance_mode`。`appearance_mode: "global"` 表示全局模块，官方默认外观是 `nest-tactical`，首次没有外观选择时自动启用。全局模块建议只启用一个；其他值按补充拓展处理，可以多个同时启用。多个全局模块同时开启时，WebUI 会显示红色冲突提示。

如果自定义前端或模块对其他人也有价值，建议整理成 PR 提交到项目仓库。PR 应该聚焦，不要一次提交过多无关改动。

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
