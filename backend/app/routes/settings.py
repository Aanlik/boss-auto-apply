"""AI 供应商设置路由"""
from fastapi import APIRouter, HTTPException
from app.services.ai_client import (
    get_config, set_config, clear_config, test_connection,
    PROVIDER_PRESETS,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/provider")
def get_provider_config() -> dict:
    """获取当前供应商配置（Key 打码）。"""
    cfg = get_config()
    key = cfg.get("api_key", "")
    masked = ""
    if key:
        masked = key[:7] + "****" + key[-4:] if len(key) >= 11 else key[:3] + "****"
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
