from __future__ import annotations


def api_error(code: str, message: str, action: str = "") -> dict:
    """Return a stable API error payload that the frontend can map to friendly UI."""
    return {
        "code": code,
        "message": message,
        "action": action,
    }
