from __future__ import annotations

import os


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "testserver"}


def is_remote_allowed() -> bool:
    return os.environ.get("BOSS_WORKBENCH_ALLOW_REMOTE", "").strip().lower() in {"1", "true", "yes"}


def is_allowed_host(host_header: str) -> bool:
    if is_remote_allowed():
        return True
    host = (host_header or "").split(",", 1)[0].strip().lower()
    if not host:
        return True
    if host.startswith("[::1]"):
        return True
    hostname = host.rsplit(":", 1)[0] if ":" in host and not host.startswith("[") else host
    return hostname in LOCAL_HOSTS
