from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from app.services.workflow_persistence import DATA_DIR, _read_json
from app.services.runtime_mode import get_runtime_mode


ROOT_DIR = Path(__file__).resolve().parents[3]
FRONTEND_DIR = ROOT_DIR / "frontend"


def _check(key: str, label: str, status: str, message: str, action: str = "") -> dict:
    return {
        "key": key,
        "label": label,
        "status": status if status in {"ok", "warn", "error"} else "warn",
        "message": message,
        "action": action,
    }


def run_health_check() -> dict:
    checks = [
        _runtime_mode_check(),
        _python_check(),
        _pnpm_check(),
        _frontend_build_check(),
        _data_dir_check(),
        _ai_provider_check(),
        _baidu_search_check(),
        _business_api_check(),
        _boss_login_check(),
    ]
    if any(item["status"] == "error" for item in checks):
        status = "error"
    elif any(item["status"] == "warn" for item in checks):
        status = "warn"
    else:
        status = "ok"
    return {"status": status, "checks": checks}


def _runtime_mode_check() -> dict:
    mode = get_runtime_mode()
    if mode == "production":
        return _check("runtime_mode", "运行模式", "ok", "当前为生产模式")
    return _check("runtime_mode", "运行模式", "warn", f"当前为 {mode} 模式", "上线前切换为 production")


def _python_check() -> dict:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    status = "ok" if sys.version_info >= (3, 10) else "warn"
    return _check("python", "Python 运行环境", status, f"当前版本 {version}", "建议使用 Python 3.10+")


def _pnpm_check() -> dict:
    if shutil.which("pnpm"):
        return _check("pnpm", "前端包管理器", "ok", "pnpm 可用")
    return _check("pnpm", "前端包管理器", "warn", "未检测到 pnpm", "安装 pnpm 后可执行前端校验")


def _frontend_build_check() -> dict:
    index = FRONTEND_DIR / "dist" / "index.html"
    if index.exists():
        return _check("frontend_build", "前端构建产物", "ok", "已检测到可发布页面")
    return _check("frontend_build", "前端构建产物", "warn", "尚未生成前端构建产物", "上线前执行前端构建")


def _data_dir_check() -> dict:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        probe = DATA_DIR / ".healthcheck"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return _check("data_dir", "数据目录", "ok", "数据目录可读写")
    except OSError as exc:
        return _check("data_dir", "数据目录", "error", f"数据目录不可写: {exc}", "检查本机文件权限")


def _ai_provider_check() -> dict:
    from app.services import ai_client

    cfg = ai_client.get_config()
    has_key = bool((cfg if isinstance(cfg, dict) else {}).get("api_key") or os.environ.get("OPENAI_API_KEY"))
    if has_key:
        return _check("ai_provider", "AI 配置", "ok", "AI Key 已配置")
    return _check("ai_provider", "AI 配置", "warn", "AI Key 未配置", "在设置页补充 AI 配置")


def _baidu_search_check() -> dict:
    from app.routes.settings import _read_baidu_config

    cfg = _read_baidu_config()
    has_key = bool((cfg if isinstance(cfg, dict) else {}).get("api_key") or os.environ.get("BAIDU_API_KEY"))
    if has_key:
        return _check("baidu_search", "百度搜索配置", "ok", "百度搜索 Key 已配置")
    return _check("baidu_search", "百度搜索配置", "warn", "百度搜索 Key 未配置", "需要搜索证据时先配置")


def _business_api_check() -> dict:
    from app.services import business_info

    cfg = business_info.get_config()
    has_secret = bool(
        (cfg.get("secret_id") and cfg.get("secret_key"))
        or (os.environ.get("TENCENT_SECRET_ID") and os.environ.get("TENCENT_SECRET_KEY"))
    )
    has_url = bool(cfg.get("endpoint") or cfg.get("url"))
    if has_secret or has_url:
        return _check("business_api", "工商 API 配置", "ok", "工商 API 已配置")
    return _check("business_api", "工商 API 配置", "warn", "工商 API 未配置", "配置腾讯云市场接口后可做公司尽调")


def _boss_login_check() -> dict:
    session_files = [
        DATA_DIR / "boss" / "storage_state.json",
        DATA_DIR / "boss_storage_state.json",
        ROOT_DIR / "boss_storage_state.json",
    ]
    if any(path.exists() for path in session_files):
        return _check("boss_login", "BOSS 登录状态", "ok", "已检测到登录缓存")
    return _check("boss_login", "BOSS 登录状态", "warn", "未检测到登录缓存", "抓取前先完成 BOSS 登录")
