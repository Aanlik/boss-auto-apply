from __future__ import annotations

import base64
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.services.workflow_persistence import DATA_DIR


KEY_FILE = DATA_DIR / ".secret_key"


def _load_key() -> bytes:
    configured = os.environ.get("BOSS_WORKBENCH_SECRET_KEY", "").strip()
    if configured:
        raw = configured.encode("ascii")
        Fernet(raw)
        return raw
    if KEY_FILE.exists():
        raw = KEY_FILE.read_bytes().strip()
        Fernet(raw)
        return raw
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    raw = Fernet.generate_key()
    KEY_FILE.write_bytes(raw + b"\n")
    try:
        KEY_FILE.chmod(0o600)
    except OSError:
        pass
    return raw


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    token = Fernet(_load_key()).encrypt(value.encode("utf-8"))
    return token.decode("ascii")


def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    try:
        return Fernet(_load_key()).decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeDecodeError):
        return ""


def is_encrypted(value: str) -> bool:
    if not value:
        return False
    try:
        return decrypt_secret(value) != ""
    except Exception:
        return False
