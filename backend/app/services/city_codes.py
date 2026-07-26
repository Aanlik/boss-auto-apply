"""BOSS 城市码表，本项目内置资源。"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


CITY_RESOURCE = Path(__file__).resolve().parents[1] / "resources" / "city_codes.json"


@lru_cache(maxsize=1)
def load_city_codes() -> dict[str, str]:
    data = json.loads(CITY_RESOURCE.read_text(encoding="utf-8"))
    return {str(name): str(code) for name, code in data.items()}


def list_city_options() -> list[dict[str, str]]:
    return [{"name": name, "code": code} for name, code in load_city_codes().items()]


def resolve_city_code(city: str | None) -> str:
    codes = load_city_codes()
    if not city:
        return codes.get("全国", "100010000")

    cleaned = city.strip()
    if not cleaned:
        return codes.get("全国", "100010000")
    if cleaned in codes:
        return codes[cleaned]

    normalized = cleaned.rstrip("市")
    for name, code in codes.items():
        if name.rstrip("市") == normalized:
            return code
    return codes.get("全国", "100010000")
