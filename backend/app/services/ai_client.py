from __future__ import annotations
"""AI 调用封装 — 支持多供应商、自定义 Base URL、模型选择"""
import json
import os
import base64
import asyncio
import logging
import time
from pathlib import Path
from openai import OpenAI
from app.services.external_service import ProviderFailure, run_with_resilience, test_mode_enabled
from app.services import workflow_persistence
from app.services.workflow_persistence import write_json_atomic
from app.services.secret_store import decrypt_secret, encrypt_secret

logger = logging.getLogger("ai_client")

_client = None
_cached_config = None

CONFIG_FILE = workflow_persistence.DATA_DIR / "provider.json"

# 预设供应商
PROVIDER_PRESETS = {
    "openai": {
        "name": "OpenAI",
        "base_url": "",
        "models": ["gpt-5.6", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.5", "gpt-5.4-mini"],
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "models": ["deepseek-v4-flash", "deepseek-v4-pro"],
    },
    "zhipu": {
        "name": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-5.2", "glm-5-turbo", "glm-5", "glm-4.7", "glm-4.6"],
    },
    "moonshot": {
        "name": "月之暗面 Moonshot",
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["kimi-k3", "kimi-k2.7-code-highspeed", "kimi-k2.7-code", "kimi-k2.6"],
    },
    "custom": {
        "name": "自定义",
        "base_url": "",
        "models": [],
    },
}


def _load_config() -> dict:
    try:
        if CONFIG_FILE.exists():
            cfg = json.loads(CONFIG_FILE.read_text())
            api_key = cfg.get("api_key", "")
            encrypted_key = cfg.get("api_key_encrypted", "")
            if encrypted_key:
                cfg["api_key"] = decrypt_secret(encrypted_key)
            elif api_key:
                cfg["api_key_encrypted"] = encrypt_secret(api_key)
                cfg["api_key"] = ""
                _save_config(cfg)
                cfg["api_key"] = api_key
            return cfg
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("加载 AI 供应商配置失败: %s", e)
    return {}


def _save_config(cfg: dict):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(CONFIG_FILE, cfg)


def get_config() -> dict:
    """获取完整供应商配置。"""
    global _cached_config
    if _cached_config is not None:
        return _cached_config
    cfg = _load_config()
    if not cfg:
        cfg = {"provider": "openai", "api_key": "", "base_url": "", "model": ""}
    _cached_config = cfg
    return cfg


def get_api_key() -> str:
    """获取 API Key：文件存储 → 环境变量。"""
    cfg = get_config()
    key = cfg.get("api_key", "") or os.environ.get("OPENAI_API_KEY", "")
    return key


def set_config(provider: str, api_key: str, base_url: str = "", model: str = "") -> bool:
    """设置并持久化供应商配置。"""
    global _client, _cached_config
    provider = provider.strip()
    api_key = api_key.strip()
    base_url = (base_url or "").strip()
    model = (model or "").strip()

    if not provider:
        return False
    if not api_key:
        return False

    cfg = {
        "provider": provider,
        "api_key": "",
        "api_key_encrypted": encrypt_secret(api_key),
        "base_url": base_url,
        "model": model,
    }
    _save_config(cfg)
    _cached_config = {**cfg, "api_key": api_key}
    _client = None
    return True


def clear_config():
    """清除供应商配置。"""
    global _client, _cached_config
    _save_config({})
    _cached_config = {"provider": "openai", "api_key": "", "base_url": "", "model": ""}
    _client = None


def _build_client():
    """根据配置构建 OpenAI 客户端。"""
    cfg = get_config()
    api_key = cfg.get("api_key", "") or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("未设置 AI API Key，请在设置页面配置")

    base_url = cfg.get("base_url", "") or None

    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    else:
        return OpenAI(api_key=api_key)


def get_client():
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def test_connection() -> dict:
    """测试 API 连接是否有效。"""
    try:
        client = get_client()
        # 发送最小 chat 请求验证连接
        client.chat.completions.create(
            model=get_model(),
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        return {"ok": True, "message": "连接成功"}
    except Exception as e:
        return {"ok": False, "message": str(e)[:200]}


def get_model() -> str:
    """获取当前配置的模型名，回退到预设默认值。"""
    cfg = get_config()
    model = cfg.get("model", "")
    provider = cfg.get("provider", "openai")
    preset = PROVIDER_PRESETS.get(provider, {})
    defaults = preset.get("models", [])
    if model and (provider == "custom" or model in defaults):
        return model
    if model and defaults:
        logger.warning("供应商 %s 的模型 %s 已不在当前预设中，回退到 %s", provider, model, defaults[0])
    # 回退到供应商默认模型
    return defaults[0] if defaults else "gpt-5.6"


def chat_json(system: str, user: str, model: str | None = None, temperature: float = 0.3):
    """调用 AI chat，要求返回 JSON，自动解析。使用配置的模型。"""
    if test_mode_enabled():
        return {
            "summary": "测试模式报告",
            "priority": "normal",
            "resumeAdvice": ["突出与岗位相关的量化成果"],
            "interviewAdvice": ["准备一个跨团队协作案例"],
            "riskAdvice": ["使用测试数据，不代表真实风险结论"],
        }
    client = get_client()
    active_model = model or get_model()
    logger.info("AI 调用: %s (model=%s)", system[:80], active_model)

    kwargs = {
        "model": active_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }

    try:
        def operation():
            request_kwargs = dict(kwargs)
            try:
                request_kwargs["response_format"] = {"type": "json_object"}
                return client.chat.completions.create(**request_kwargs)
            except Exception:
                request_kwargs.pop("response_format", None)
                return client.chat.completions.create(**request_kwargs)

        started = time.time()
        resp = run_with_resilience("ai", operation, max_attempts=3, circuit_threshold=3)
    except ProviderFailure as exc:
        return {"error": str(exc), "errorMeta": exc.public_payload()}
    try:
        from app.services.maintenance_service import log_api_call
        log_api_call(
            "ai",
            "POST",
            str(get_config().get("base_url") or "openai"),
            200,
            int((time.time() - started) * 1000),
            {"model": active_model, "attempts": 1, "outcome": "success"},
        )
    except Exception:
        pass

    text = resp.choices[0].message.content
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("AI 返回非 JSON: %s", str(text)[:200] if text else "None")
        return {"error": "AI 返回格式异常", "raw": str(text)[:500] if text else ""}


def ocr_image(image_bytes: bytes, filename: str = "") -> str:
    """通过 AI Vision API 从图片中提取文本（OCR）。"""
    import mimetypes
    mime = mimetypes.guess_type(filename)[0] or "image/png"
    if mime not in ("image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"):
        mime = "image/png"

    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"

    client = get_client()
    model = get_model()

    resp = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": (
                    "请精确提取这张简历图片中的所有文字内容。"
                    "保持原文格式、分段和标点。不要添加任何解释或问候语，只输出提取的文本。"
                    "如果图片中是中文简历，请以中文输出。"
                )},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }],
        temperature=0.1,
        max_tokens=4096,
    )
    return resp.choices[0].message.content or ""


async def ocr_image_async(image_bytes: bytes, filename: str = "") -> str:
    """异步版本 — 通过 AI Vision API 从图片中提取文本（OCR）。"""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, ocr_image, image_bytes, filename)


async def chat(prompt: str, temperature: float = 0.3, max_tokens: int = 2000) -> str:
    """简单对话接口 — 发送单条 prompt，返回文本"""
    return await asyncio.to_thread(_chat_sync, prompt, temperature, max_tokens)


def _chat_sync(prompt: str, temperature: float, max_tokens: int) -> str:
    """在线程中执行同步 SDK 请求，避免阻塞 FastAPI 事件循环。"""
    client = get_client()
    model = get_model()
    started = time.time()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        try:
            from app.services.maintenance_service import log_api_call
            log_api_call(
                "ai",
                "POST",
                str(get_config().get("base_url") or "openai"),
                200,
                int((time.time() - started) * 1000),
                {"model": model, "stage": "ranking", "outcome": "success"},
            )
        except Exception:
            pass
        return resp.choices[0].message.content or ""
    except Exception as exc:
        try:
            from app.services.maintenance_service import log_api_call
            log_api_call(
                "ai",
                "POST",
                str(get_config().get("base_url") or "openai"),
                500,
                int((time.time() - started) * 1000),
                {"model": model, "stage": "ranking", "outcome": "failure", "error": str(exc)[:200]},
            )
        except Exception:
            pass
        raise


def get_ai_client():
    """返回可用于调用的 AI 客户端对象"""
    return _AIClient()


class _AIClient:
    """AI 客户端包装器，提供 chat 方法"""
    async def chat(self, prompt: str, temperature: float = 0.3, max_tokens: int = 2000) -> str:
        return await chat(prompt, temperature, max_tokens)
