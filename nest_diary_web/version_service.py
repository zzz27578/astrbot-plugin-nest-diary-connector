from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen


@dataclass(frozen=True)
class VersionCheckResult:
    current: str
    latest: str
    update_available: bool
    source: str


@dataclass(frozen=True)
class VersionUpdateResult:
    ok: bool
    message: str
    output: str = ""


class VersionService:
    def __init__(
        self,
        current_version: str,
        repo_root: Path,
        latest_url: str = "https://raw.githubusercontent.com/zzz27578/astrbot-plugin-nest-diary-connector/master/metadata.yaml",
        enable_self_update: bool = False,
    ):
        self.current_version = current_version
        self.repo_root = Path(repo_root)
        self.latest_url = latest_url
        self.enable_self_update = enable_self_update

    def check_latest(self) -> VersionCheckResult:
        with urlopen(self.latest_url, timeout=8) as response:
            text = response.read().decode("utf-8")
        latest = self._parse_version(text)
        return VersionCheckResult(
            current=self.current_version,
            latest=latest,
            update_available=self._version_tuple(latest) > self._version_tuple(self.current_version),
            source=self.latest_url,
        )

    def update(self) -> VersionUpdateResult:
        if not self.enable_self_update:
            return VersionUpdateResult(
                ok=False,
                message="当前未启用自更新。插件更新请在 AstrBot 插件管理中拉取新版；如需 git 自更新，请设置 NEST_ENABLE_SELF_UPDATE=true。",
            )
        if not (self.repo_root / ".git").exists():
            return VersionUpdateResult(
                ok=False,
                message="当前运行目录不是 git 仓库，不能执行 git pull。请使用 AstrBot 插件管理更新。",
            )
        result = subprocess.run(
            ["git", "-C", str(self.repo_root), "pull", "--ff-only"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        output = (result.stdout + "\n" + result.stderr).strip()
        if result.returncode != 0:
            return VersionUpdateResult(ok=False, message="git pull 更新失败。", output=output)
        return VersionUpdateResult(ok=True, message="已执行 git pull。请重启小窝服务让新代码生效。", output=output)

    def _parse_version(self, text: str) -> str:
        match = re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
        if not match:
            match = re.search(r'^version\s*:\s*v?([^\s]+)', text, flags=re.MULTILINE)
        if not match:
            raise ValueError("Cannot find version in remote version file")
        return match.group(1)

    def _version_tuple(self, value: str) -> tuple[int, ...]:
        return tuple(int(part) for part in re.findall(r"\d+", value))
