from __future__ import annotations

"""AI 供应商设置路由"""
import json as _json
import logging
import secrets
import time

from fastapi import APIRouter, Header, HTTPException
from pathlib import Path as _Path

from app.services.ai_client import (
    get_config, set_config, clear_config, test_connection,
    PROVIDER_PRESETS,
)
from app.services.workflow_persistence import write_json_atomic

router = APIRouter(prefix="/api/settings", tags=["settings"])
_EXPORT_TOKENS: dict[str, float] = {}
EXPORT_TOKEN_TTL_SECONDS = 300
logger = logging.getLogger(__name__)


def _mask_secret(value: str, head: int = 6, tail: int = 4) -> str:
    if not value:
        return ""
    return value[:head] + "****" + value[-tail:] if len(value) > head + tail else value[:3] + "****"


@router.get("/provider")
def get_provider_config() -> dict:
    """获取当前供应商配置（Key 打码）。"""
    cfg = get_config()
    key = cfg.get("api_key", "")
    masked = ""
    if key:
        masked = _mask_secret(key, 7, 4)
    return {
        "provider": cfg.get("provider", "openai"),
        "configured": bool(key),
        "masked": masked,
        "base_url": cfg.get("base_url", ""),
        "model": cfg.get("model", ""),
    }


@router.get("/provider/presets")
def get_provider_presets() -> dict:
    """返回所有预设供应商信息（不含 Key）。"""
    return {"presets": PROVIDER_PRESETS}


@router.post("/provider")
def save_provider_config(payload: dict) -> dict:
    """保存供应商配置。"""
    provider = payload.get("provider", "").strip()
    api_key = payload.get("api_key", "").strip()
    base_url = payload.get("base_url", "").strip()
    model = payload.get("model", "").strip()

    if not api_key:
        raise HTTPException(status_code=400, detail="API Key 不能为空")
    if not provider:
        raise HTTPException(status_code=400, detail="请选择一个供应商")

    if not set_config(provider, api_key, base_url, model):
        raise HTTPException(status_code=400, detail="配置保存失败")

    return {"configured": True, "message": "配置已保存"}


@router.delete("/provider")
def delete_provider_config() -> dict:
    """清除供应商配置。"""
    clear_config()
    return {"configured": False, "message": "配置已清除"}


@router.post("/provider/test")
def test_provider() -> dict:
    """测试当前供应商连接是否有效。"""
    if not get_config().get("api_key"):
        raise HTTPException(status_code=400, detail="请先设置 API Key")
    result = test_connection()
    return result


@router.post("/export/authorize")
def authorize_settings_export() -> dict:
    """生成一次性完整配置导出令牌。"""
    token = secrets.token_urlsafe(24)
    _EXPORT_TOKENS[token] = time.time() + EXPORT_TOKEN_TTL_SECONDS
    return {"token": token, "expiresIn": EXPORT_TOKEN_TTL_SECONDS}


def _consume_export_token(token: str | None) -> bool:
    now = time.time()
    for saved, expires_at in list(_EXPORT_TOKENS.items()):
        if expires_at < now:
            _EXPORT_TOKENS.pop(saved, None)
    if not token:
        return False
    expires_at = _EXPORT_TOKENS.pop(token, None)
    return bool(expires_at and expires_at >= now)


@router.get("/export")
def export_settings(
    include_secret: bool = False,
    x_settings_export_token: str | None = Header(default=None),
) -> dict:
    """导出全部 API 配置。默认脱敏；include_secret=true 才导出完整密钥。"""
    from app.services import business_info

    if include_secret and not _consume_export_token(x_settings_export_token):
        raise HTTPException(status_code=403, detail="完整配置导出需要重新确认")

    provider_cfg = get_config()
    baidu_cfg = _read_baidu_config()
    business_cfg = business_info.get_config()

    provider_key = provider_cfg.get("api_key", "")
    baidu_key = baidu_cfg.get("api_key", "")
    secret_id = business_cfg.get("secret_id", "")
    secret_key = business_cfg.get("secret_key", "")

    return {
        "kind": "settings_backup",
        "version": 1,
        "includeSecret": include_secret,
        "provider": {
            "provider": provider_cfg.get("provider", "openai"),
            "api_key": provider_key if include_secret else "",
            "masked": _mask_secret(provider_key, 7, 4),
            "base_url": provider_cfg.get("base_url", ""),
            "model": provider_cfg.get("model", ""),
        },
        "baidu": {
            "api_key": baidu_key if include_secret else "",
            "masked": _mask_secret(baidu_key, 7, 4),
        },
        "business": {
            "secret_id": secret_id if include_secret else "",
            "secret_key": secret_key if include_secret else "",
            "masked": _mask_secret(secret_id, 6, 4),
            "endpoint": business_cfg.get("endpoint", ""),
        },
    }


@router.post("/import")
def import_settings(payload: dict) -> dict:
    """导入配置备份。脱敏备份不会覆盖现有密钥。"""
    from app.services import ai_client, business_info
    imported: list[str] = []

    provider = payload.get("provider") if isinstance(payload.get("provider"), dict) else {}
    provider_key = str(provider.get("api_key") or "").strip()
    if provider_key:
        if not ai_client.set_config(
            str(provider.get("provider") or "openai"),
            provider_key,
            str(provider.get("base_url") or ""),
            str(provider.get("model") or ""),
        ):
            raise HTTPException(status_code=400, detail="AI 供应商配置导入失败")
        imported.append("provider")

    baidu = payload.get("baidu") if isinstance(payload.get("baidu"), dict) else {}
    baidu_key = str(baidu.get("api_key") or "").strip()
    if baidu_key:
        _write_baidu_config({"api_key": baidu_key})
        imported.append("baidu")

    business = payload.get("business") if isinstance(payload.get("business"), dict) else {}
    secret_id = str(business.get("secret_id") or "").strip()
    secret_key = str(business.get("secret_key") or "").strip()
    if secret_id and secret_key:
        if not business_info.set_config(secret_id, secret_key, str(business.get("endpoint") or "")):
            raise HTTPException(status_code=400, detail="工商 API 配置导入失败")
        imported.append("business")

    return {"imported": imported, "message": "配置导入完成"}


# ═══════════════════════════════════════════════════════════
#  百度千帆智能搜索 API 配置（仅需 API Key）
# ═══════════════════════════════════════════════════════════

BAIDU_CONFIG_FILE = _Path(__file__).resolve().parents[3] / "data" / "baidu_config.json"


def _read_baidu_config() -> dict:
    try:
        if BAIDU_CONFIG_FILE.exists():
            return _json.loads(BAIDU_CONFIG_FILE.read_text())
    except (_json.JSONDecodeError, OSError) as e:
        logger.warning("加载百度搜索 API 配置失败: %s", e)
    return {"api_key": ""}


def _write_baidu_config(cfg: dict):
    BAIDU_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(BAIDU_CONFIG_FILE, cfg)


@router.get("/baidu")
def get_baidu_config() -> dict:
    """获取千帆智能搜索 API Key（打码）。"""
    cfg = _read_baidu_config()
    key = cfg.get("api_key", "")
    masked = key[:7] + "****" + key[-4:] if len(key) >= 11 else (key[:3] + "****" if key else "")
    return {"configured": bool(key), "masked": masked}


@router.post("/baidu")
def save_baidu_config(payload: dict) -> dict:
    """保存千帆智能搜索 API Key。"""
    api_key = payload.get("api_key", "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key 不能为空")

    cfg = {"api_key": api_key}
    _write_baidu_config(cfg)

    import os as _os
    _os.environ["BAIDU_API_KEY"] = api_key
    from app.services.internet_search import load_baidu_config, _search_cache
    load_baidu_config()
    _search_cache.clear()

    masked = api_key[:7] + "****" + api_key[-4:] if len(api_key) >= 11 else api_key[:3] + "****"
    return {"configured": True, "masked": masked, "message": "千帆搜索 API Key 已保存"}


@router.delete("/baidu")
def delete_baidu_config() -> dict:
    """清除千帆搜索 API Key。"""
    _write_baidu_config({"api_key": ""})

    import os as _os
    _os.environ.pop("BAIDU_API_KEY", None)
    from app.services.internet_search import load_baidu_config, _search_cache
    load_baidu_config()
    _search_cache.clear()

    return {"configured": False, "message": "千帆搜索 API Key 已清除"}


@router.post("/baidu/test")
async def test_baidu_connection() -> dict:
    """测试千帆智能搜索 API 连接。"""
    from app.services.internet_search import test_qianfan_connection
    return await test_qianfan_connection()


# ═══════════════════════════════════════════════════════════
#  腾讯云市场企业工商 API 配置
# ═══════════════════════════════════════════════════════════

@router.get("/business")
def get_business_config() -> dict:
    """获取工商 API 配置（Key 打码）。"""
    from app.services.business_info import get_config
    cfg = get_config()
    sid = cfg.get("secret_id", "")
    masked = sid[:6] + "****" + sid[-4:] if len(sid) >= 10 else (sid[:3] + "****" if sid else "")
    return {
        "configured": cfg.get("configured", False),
        "masked": masked,
        "endpoint": cfg.get("endpoint", ""),
    }


@router.post("/business")
def save_business_config(payload: dict) -> dict:
    """保存工商 API 配置。"""
    from app.services.business_info import set_config, _info_cache
    secret_id = payload.get("secret_id", "").strip()
    secret_key = payload.get("secret_key", "").strip()
    endpoint = payload.get("endpoint", "").strip()

    if not secret_id or not secret_key:
        raise HTTPException(status_code=400, detail="SecretId 和 SecretKey 不能为空")

    if not set_config(secret_id, secret_key, endpoint):
        raise HTTPException(status_code=400, detail="配置保存失败")

    _info_cache.clear()

    masked = secret_id[:6] + "****" + secret_id[-4:] if len(secret_id) >= 10 else secret_id[:3] + "****"
    return {"configured": True, "masked": masked, "message": "工商 API 配置已保存"}


@router.delete("/business")
def delete_business_config() -> dict:
    """清除工商 API 配置。"""
    from app.services.business_info import clear_config, _info_cache
    clear_config()
    _info_cache.clear()
    return {"configured": False, "message": "工商 API 配置已清除"}


@router.post("/business/test")
async def test_business_connection() -> dict:
    """测试工商 API 连接。"""
    from app.services.business_info import test_connection
    return await test_connection()
