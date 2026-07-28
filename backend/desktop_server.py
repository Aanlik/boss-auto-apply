from __future__ import annotations

import os
import platform
import sys
from pathlib import Path


def _resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def _default_desktop_data_dir() -> Path:
    configured = os.environ.get("BOSS_WORKBENCH_DATA_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    system = platform.system().lower()
    if system == "darwin":
        return Path.home() / "Library" / "Application Support" / "BOSS Workbench" / "data"
    if system == "windows":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "BOSS Workbench" / "data"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "boss-workbench" / "data"


def configure_desktop_environment() -> None:
    root = _resource_root()
    frontend_dist = root / "frontend" / "dist"
    os.environ.setdefault("BOSS_WORKBENCH_FRONTEND_DIST", str(frontend_dist))
    os.environ.setdefault("BOSS_WORKBENCH_DATA_DIR", str(_default_desktop_data_dir()))
    os.environ.setdefault("BOSS_WORKBENCH_DESKTOP", "1")
    Path(os.environ["BOSS_WORKBENCH_DATA_DIR"]).mkdir(parents=True, exist_ok=True)


def main() -> None:
    configure_desktop_environment()
    import uvicorn

    port = int(os.environ.get("BOSS_WORKBENCH_PORT", "5173"))
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level=os.environ.get("BOSS_WORKBENCH_LOG_LEVEL", "warning"))


if __name__ == "__main__":
    main()
