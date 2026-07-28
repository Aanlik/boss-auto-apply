from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _default_data_dir() -> Path:
    configured = os.environ.get("BOSS_WORKBENCH_DATA_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parents[3] / "data"


DATA_DIR = _default_data_dir()


def _read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return default


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, default=str)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _write_json(path: Path, payload: Any) -> None:
    write_json_atomic(path, payload)


def _active_store() -> str:
    cfg = _read_json(DATA_DIR / "storage" / "config.json", {})
    store = str((cfg if isinstance(cfg, dict) else {}).get("activeStore") or "json").lower()
    return "sqlite" if store == "sqlite" else "json"


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value).strip("_") or "unknown"


def _company_key(report: dict) -> str:
    business = report.get("businessInfo") if isinstance(report.get("businessInfo"), dict) else {}
    return (
        str(report.get("companyKey") or "").strip()
        or str(business.get("companyKey") or "").strip()
        or str(business.get("unifiedCreditCode") or "").strip()
        or _slug(str(report.get("companyName") or report.get("company_name") or ""))
    )


def save_diligence_report(report: dict) -> dict:
    company = report.get("companyName") or report.get("company_name") or ""
    if not company:
        raise ValueError("companyName is required")
    saved = {
        **report,
        "companyKey": _company_key(report),
        "sourceCompanyName": report.get("sourceCompanyName") or report.get("source_company_name") or company,
        "completedAt": report.get("completedAt") or datetime.now(timezone.utc).isoformat(),
    }
    _write_json(DATA_DIR / "diligence" / f"{_slug(company)}.json", saved)
    if _active_store() == "sqlite":
        from app.services import sqlite_kv_store
        sqlite_kv_store.put("diligence", _company_key(saved), saved)
        sqlite_kv_store.put("diligence_by_name", str(saved.get("companyName") or company), saved)
    return saved


def load_diligence_reports() -> dict[str, dict]:
    if _active_store() == "sqlite":
        from app.services import sqlite_kv_store
        stored = sqlite_kv_store.all("diligence_by_name")
        if stored:
            return {str(key): value for key, value in stored.items() if isinstance(value, dict)}
    root = DATA_DIR / "diligence"
    reports: dict[str, dict] = {}
    if not root.exists():
        return reports
    for path in sorted(root.glob("*.json")):
        report = _read_json(path, {})
        company = report.get("companyName")
        if company:
            reports[company] = report
    return reports


def find_diligence_report(identifier: str) -> dict | None:
    target = str(identifier or "").strip()
    if not target:
        return None
    for report in load_diligence_reports().values():
        if not isinstance(report, dict):
            continue
        business = report.get("businessInfo") if isinstance(report.get("businessInfo"), dict) else {}
        keys = (
            report.get("companyName"),
            report.get("sourceCompanyName"),
            report.get("companyKey"),
            business.get("companyName"),
            business.get("sourceCompanyName"),
            business.get("companyKey"),
            business.get("unifiedCreditCode"),
        )
        if any(str(key or "").strip() == target for key in keys):
            return report
    return None


def save_rankings(rankings: list[dict]) -> list[dict]:
    _write_json(DATA_DIR / "rankings" / "latest.json", rankings)
    if _active_store() == "sqlite":
        from app.services import sqlite_kv_store
        sqlite_kv_store.put("rankings", "latest", rankings)
    return rankings


def load_rankings() -> list[dict]:
    if _active_store() == "sqlite":
        from app.services import sqlite_kv_store
        stored = sqlite_kv_store.get("rankings", "latest", [])
        if isinstance(stored, list):
            return stored
    data = _read_json(DATA_DIR / "rankings" / "latest.json", [])
    return data if isinstance(data, list) else []


def save_greetings(greetings: dict[str, str]) -> dict[str, str]:
    _write_json(DATA_DIR / "greetings" / "drafts.json", greetings)
    return greetings


def load_greetings() -> dict[str, str]:
    data = _read_json(DATA_DIR / "greetings" / "drafts.json", {})
    return data if isinstance(data, dict) else {}


def save_send_record(job_id: str, status: str, note: str = "", message: str = "", dry_run: bool = False) -> dict:
    if not job_id:
        raise ValueError("job_id is required")
    records = load_send_records()
    existing = next((record for record in records if record.get("jobId") == job_id), None)
    if existing and existing.get("status") == "sent" and status == "sent":
        return existing
    record = {
        "jobId": job_id,
        "status": status,
        "note": note,
        "message": message,
        "dryRun": dry_run,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    records = [record for record in records if record.get("jobId") != job_id] + [record]
    _write_json(DATA_DIR / "greetings" / "send_records.json", records)
    return record


def load_send_records() -> list[dict]:
    data = _read_json(DATA_DIR / "greetings" / "send_records.json", [])
    return data if isinstance(data, list) else []
