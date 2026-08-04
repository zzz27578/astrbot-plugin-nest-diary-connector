---
name: nest-webui-customization
description: Use this skill when the agent is asked to customize, redesign, theme, extend, or repair the Nest private home interface, including framework-level WebUI, themes, app shell, custom frontends, and module-specific UI. Use this for 小窝页面, WebUI, frontend style, themes, custom modules, buttons, layout, CSS, or update-safe personalization.
---

# Nest WebUI Customization

Customize 小窝 as a private home framework. Keep official plugin files updateable, and put personal designs in the data directory.

## Storage Roots

Always call `nest_status` first. Use its returned data directory as the root.

Default layout:

```text
<data_dir>/
  framework/
    settings/
    user_custom/
      webui/
        themes/
        modules/
        static/
        templates/
        extensions/
  modules/
    diary/
    impressions/
    media/
    extensions/
```

Legacy layouts may still contain `user_custom/webui` or `system/settings`. Prefer the `framework/` layout for new work.

## Core Rule

Official files are the fallback. Personalization belongs in:

```text
framework/user_custom/webui/
```

Do not edit built-in plugin UI files for personal customization unless the task explicitly says to maintain the official default:

```text
nest_diary_web/web_dist/
nest_diary_web/web/templates/
nest_diary_web/web/static/
```

## Built-In Appearance Modules

Version 0.5.15 ships three official global appearance modules. They are selectable in WebUI settings under `外观设置`; do not show these official global styles as ordinary module cards in `模块控制台`.

- `nest-paper-garden`: warm paper reading style for long diary browsing.
- `nest-glass-cabin`: bright glass interface for a cleaner modern home.
- `nest-night-atelier`: gentle dark workspace for night maintenance.

Selecting one global style should update `active_frontend_style` and keep only that global appearance enabled. Do not reintroduce retired industrial or tactical official themes. If a user wants a similar sharp style, create a custom theme with a new id under `framework/user_custom/webui/themes/`.

New WebUI pages should use shared shell variables and common classes (`--paper`, `--panel`, `--wash`, `--ink`, `--muted`, `.card`, `.topbar`, `.settings-collapse`, `.choice-card`, `.module-card`, etc.) so official appearances can theme them globally. Do not build four separate frontends for default, paper, glass, and night; add a narrow theme override only when a new component has a genuinely unique visual surface.

## Framework vs Module Customization

This skill covers the **shell** of 小窝: global appearance, themes, title, avatar, and shared components. If the task is to add a new page, a new sidebar entry, a new feature, or module data, that is module development — use the `nest-module-development` skill instead, which describes the `module.json` capability declaration and the `page.js` mount contract.

Use framework-level customization for the shell of 小窝:

```text
framework/user_custom/webui/themes/<theme-id>/style.css
framework/user_custom/webui/appearance/<appearance-id>/style.css
framework/user_custom/webui/static/
```

Global appearance packages are the one customization surface that is purely CSS: 小窝 concatenates the `style.css` of every enabled appearance package and serves it at `/theme.css`.

Simple identity changes such as the page title (`xxx的小窝`) and the top-left avatar should be done through WebUI settings first. Uploaded official avatar files are stored under `framework/assets/`; deeper visual redesigns belong in `framework/user_custom/webui/`.

Use module-level customization when a feature owns its own UI or data. A module directory holds its declaration and its frontend entry:

```text
modules/<module-id>/
  module.json      # 声明 runtime / nav / page / store
  page.js          # export mount(root, ctx)
  data/            # 持久数据
```

`framework/user_custom/webui/modules/<module-id>/` also works and is searched for frontend files, with the same `module.json` + `page.js` contract. Note that `templates/` and `static/` inside a module folder are **not** loaded by the SPA — server-rendered module templates are not part of the current contract. Use `page.js`.

Prefer extension packages when enhancing an existing module:

```text
framework/user_custom/webui/extensions/<extension-id>/
modules/extensions/<extension-id>/
```

Examples:

```text
avatar-room
mood-timeline
memory-map
study-board
diary-emotion-chart
impressions-radar
```

Keep module ids lowercase with hyphens.

## Official Module Rule

Official modules are updateable defaults. Do not directly edit official module code or bundled WebUI files for a user's personal customization:

```text
modules/diary/module.json
nest_diary_web/diary/
nest_diary_web/web_dist/
skills/nest-diary/SKILL.md
```

If the user wants to customize an official module:

1. If it is only visual, create or edit a theme under `framework/user_custom/webui/themes/`.
2. If it adds a view, create an extension under `framework/user_custom/webui/extensions/<extension-id>/`.
3. If it adds persistent data, store it under `modules/extensions/<extension-id>/`.
4. If it replaces the full module, create a new full module such as `modules/diary-plus/`, not a direct edit to `modules/diary/`.
5. If the change should become the official default, recommend a focused PR.

## Module Package Metadata

Every custom module or extension should include a `module.json` with clear identity and conflict metadata.

Full module example:

```json
{
  "id": "diary-plus",
  "type": "module",
  "feature_tags": ["diary-core"],
  "replaces": ["diary"],
  "conflicts_with": ["diary"]
}
```

Extension example:

```json
{
  "id": "diary-emotion-chart",
  "type": "extension",
  "target_modules": ["diary"],
  "feature_tags": ["diary-visualization"],
  "conflicts_with": []
}
```

If two enabled packages share a feature tag, the module console should warn about possible overlap. Do not forcibly disable either package unless the user explicitly asks.

Identity and conflict metadata is only half of a module manifest. The other half — `runtime`, `nav`, `page`, `store` — decides whether the module actually gets a sidebar entry and a page. See the `nest-module-development` skill for that contract.

## From-Link Module Installation

The WebUI module console supports installing a module package from a link. The package must be a zip file or a GitHub repository that contains `module.json`.

Expected package locations after install:

```text
modules/<module-id>/                    # full module with persistent data
modules/extensions/<extension-id>/      # extension package with persistent data
framework/user_custom/webui/appearance/<theme-id>/  # appearance package
```

Do not use an official module id (`diary`, `impressions`, `media`, `memos`, `webui`) or an official appearance id for a downloadable package. If a package replaces an official module, use a distinct id, set `replaces` and `conflicts_with`, and let the module console warn the user.

A package that declares `runtime: "python"` runs code inside the plugin process, so 小窝 will not auto-enable it after install even if the user checked that box. Tell the user they need to switch it on deliberately from the module card.

Custom modules, extensions and appearance packages can be uninstalled from their module detail page — either fully, or keeping `modules/<id>/data`. Both paths back up to `imports/module-uninstall-backups/` first. Official modules cannot be uninstalled, only switched off.

## Module Data Rule

If a customization needs persistent data, do not hide it inside a frontend folder. Use a module data folder:

```text
modules/<module-id>/
  data/
  index/
  snapshots/
  module.json
```

For extension packages:

```text
modules/extensions/<extension-id>/
  data/
  index/
  module.json
```

For existing official modules:

```text
modules/diary/
modules/impressions/
modules/media/
modules/memos/
```

Frontend files describe the room. Module data stores the memory. For a lightweight module the storage API is `ctx.store` from the page contract, which writes to `modules/<module-id>/data/store/`; never use `localStorage`, or the data will be invisible to export and backup.

## Real Controls Only

Every visible button, route, switch, form, or menu must be backed by a real route, tool, script, or saved setting.

Remove or hide unfinished controls. Do not create fake dashboards or pretend modules are functional before backend support exists.

## Safe Workflow

1. Call `nest_status` and locate `<data_dir>`.
2. Decide whether the change is framework-level (this skill) or a new module/page/feature (`nest-module-development`).
3. Work under `framework/user_custom/webui/` for personal shell UI and appearance.
4. Work under `modules/<module-id>/` when adding a module, its page entry, or its persistent data.
5. Keep existing form names, API paths, and route contracts unless backend code is updated too.
6. Test login, navigation, diary read/write, search, settings, import/export, and any changed module.
7. Record changes in `notes.md` for custom modules.

## Update Safety

Before major customization, back up:

```text
framework/
modules/
imports/
```

Plugin updates may replace official files. They must not overwrite `framework/user_custom/webui/`.

Layered exports should be used for sharing and moving custom work. Prefer exporting a custom module or extension package instead of exporting a full nest when sharing with others. Import should read `manifest.json` and merge according to the chosen strategy.

If a personal customization becomes broadly useful, recommend opening a PR to the official 小窝 plugin repository. Keep PRs focused:

- one framework improvement,
- one module improvement,
- or one theme/module contribution at a time.

## Response Style

When reporting customization work, include:

- whether it changed framework UI or a module UI,
- files changed under `framework/user_custom/webui/` or `modules/<module-id>/`,
- whether official plugin files were left untouched,
- what was tested.

Do not call a visual mockup complete if it cannot actually run.
