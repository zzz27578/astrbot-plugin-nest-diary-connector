---
name: nest-webui-customization
description: Use this skill when the agent is asked to customize, redesign, theme, extend, or repair the Nest WebUI/private home interface. Trigger on requests about 小窝页面, WebUI, frontend style, themes, custom modules, templates, buttons, layout, CSS, visual design, or preserving user-made customization during updates. Modify user_custom files only; do not edit built-in plugin templates unless explicitly maintaining the official default module.
---

# Nest WebUI Customization

Customize the Nest WebUI as a private home interface while preserving the official plugin as an updateable base.

## Core Rule

Official files are the fallback. User-made design belongs in the data directory.

Do not edit these built-in files for personal customization:

```text
nest_diary_web/web/templates/
nest_diary_web/web/static/
```

Edit or create files under the active data directory instead:

```text
user_custom/webui/templates/
user_custom/webui/static/
user_custom/webui/themes/
user_custom/webui/modules/
```

The WebUI loads templates in this order:

1. `user_custom/webui/templates/<template name>`
2. built-in `nest_diary_web/web/templates/<template name>`

Custom static assets are served from:

```text
/custom-static/<file>
```

Built-in static assets remain available from:

```text
/static/<file>
```

## First Step

Call `nest_status` before planning a customization. Use the returned data directory as the root for user customization.

If `nest_status` is unavailable, ask for the active Nest data directory. Do not guess a production path when writing files.

## What To Customize

Use template overrides when changing page structure:

```text
user_custom/webui/templates/dashboard.html
user_custom/webui/templates/diary.html
user_custom/webui/templates/write.html
user_custom/webui/templates/search.html
user_custom/webui/templates/media.html
user_custom/webui/templates/impressions.html
user_custom/webui/templates/settings.html
user_custom/webui/templates/login.html
user_custom/webui/templates/_shell.html
```

Use custom static files for style, images, scripts, and fonts:

```text
user_custom/webui/static/custom.css
user_custom/webui/static/custom.js
user_custom/webui/static/images/
user_custom/webui/static/fonts/
```

Custom templates can reference these assets with:

```html
<link rel="stylesheet" href="/custom-static/custom.css">
<script src="/custom-static/custom.js"></script>
```

## Design Constraints

Build the actual admin experience, not a landing page.

Every visible button or navigation item must do one of these:

- link to a real route that exists,
- submit a real form that exists,
- call a script that is included in custom static files,
- clearly be removed until its feature exists.

Do not add fake controls, fake settings, fake routes, or placeholder dashboards that imply a feature works.

## Safe Workflow

1. Read the built-in template that matches the page being customized.
2. Copy only the template that needs customization into `user_custom/webui/templates/`.
3. Keep existing form field names, route paths, and required variables unless the backend is updated too.
4. Put new CSS, images, and scripts under `user_custom/webui/static/`.
5. Reference custom assets through `/custom-static/...`.
6. Test login, navigation, forms, diary reading, diary writing, search, settings, import/export, and version actions if those pages changed.
7. If a change breaks rendering, remove or fix the custom override; the built-in fallback will work when the custom file is absent.

## Template Compatibility

Preserve Jinja variables that the built-in route expects. Common variables include:

- `active`
- `saved`
- `error`
- `entries`
- `selected_entry`
- `archive`
- `manifests`
- `people`
- `selected_person`
- `settings`
- `security`
- `runtime_settings`
- `version_message`

When uncertain, keep the original variable names and form fields from the built-in template.

## Custom Modules

Use `user_custom/webui/modules/<module-id>/` for experimental features, visual widgets, or bot-made additions that should survive plugin updates.

Recommended module layout:

```text
user_custom/webui/modules/<module-id>/
  module.json
  templates/
  static/
  notes.md
```

Keep module ids lowercase with hyphens, for example:

```text
mood-timeline
memory-map
avatar-room
```

Module notes should record:

- what the module changes,
- which templates or assets it depends on,
- whether backend support is required,
- how to disable it safely.

## Update Safety

Before large custom changes, create a backup of:

```text
user_custom/
system/settings/
modules/
```

Plugin updates may replace built-in templates and static files. They must not overwrite `user_custom/`. If a customized page stops working after an update, compare the matching built-in template with the custom override and merge only the required route/form changes.

## When Backend Work Is Needed

Frontend-only customization is enough for:

- layout changes,
- colors and typography,
- page composition,
- hiding or reordering existing controls,
- adding visual-only widgets based on existing page data.

Backend/plugin work is needed for:

- new persistent data,
- new routes,
- new forms that save data,
- new LLM tools,
- new scheduled actions,
- new external API behavior.

If backend work is needed, state that clearly before editing templates.

## Response Style

When reporting customization work, include:

- files changed under `user_custom`,
- routes affected,
- whether built-in plugin files were left untouched,
- what was tested.

Do not describe customization as complete if it was only a visual mockup.
