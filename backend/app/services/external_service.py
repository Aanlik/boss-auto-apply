from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


RETRYABLE_STATUS_CODES = {408, 425, 429}
RETRYABLE_KINDS = {"network", "timeout", "rate_limit", "provider", "http"}
NON_RETRYABLE_KINDS = {"credentials", "validation", "configuration"}


@dataclass
class CircuitState:
    failures: int = 0
    opened_at: float = 0.0


class ProviderFailure(RuntimeError):
    def __init__(
        self,
        provider: str,
        kind: str,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool | None = None,
        attempts: int = 0,
    ):
        self.provider = provider
        self.kind = kind
        self.status_code = status_code
        self.retryable = (
            retryable
            if retryable is not None
            else kind in RETRYABLE_KINDS or status_code in RETRYABLE_STATUS_CODES or (status_code is not None and status_code >= 500)
        )
        self.attempts = attempts
        super().__init__(message)

    def public_payload(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "kind": self.kind,
            "message": str(self),
            "retryable": self.retryable,
            "attempts": self.attempts,
        }


_circuits: dict[str, CircuitState] = {}


def reset_circuits() -> None:
    _circuits.clear()


def test_mode_enabled() -> bool:
    return os.environ.get("BOSS_WORKBENCH_TEST_MODE", "").strip().lower() in {"1", "true", "yes"}


def _as_provider_failure(provider: str, exc: BaseException) -> ProviderFailure:
    if isinstance(exc, ProviderFailure):
        return exc
    status_code = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if isinstance(status_code, str) and status_code.isdigit():
        status_code = int(status_code)
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return ProviderFailure(provider, "timeout", "供应商请求超时", status_code=status_code)
    if status_code in (401, 403):
        return ProviderFailure(provider, "credentials", "供应商鉴权失败", status_code=status_code)
    if status_code == 429:
        return ProviderFailure(provider, "rate_limit", "供应商请求受到限流", status_code=status_code)
    if isinstance(status_code, int) and status_code >= 500:
        return ProviderFailure(provider, "provider", f"供应商服务异常（HTTP {status_code}）", status_code=status_code)
    if isinstance(status_code, int) and 400 <= status_code < 500:
        return ProviderFailure(provider, "validation", f"供应商请求无效（HTTP {status_code}）", status_code=status_code)
    if isinstance(exc, (ConnectionError, OSError)):
        return ProviderFailure(provider, "network", "供应商网络连接失败")
    return ProviderFailure(provider, "provider", str(exc)[:200] or "供应商调用失败")


def _check_circuit(provider: str, cooldown: float) -> None:
    state = _circuits.get(provider)
    if not state or not state.opened_at:
        return
    if time.monotonic() - state.opened_at < cooldown:
        raise ProviderFailure(provider, "circuit_open", "供应商暂时不可用，请稍后重试", retryable=True)
    state.opened_at = 0.0
    state.failures = 0


def _record_success(provider: str) -> None:
    _circuits[provider] = CircuitState()


def _record_failure(provider: str, threshold: int) -> None:
    state = _circuits.setdefault(provider, CircuitState())
    state.failures += 1
    if state.failures >= max(1, threshold):
        state.opened_at = time.monotonic()


def _delay(base_delay: float, attempt: int, max_delay: float) -> float:
    return min(max_delay, max(0.0, base_delay) * (2 ** max(0, attempt - 1)))


def run_with_resilience(
    provider: str,
    operation: Callable[[], Any],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.25,
    max_delay: float = 2.0,
    circuit_threshold: int = 3,
    circuit_cooldown: float = 30.0,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    _check_circuit(provider, circuit_cooldown)
    attempts = max(1, int(max_attempts))
    for attempt in range(1, attempts + 1):
        try:
            result = operation()
            _record_success(provider)
            return result
        except Exception as raw_exc:
            failure = _as_provider_failure(provider, raw_exc)
            failure.attempts = attempt
            if not failure.retryable or attempt >= attempts:
                _record_failure(provider, circuit_threshold)
                raise failure
            sleep(_delay(base_delay, attempt, max_delay))
    raise AssertionError("unreachable")


async def async_run_with_resilience(
    provider: str,
    operation: Callable[[], Awaitable[Any]],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.25,
    max_delay: float = 2.0,
    circuit_threshold: int = 3,
    circuit_cooldown: float = 30.0,
    async_sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
) -> Any:
    _check_circuit(provider, circuit_cooldown)
    attempts = max(1, int(max_attempts))
    for attempt in range(1, attempts + 1):
        try:
            result = await operation()
            _record_success(provider)
            return result
        except Exception as raw_exc:
            failure = _as_provider_failure(provider, raw_exc)
            failure.attempts = attempt
            if not failure.retryable or attempt >= attempts:
                _record_failure(provider, circuit_threshold)
                raise failure
            await async_sleep(_delay(base_delay, attempt, max_delay))
    raise AssertionError("unreachable")
