from __future__ import annotations

import os

from app.services import workflow_persistence


VALID_MODES = {"production", "demo", "test"}


def _mode_file():
    return workflow_persistence.DATA_DIR / "runtime" / "mode.json"


def get_runtime_mode() -> str:
    env_mode = os.environ.get("BOSS_WORKBENCH_MODE", "").strip().lower()
    if env_mode:
        return env_mode if env_mode in VALID_MODES else "production"
    data = workflow_persistence._read_json(_mode_file(), {})
    mode = str(data.get("mode") or "production").strip().lower() if isinstance(data, dict) else "production"
    return mode if mode in VALID_MODES else "production"


def set_runtime_mode(mode: str) -> dict:
    next_mode = str(mode or "").strip().lower()
    if next_mode not in VALID_MODES:
        raise ValueError("运行模式必须是 production/demo/test")
    payload = {"mode": next_mode}
    workflow_persistence.write_json_atomic(_mode_file(), payload)
    return runtime_mode_status()


def runtime_mode_status() -> dict:
    env_mode = os.environ.get("BOSS_WORKBENCH_MODE", "").strip().lower()
    mode = get_runtime_mode()
    return {
        "mode": mode,
        "source": "env" if env_mode else "local",
        "demoAllowed": mode in {"demo", "test"},
        "dataScope": "演示/测试数据" if mode in {"demo", "test"} else "生产数据",
        "lockedByEnv": bool(env_mode),
        "warning": "当前由环境变量锁定，页面修改不会覆盖启动参数。" if env_mode else "",
    }


def is_demo_allowed() -> bool:
    return get_runtime_mode() in {"demo", "test"}
