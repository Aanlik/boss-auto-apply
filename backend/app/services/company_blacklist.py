"""企业黑名单持久化与匹配。"""
from __future__ import annotations

from datetime import datetime, timezone
import re

from app.services import workflow_persistence as persistence


BLACKLIST_FILE = "jobs/company_blacklist.json"


def _path():
    return persistence.DATA_DIR / BLACKLIST_FILE


def _normalize(value: str) -> str:
    text = str(value or "").lower().strip()
    return re.sub(r"[\s·,，.。()（）【】\[\]{}<>《》\-_/|]+", "", text)


def load_company_blacklist() -> list[dict[str, str]]:
    data = persistence._read_json(_path(), [])
    if isinstance(data, dict):
        data = data.get("companies", [])
    if not isinstance(data, list):
        return []
    items = []
    seen = set()
    for item in data:
        name = item.get("name") if isinstance(item, dict) else str(item)
        clean = str(name or "").strip()
        key = _normalize(clean)
        if not clean or key in seen:
            continue
        seen.add(key)
        items.append({
            "name": clean,
            "createdAt": str((item or {}).get("createdAt") or "") if isinstance(item, dict) else "",
        })
    return items


def save_company_blacklist(items: list[dict[str, str]]) -> list[dict[str, str]]:
    persistence.write_json_atomic(_path(), items)
    return items


def add_company_to_blacklist(name: str) -> list[dict[str, str]]:
    clean = str(name or "").strip()
    if not clean:
        raise ValueError("company name is required")
    items = load_company_blacklist()
    key = _normalize(clean)
    if not any(_normalize(item["name"]) == key for item in items):
        items.append({"name": clean, "createdAt": datetime.now(timezone.utc).isoformat()})
        save_company_blacklist(items)
    return load_company_blacklist()


def remove_company_from_blacklist(name: str) -> list[dict[str, str]]:
    key = _normalize(name)
    items = [item for item in load_company_blacklist() if _normalize(item["name"]) != key]
    save_company_blacklist(items)
    return items


def is_company_blacklisted(company_name: str, items: list[dict[str, str]] | None = None) -> bool:
    company_key = _normalize(company_name)
    if not company_key:
        return False
    blacklist = items if items is not None else load_company_blacklist()
    for item in blacklist:
        black_key = _normalize(item.get("name", ""))
        if not black_key:
            continue
        if company_key == black_key or company_key in black_key or black_key in company_key:
            return True
    return False


def filter_blacklisted_jobs(jobs):
    blacklist = load_company_blacklist()
    kept = []
    removed = []
    for job in jobs:
        company = getattr(job, "company", "") if hasattr(job, "company") else job.get("company", "")
        if is_company_blacklisted(company, blacklist):
            removed.append(job)
        else:
            kept.append(job)
    return kept, removed
