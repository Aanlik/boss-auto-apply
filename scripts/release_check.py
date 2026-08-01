#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Check:
    name: str
    command: list[str]
    cwd: Path
    env: dict[str, str] | None = None

    @property
    def display(self) -> str:
        return " ".join(self.command)


def checks() -> list[Check]:
    backend_path = str(REPO_ROOT / "backend")
    existing_pythonpath = os.environ.get("PYTHONPATH", "")
    pythonpath = os.pathsep.join(part for part in (backend_path, existing_pythonpath) if part)
    return [
        Check("后端全量测试", [sys.executable, "-m", "pytest", "backend/tests", "-q"], REPO_ROOT, {"PYTHONPATH": pythonpath}),
        Check("前端校验", ["pnpm", "validate"], REPO_ROOT / "frontend"),
        Check("Git 空白与换行检查", ["git", "diff", "--check"], REPO_ROOT),
        Check("本地密钥扫描", [sys.executable, str(Path(__file__).resolve()), "--local-secret-scan"], REPO_ROOT),
    ]


def local_secret_scan() -> int:
    data_root = REPO_ROOT / "data"
    suspicious: list[str] = []
    for rel in ("provider.json", "baidu_config.json", "business_info_config.json"):
        path = data_root / rel
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict):
            continue
        for key in ("api_key", "secret_key", "secret_id"):
            value = str(payload.get(key) or "")
            encrypted = str(payload.get(f"{key}_encrypted") or "")
            if value and not encrypted:
                suspicious.append(f"{rel}:{key}")
    if suspicious:
        print("Plain secret fields found:")
        for item in suspicious:
            print(f"- {item}")
        return 1
    print("local secret scan passed")
    return 0


def run_check(check: Check) -> int:
    print(f"\n== {check.name}: {check.display}")
    environment = os.environ.copy()
    environment.update(check.env or {})
    result = subprocess.run(check.command, cwd=check.cwd, env=environment, check=False)
    if result.returncode:
        print(f"!! {check.name} failed with exit code {result.returncode}")
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run release quality gates for BOSS Workbench.")
    parser.add_argument("--dry-run", action="store_true", help="List checks without executing them.")
    parser.add_argument("--local-secret-scan", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.local_secret_scan:
        return local_secret_scan()

    planned = checks()
    if args.dry_run:
        print("Release checks to run:")
        for item in planned:
            label = "local secret scan" if "--local-secret-scan" in item.command else item.display
            print(f"- {item.name}: {label}")
        return 0

    for item in planned:
        code = run_check(item)
        if code:
            return code
    print("\nAll release checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
