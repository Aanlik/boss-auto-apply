import asyncio

import pytest

from app.services.external_service import (
    ProviderFailure,
    async_run_with_resilience,
    reset_circuits,
    run_with_resilience,
)


def setup_function():
    reset_circuits()


def test_retries_transient_http_failure_then_succeeds():
    attempts = 0

    def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ProviderFailure("deepseek", "http", "服务繁忙", status_code=503)
        return {"ok": True}

    result = run_with_resilience(
        "deepseek",
        operation,
        max_attempts=3,
        base_delay=0,
        sleep=lambda _: None,
    )

    assert result == {"ok": True}
    assert attempts == 3


def test_does_not_retry_authentication_failure():
    attempts = 0

    def operation():
        nonlocal attempts
        attempts += 1
        raise ProviderFailure("business", "credentials", "鉴权失败", status_code=401)

    with pytest.raises(ProviderFailure) as exc_info:
        run_with_resilience(
            "business",
            operation,
            max_attempts=3,
            base_delay=0,
            sleep=lambda _: None,
        )

    assert attempts == 1
    assert exc_info.value.retryable is False
    assert exc_info.value.kind == "credentials"


def test_circuit_opens_after_repeated_failures():
    def operation():
        raise ProviderFailure("baidu", "network", "网络失败")

    for _ in range(2):
        with pytest.raises(ProviderFailure):
            run_with_resilience(
                "baidu",
                operation,
                max_attempts=1,
                circuit_threshold=2,
                base_delay=0,
                sleep=lambda _: None,
            )

    with pytest.raises(ProviderFailure) as exc_info:
        run_with_resilience(
            "baidu",
            operation,
            max_attempts=1,
            circuit_threshold=2,
            base_delay=0,
            sleep=lambda _: None,
        )

    assert exc_info.value.kind == "circuit_open"
    assert exc_info.value.retryable is True


def test_async_retry_uses_same_policy():
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ProviderFailure("business", "rate_limit", "请求过于频繁", status_code=429)
        return "done"

    result = asyncio.run(
        async_run_with_resilience(
            "business",
            operation,
            max_attempts=2,
            base_delay=0,
            async_sleep=lambda _: asyncio.sleep(0),
        )
    )

    assert result == "done"
    assert attempts == 2


def test_ai_test_mode_returns_deterministic_result_without_client(monkeypatch):
    from app.services import ai_client

    monkeypatch.setenv("BOSS_WORKBENCH_TEST_MODE", "1")
    monkeypatch.setattr(ai_client, "get_client", lambda: (_ for _ in ()).throw(AssertionError("external client used")))

    result = ai_client.chat_json("求职报告", "测试输入")

    assert result["summary"] == "测试模式报告"
    assert result["priority"] == "normal"


def test_qianfan_test_mode_does_not_open_http_session(monkeypatch):
    from app.services import internet_search, http_client

    monkeypatch.setenv("BOSS_WORKBENCH_TEST_MODE", "1")

    def forbidden_session(*args, **kwargs):
        raise AssertionError("external search used")

    monkeypatch.setattr(http_client, "build_aiohttp_session", forbidden_session)

    result = asyncio.run(internet_search._qianfan_search("test"))

    assert result["testMode"] is True
    assert result["summary"] == ""


def test_qianfan_retries_transient_failure(monkeypatch):
    from app.services import internet_search

    attempts = {"count": 0}
    monkeypatch.delenv("BOSS_WORKBENCH_TEST_MODE", raising=False)
    monkeypatch.setattr(internet_search, "QIANFAN_API_KEY", "baidu-key")

    async def fake_qianfan_search_once(prompt, max_results=8):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise ProviderFailure("baidu", "provider", "temporary failure", status_code=503, retryable=True)
        return {"summary": "重试成功", "references": [], "error": ""}

    monkeypatch.setattr(internet_search, "_qianfan_search_once", fake_qianfan_search_once)

    result = asyncio.run(internet_search._qianfan_search("test"))

    assert attempts["count"] == 3
    assert result["summary"] == "重试成功"


def test_ai_retries_transient_failure(monkeypatch):
    from app.services import ai_client

    attempts = 0

    class Message:
        content = '{"summary":"重试成功"}'

    class Choice:
        message = Message()

    class Response:
        choices = [Choice()]

    class Completions:
        def create(self, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                error = RuntimeError("temporary provider failure")
                error.status_code = 503
                raise error
            return Response()

    class FakeClient:
        chat = type("Chat", (), {"completions": Completions()})()

    monkeypatch.delenv("BOSS_WORKBENCH_TEST_MODE", raising=False)
    monkeypatch.setattr(ai_client, "get_client", lambda: FakeClient())
    monkeypatch.setattr(ai_client, "get_config", lambda: {"base_url": "https://example.test"})
    monkeypatch.setattr(ai_client, "get_model", lambda: "test-model")

    result = ai_client.chat_json("test", "test")

    assert attempts == 3
    assert result["summary"] == "重试成功"
