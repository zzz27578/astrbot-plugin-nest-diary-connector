"""小窝模块契约层。

这个文件是"官方模块有哪些"和"模块能声明什么能力"的唯一权威来源。
所有发现、安装、卸载、路由挂载逻辑都必须从这里取值，不要再散落硬编码。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .paths import safe_package_id

# ---------------------------------------------------------------------------
# 官方身份注册表
# ---------------------------------------------------------------------------

#: 官方功能模块 ID。链接安装不允许占用这些 ID。
OFFICIAL_MODULE_IDS: tuple[str, ...] = ("diary", "impressions", "media", "memos", "webui")

#: 官方内置全局外观 ID。
OFFICIAL_APPEARANCE_IDS: tuple[str, ...] = (
    "nest-paper-garden",
    "nest-glass-cabin",
    "nest-night-atelier",
)

#: modules/ 下不属于"自定义模块"的保留目录名。
RESERVED_MODULE_DIR_NAMES: frozenset[str] = frozenset({*OFFICIAL_MODULE_IDS, "extensions", "archive"})

#: 侧边栏内置图标名。模块 nav.icon 只能取这些值，或指向自带资源文件。
BUILTIN_NAV_ICONS: frozenset[str] = frozenset(
    {
        "access",
        "appearance",
        "backup",
        "diary",
        "home",
        "impressions",
        "media",
        "memos",
        "modules",
        "search",
        "settings",
        "webui",
    }
)

#: 模块自带前端资源允许的扩展名。
ALLOWED_ASSET_SUFFIXES: frozenset[str] = frozenset(
    {".js", ".mjs", ".css", ".json", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".woff2", ".html", ".txt", ".md"}
)

#: 模块声明的运行档位。webui = 只有前端与通用存储；python = 自带后端代码。
RUNTIME_WEBUI = "webui"
RUNTIME_PYTHON = "python"
KNOWN_RUNTIMES: frozenset[str] = frozenset({RUNTIME_WEBUI, RUNTIME_PYTHON})

#: 单个模块存储文档的体积上限。
STORE_MAX_BYTES = 1024 * 1024
#: 单个模块允许的存储键数量上限。
STORE_MAX_KEYS = 64

MODULE_ROUTE_PREFIX = "/m"
MODULE_ASSET_PREFIX = "/api/ui/module-assets"
MODULE_API_PREFIX = "/api/ui/modules"


def is_official_id(module_id: str) -> bool:
    return module_id in OFFICIAL_MODULE_IDS or module_id in OFFICIAL_APPEARANCE_IDS


def module_route(module_id: str) -> str:
    return f"{MODULE_ROUTE_PREFIX}/{module_id}"


def module_asset_base(module_id: str) -> str:
    return f"{MODULE_ASSET_PREFIX}/{module_id}"


# ---------------------------------------------------------------------------
# 能力声明解析
# ---------------------------------------------------------------------------


def _clean_text(value: Any, fallback: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or fallback


def _relative_asset_path(value: Any) -> str:
    """把声明里的资源路径收成安全的相对路径，拒绝越界与绝对路径。"""
    raw = _clean_text(value).replace("\\", "/").lstrip("/")
    if not raw:
        return ""
    parts = [part for part in raw.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        return ""
    return "/".join(parts)


def normalize_nav(raw: Any, module_id: str, module_name: str, errors: list[str]) -> dict | None:
    """解析侧边栏声明。没有声明就没有入口，这是缺省即关闭。"""
    if raw is None or raw is False:
        return None
    if raw is True:
        raw = {}
    if not isinstance(raw, dict):
        errors.append("nav 声明必须是对象或布尔值。")
        return None
    if raw.get("enabled") is False:
        return None

    icon = _clean_text(raw.get("icon"), "modules")
    icon_asset = ""
    if icon not in BUILTIN_NAV_ICONS:
        icon_asset = _relative_asset_path(icon)
        if not icon_asset:
            errors.append(f"nav.icon 既不是内置图标也不是合法资源路径：{icon}")
        icon = ""

    order = raw.get("order", 500)
    try:
        order = int(order)
    except (TypeError, ValueError):
        order = 500
    order = max(0, min(999, order))

    return {
        "label": _clean_text(raw.get("label"), module_name or module_id),
        "icon": icon,
        "icon_asset": icon_asset,
        "order": order,
        "route": module_route(module_id),
    }


def normalize_page(raw: Any, module_id: str, errors: list[str]) -> dict | None:
    """解析页面声明。entry 指向模块自带的 ES module 文件。"""
    if raw is None or raw is False:
        return None
    if raw is True:
        raw = {}
    if isinstance(raw, str):
        raw = {"entry": raw}
    if not isinstance(raw, dict):
        errors.append("page 声明必须是对象或字符串。")
        return None
    if raw.get("enabled") is False:
        return None

    entry = _relative_asset_path(raw.get("entry") or "page.js")
    if not entry:
        errors.append("page.entry 不是合法的相对路径。")
        return None
    if Path(entry).suffix.lower() not in {".js", ".mjs"}:
        errors.append("page.entry 必须是 .js 或 .mjs 文件。")
        return None

    return {
        "entry": entry,
        "export": _clean_text(raw.get("export"), "mount"),
        "title": _clean_text(raw.get("title")),
    }


def normalize_store(raw: Any, errors: list[str]) -> dict | None:
    """解析通用存储声明。轻量模块靠它落地数据，不需要写后端。"""
    if raw is None or raw is False:
        return None
    if raw is True:
        raw = {}
    if not isinstance(raw, dict):
        errors.append("store 声明必须是对象或布尔值。")
        return None
    if raw.get("enabled") is False:
        return None

    max_bytes = raw.get("max_bytes", STORE_MAX_BYTES)
    try:
        max_bytes = int(max_bytes)
    except (TypeError, ValueError):
        max_bytes = STORE_MAX_BYTES
    return {"max_bytes": max(1024, min(STORE_MAX_BYTES, max_bytes))}


def normalize_capabilities(manifest: dict) -> dict:
    """把 manifest 里的能力声明收成统一结构，并记录声明错误。

    返回结构会挂在 manifest 的 ``capabilities`` 上，前端据此决定：
    要不要侧边栏入口、要不要页面、页面从哪加载。
    """
    module_id = safe_package_id(str(manifest.get("id") or ""), "module")
    module_name = _clean_text(manifest.get("name"), module_id)
    errors: list[str] = []

    runtime = _clean_text(manifest.get("runtime"), RUNTIME_WEBUI).lower()
    if runtime not in KNOWN_RUNTIMES:
        errors.append(f"runtime 只支持 {RUNTIME_WEBUI} 或 {RUNTIME_PYTHON}，收到 {runtime}。")
        runtime = RUNTIME_WEBUI

    page = normalize_page(manifest.get("page"), module_id, errors)
    nav = normalize_nav(manifest.get("nav"), module_id, module_name, errors)
    store = normalize_store(manifest.get("store"), errors)

    if nav and not page:
        errors.append("声明了侧边栏入口但没有声明 page，入口不会被渲染。")
        nav = None

    return {
        "runtime": runtime,
        "nav": nav,
        "page": page,
        "store": store,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# 资源根解析
# ---------------------------------------------------------------------------


def asset_roots(manifest: dict) -> list[Path]:
    """模块自带前端文件的候选根目录，按优先级排列。"""
    roots: list[Path] = []
    for key in ("frontend_path", "data_path"):
        value = _clean_text(manifest.get(key))
        if not value:
            continue
        base = Path(value)
        roots.append(base)
        roots.append(base / "webui")
    seen: set[str] = set()
    unique: list[Path] = []
    for root in roots:
        marker = str(root)
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(root)
    return unique


def resolve_asset(manifest: dict, relative_path: str) -> Path | None:
    """在模块的资源根里解析一个相对路径，越界或类型不允许时返回 None。"""
    safe_relative = _relative_asset_path(relative_path)
    if not safe_relative:
        return None
    if Path(safe_relative).suffix.lower() not in ALLOWED_ASSET_SUFFIXES:
        return None
    for root in asset_roots(manifest):
        if not root.is_dir():
            continue
        try:
            root_real = root.resolve(strict=True)
            candidate = (root_real / safe_relative).resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if candidate.is_file() and root_real in candidate.parents:
            return candidate
    return None


def verify_page_entry(manifest: dict) -> str:
    """校验声明的 page.entry 真实存在。返回错误描述，通过则返回空串。"""
    capabilities = manifest.get("capabilities") or {}
    page = capabilities.get("page")
    if not page:
        return ""
    if resolve_asset(manifest, page.get("entry", "")) is None:
        return f"声明的页面文件不存在或类型不被允许：{page.get('entry', '')}"
    return ""


# ---------------------------------------------------------------------------
# 侧边栏入口
# ---------------------------------------------------------------------------


def nav_entry_for(manifest: dict) -> dict | None:
    """把一个已通过校验的模块 manifest 转成前端可用的侧边栏入口。

    返回 None 表示这个模块不该有入口：没声明 nav、没声明 page，
    或者声明没通过框架验真（``_attach_capabilities`` 已经把 nav 清掉了）。
    """
    capabilities = manifest.get("capabilities") or {}
    nav = capabilities.get("nav")
    page = capabilities.get("page")
    if not nav or not page:
        return None

    module_id = manifest.get("id", "")
    asset_base = manifest.get("asset_base") or module_asset_base(module_id)
    icon_asset = nav.get("icon_asset") or ""
    return {
        "id": module_id,
        "label": nav.get("label") or manifest.get("name") or module_id,
        "icon": nav.get("icon") or "",
        "icon_url": f"{asset_base}/{icon_asset}" if icon_asset else "",
        "order": nav.get("order", 500),
        "route": nav.get("route") or module_route(module_id),
        "page_url": f"{asset_base}/{page['entry']}",
        "page_export": page.get("export", "mount"),
        "title": page.get("title") or manifest.get("name") or module_id,
        "store": bool(capabilities.get("store")),
        "asset_base": asset_base,
    }


def collect_nav_entries(groups: list[tuple[list[dict], list[str]]], hidden_ids: list[str] | None = None) -> list[dict]:
    """按 (模块列表, 已启用 ID 列表) 分组算出全部自定义侧边栏入口。

    三层把关在这里汇合：模块要声明 nav 与 page（第一层），要被用户启用
    （第二层），声明的页面文件要真实存在（第三层，在发现阶段验过）。
    ``hidden_ids`` 是用户对已启用模块单独隐藏入口的选择。
    """
    hidden = set(hidden_ids or [])
    entries: list[dict] = []
    for items, enabled_ids in groups:
        allowed = set(enabled_ids or [])
        for item in items:
            module_id = item.get("id", "")
            if module_id not in allowed or module_id in hidden:
                continue
            entry = nav_entry_for(item)
            if entry:
                entries.append(entry)
    return sorted(entries, key=lambda entry: (entry["order"], entry["id"]))

