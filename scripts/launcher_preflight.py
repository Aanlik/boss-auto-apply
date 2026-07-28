#!/usr/bin/env python3
from __future__ import annotations

import shutil
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def main() -> int:
    checks = [
        ("python", sys.executable, True),
        ("pnpm", shutil.which("pnpm") or "", True),
        ("frontend build", str(ROOT / "frontend" / "dist" / "index.html"), True),
        ("data directory", str(ROOT / "data"), True),
        ("port 5173", "available" if port_available(5173) else "in use", False),
    ]
    failures = 0
    for name, value, required in checks:
        ok = bool(value) and (name != "port 5173" or value == "available")
        if not ok and required:
            failures += 1
        state = "OK" if ok else ("WARN" if not required else "FAIL")
        print(f"[{state}] {name}: {value or 'missing'}")
    if failures:
        print("启动前检查未通过，请先处理 FAIL 项。")
        return 1
    print("启动前检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
