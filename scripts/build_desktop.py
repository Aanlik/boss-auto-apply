#!/usr/bin/env python3
from __future__ import annotations

import os
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
DIST_DESKTOP = ROOT / "dist-desktop"
BACKEND_DIST = DIST_DESKTOP / "backend"
BROWSER_DIST = DIST_DESKTOP / "browser"


def run(command: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print(f"\n== {' '.join(command)}")
    subprocess.run(command, cwd=cwd, env={**os.environ, **(env or {})}, check=True)


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        run([sys.executable, "-m", "pip", "install", "pyinstaller>=6.0"])


def build_frontend() -> None:
    run(["pnpm", "install", "--frozen-lockfile"], cwd=FRONTEND)
    run(["pnpm", "build"], cwd=FRONTEND)


def build_backend() -> None:
    ensure_pyinstaller()
    shutil.rmtree(BACKEND / "build", ignore_errors=True)
    shutil.rmtree(BACKEND_DIST, ignore_errors=True)
    BACKEND_DIST.mkdir(parents=True, exist_ok=True)
    separator = ";" if os.name == "nt" else ":"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--onedir",
        "--name",
        "boss-workbench-backend",
        "--distpath",
        str(BACKEND_DIST),
        "--workpath",
        str(BACKEND / "build" / "pyinstaller"),
        "--specpath",
        str(BACKEND / "build"),
        "--add-data",
        f"{FRONTEND / 'dist'}{separator}frontend/dist",
        "--add-data",
        f"{BACKEND / 'app' / 'resources'}{separator}app/resources",
        "--add-data",
        f"{BACKEND / 'app' / 'services' / 'extract_detail.js'}{separator}app/services",
        "--hidden-import",
        "app.main",
        "--hidden-import",
        "uvicorn.logging",
        "--hidden-import",
        "uvicorn.loops",
        "--hidden-import",
        "uvicorn.loops.auto",
        "--hidden-import",
        "uvicorn.protocols",
        "--hidden-import",
        "uvicorn.protocols.http",
        "--hidden-import",
        "uvicorn.protocols.http.auto",
        "--hidden-import",
        "uvicorn.protocols.websockets",
        "--hidden-import",
        "uvicorn.protocols.websockets.auto",
        str(BACKEND / "desktop_server.py"),
    ]
    run(command, cwd=ROOT)


def build_browser_runtime() -> None:
    run(["pnpm", "exec", "playwright", "install", "chromium"], cwd=FRONTEND)
    executable = subprocess.check_output(
        ["node", "-e", "const { chromium } = require('playwright'); console.log(chromium.executablePath())"],
        cwd=FRONTEND,
        text=True,
    ).strip()
    executable_path = Path(executable)
    if not executable_path.exists():
        raise FileNotFoundError(f"未找到 Chromium 可执行文件: {executable_path}")

    browser_root = next((item for item in executable_path.parents if item.name.startswith("chromium-")), None)
    if browser_root is None:
        raise RuntimeError(f"无法识别 Chromium 资源目录: {executable_path}")

    shutil.rmtree(BROWSER_DIST, ignore_errors=True)
    BROWSER_DIST.mkdir(parents=True, exist_ok=True)
    bundled_root = BROWSER_DIST / browser_root.name
    shutil.copytree(browser_root, bundled_root, symlinks=True)
    relative_executable = executable_path.relative_to(browser_root)
    (BROWSER_DIST / "browser-manifest.json").write_text(
        json.dumps(
            {
                "name": "chromium",
                "source": "playwright",
                "executableRelativePath": str(Path(browser_root.name) / relative_executable),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def build_electron(target: str) -> None:
    install_command = ["pnpm", "install", "--frozen-lockfile"] if (ROOT / "pnpm-lock.yaml").exists() else ["pnpm", "install", "--no-frozen-lockfile"]
    run(install_command, cwd=ROOT)
    env = {"CSC_IDENTITY_AUTO_DISCOVERY": "false"}
    if target == "dmg":
        run(["pnpm", "exec", "electron-builder", "--mac", "dmg"], cwd=ROOT, env=env)
    else:
        run(["pnpm", "exec", "electron-builder", "--mac", "dir"], cwd=ROOT, env=env)


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "dir"
    if target not in {"dir", "dmg"}:
        print("用法: python3 scripts/build_desktop.py [dir|dmg]")
        return 2
    build_frontend()
    build_backend()
    build_browser_runtime()
    build_electron(target)
    print("\n桌面端打包完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
