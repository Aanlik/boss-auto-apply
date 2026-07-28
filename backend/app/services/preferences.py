from __future__ import annotations

import json
import time
from pathlib import Path

from app.services import workflow_persistence
from app.services.workflow_persistence import write_json_atomic


PREFERENCES_FILE = workflow_persistence.DATA_DIR / "preferences.json"


def default_preferences() -> dict:
    return {
        "stability": 70,
        "salary": 70,
        "growth": 70,
        "match": 80,
        "avoid_industries": [],
        "preferred_cities": [],
        "updatedAt": "",
    }


def load_preferences() -> dict:
    try:
        if PREFERENCES_FILE.exists():
            data = json.loads(PREFERENCES_FILE.read_text())
            if isinstance(data, dict):
                return {**default_preferences(), **data}
    except (json.JSONDecodeError, OSError):
        pass
    return default_preferences()


def save_preferences(payload: dict) -> dict:
    preferences = default_preferences()
    for key in ("stability", "salary", "growth", "match"):
        preferences[key] = max(0, min(100, int(payload.get(key, preferences[key]) or 0)))
    preferences["avoid_industries"] = (
        [str(item).strip() for item in payload.get("avoid_industries", []) if str(item).strip()]
        if isinstance(payload.get("avoid_industries"), list)
        else []
    )
    preferences["preferred_cities"] = (
        [str(item).strip() for item in payload.get("preferred_cities", []) if str(item).strip()]
        if isinstance(payload.get("preferred_cities"), list)
        else []
    )
    preferences["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    write_json_atomic(PREFERENCES_FILE, preferences)
    return preferences
