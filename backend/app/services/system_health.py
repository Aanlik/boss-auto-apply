from __future__ import annotations

import os
import shutil
from pathlib import Path

from app.services.workflow_persistence import DATA_DIR, _read_json
from app.services.boss_scraper import check_login_status


ROOT_DIR = Path(__file__).resolve().parents[3]
FRONTEND_DIR = ROOT_DIR / "frontend"


def _is_desktop() -> bool:
    return os.environ.get("BOSS_WORKBENCH_DESKTOP", "").strip().lower() in {"1", "true", "yes"}


def _check(key: str, label: str, status: str, message: str, action: str = "") -> dict:
    return {
        "key": key,
        "label": label,
        "status": status if status in {"ok", "warn", "error"} else "warn",
        "message": message,
        "action": action,
    }


def run_health_check() -> dict:
    desktop = _is_desktop()
    checks = []
    if desktop:
        checks.extend([
            _desktop_backend_check(),
            _browser_runtime_check(),
            _pnpm_check(desktop=True),
            _frontend_build_check(desktop=True),
        ])
    else:
        checks.extend([
            _pnpm_check(),
            _frontend_build_check(),
        ])
    checks.extend([
        _data_dir_check(),
        _ai_provider_check(),
        _baidu_search_check(),
        _business_api_check(),
        _boss_login_check(),
    ])
    required_checks = [item for item in checks if not item.get("optional")]
    if any(item["status"] == "error" for item in required_checks):
        status = "error"
    elif any(item["status"] == "warn" for item in required_checks):
        status = "warn"
    else:
        status = "ok"
    return {"status": status, "runtime": "desktop" if desktop else "development", "checks": checks}


def _desktop_backend_check() -> dict:
    return _check("desktop_backend", "桌面端后端", "ok", "后端运行环境已内置在安装包内")


def _browser_runtime_check() -> dict:
    executable = os.environ.get("BOSS_WORKBENCH_BROWSER_EXECUTABLE", "").strip()
    if executable and Path(executable).exists():
        return _check("browser_runtime", "内置浏览器", "ok", "Chromium 已随安装包内置")
    return _check("browser_runtime", "内置浏览器", "warn", "未检测到内置 Chromium 路径", "BOSS 抓取会尝试使用系统 Chrome")


def _pnpm_check(desktop: bool = False) -> dict:
    if desktop:
        item = _check("pnpm", "前端包管理器", "ok", "桌面端不需要安装 pnpm", "仅源码开发和重新打包需要 pnpm")
        item["optional"] = True
        return item
    if shutil.which("pnpm"):
        return _check("pnpm", "前端包管理器", "ok", "pnpm 可用")
    return _check("pnpm", "前端包管理器", "warn", "未检测到 pnpm", "安装 pnpm 后可执行前端校验")


def _frontend_build_check(desktop: bool = False) -> dict:
    if desktop and os.environ.get("BOSS_WORKBENCH_FRONTEND_DIST"):
        item = _check("frontend_build", "前端页面", "ok", "前端页面已内置在安装包内", "仅源码开发需要执行前端构建")
        item["optional"] = True
        return item
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
    try:
        status = check_login_status(probe=False)
    except Exception as exc:
        return _check("boss_login", "BOSS 登录状态", "warn", f"登录状态检测失败: {exc}", "请重新打开岗位模块并检测 BOSS 登录")

    if isinstance(status, dict) and status.get("logged_in"):
        message = status.get("message") or "已检测到有效登录状态"
        return _check("boss_login", "BOSS 登录状态", "ok", message)

    reason = str((status or {}).get("reason") or "")
    action = str((status or {}).get("action") or "")
    if reason in {"cookie_expired", "restricted"}:
        return _check("boss_login", "BOSS 登录状态", "error", status.get("message") or "登录已过期", action or "重新登录 BOSS 并再次检测")
    return _check("boss_login", "BOSS 登录状态", "warn", status.get("message") or "未检测到有效登录状态", action or "抓取前先完成 BOSS 登录")
