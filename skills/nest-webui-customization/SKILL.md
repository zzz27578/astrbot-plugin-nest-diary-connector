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
  modules/
    diary/
    impressions/
    media/
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

## Framework vs Module Customization

Use framework-level customization for the shell of 小窝:

```text
framework/user_custom/webui/themes/<theme-id>/style.css
framework/user_custom/webui/static/
framework/user_custom/webui/templates/
```

Use module-level customization when a feature owns its own UI or data:

```text
framework/user_custom/webui/modules/<module-id>/
  module.json
  templates/
  static/
  notes.md
```

Examples:

```text
avatar-room
mood-timeline
memory-map
study-board
```

Keep module ids lowercase with hyphens.

## Module Data Rule

If a customization needs persistent data, do not hide it inside a frontend folder. Use a module data folder:

```text
modules/<module-id>/
  data/
  index/
  snapshots/
  module.json
```

For existing official modules:

```text
modules/diary/
modules/impressions/
modules/media/
```

Frontend files describe the room. Module data stores the memory.

## Real Controls Only

Every visible button, route, switch, form, or menu must be backed by a real route, tool, script, or saved setting.

Remove or hide unfinished controls. Do not create fake dashboards or pretend modules are functional before backend support exists.

## Safe Workflow

1. Call `nest_status` and locate `<data_dir>`.
2. Decide whether the change is framework-level or module-level.
3. Work under `framework/user_custom/webui/` for personal UI.
4. Work under `modules/<module-id>/` only when adding persistent module data.
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
