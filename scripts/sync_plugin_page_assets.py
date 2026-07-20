from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "nest_diary_web" / "web_dist" / "assets"
TARGET = ROOT / "pages" / "nest" / "assets"


def main() -> None:
    if not SOURCE.is_dir():
        raise SystemExit(f"Missing WebUI asset directory: {SOURCE}")
    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(SOURCE, TARGET)
    print(f"Synced plugin page assets from {SOURCE} to {TARGET}")


if __name__ == "__main__":
    main()