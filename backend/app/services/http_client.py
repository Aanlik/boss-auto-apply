from __future__ import annotations

import ssl
from typing import Any

import aiohttp
import certifi


def build_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context(cafile=certifi.where())
    return ctx


def build_aiohttp_session(timeout_seconds: float = 30.0) -> aiohttp.ClientSession:
    return aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=timeout_seconds),
        connector=aiohttp.TCPConnector(ssl=build_ssl_context()),
    )


def format_http_error(exc: BaseException) -> str:
    from app.services.external_service import ProviderFailure
    if isinstance(exc, ProviderFailure):
        return str(exc)
    message = str(exc) or "网络请求失败"
    if "CERTIFICATE_VERIFY_FAILED" in message or "certificate verify failed" in message.lower():
        return "SSL 证书验证失败，请检查系统证书链或网络代理；桌面端默认使用 certifi 根证书"
    if "getaddrinfo" in message or "Name or service not known" in message or "nodename nor servname provided" in message:
        return "域名解析失败，请检查网络或 DNS"
    if "Connection refused" in message or "Network is unreachable" in message:
        return "目标服务不可达，请检查网络或防火墙"
    return message[:240]


def classify_http_error(exc: BaseException) -> dict[str, Any]:
    message = format_http_error(exc)
    kind = "network"
    if "SSL 证书验证失败" in message:
        kind = "ssl"
    elif "域名解析失败" in message:
        kind = "dns"
    elif "目标服务不可达" in message:
        kind = "connection"
    return {"message": message, "kind": kind}
