from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.services import workflow_persistence


def sqlite_path() -> Path:
    return workflow_persistence.DATA_DIR / "boss_workbench.sqlite3"


def connect() -> sqlite3.Connection:
    path = sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            company TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            city TEXT NOT NULL DEFAULT '',
            dedupe_key TEXT NOT NULL DEFAULT '',
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    return conn


def save_jobs(jobs: dict[str, Any]) -> int:
    with connect() as conn:
        conn.execute("DELETE FROM jobs")
        for job_id, job in jobs.items():
            payload = job.model_dump() if hasattr(job, "model_dump") else dict(job)
            conn.execute(
                """
                INSERT OR REPLACE INTO jobs(
                    id, company, title, city, dedupe_key, lifecycle_status, payload, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    str(job_id),
                    str(payload.get("company") or ""),
                    str(payload.get("title") or ""),
                    str(payload.get("city") or ""),
                    str(payload.get("dedupe_key") or ""),
                    str(payload.get("lifecycle_status") or "active"),
                    json.dumps(payload, ensure_ascii=False, default=str),
                ),
            )
        conn.commit()
    return len(jobs)


def load_jobs() -> dict[str, dict]:
    path = sqlite_path()
    if not path.exists():
        return {}
    with connect() as conn:
        rows = conn.execute("SELECT id, payload FROM jobs ORDER BY updated_at DESC").fetchall()
    jobs: dict[str, dict] = {}
    for row in rows:
        try:
            jobs[str(row["id"])] = json.loads(row["payload"])
        except (json.JSONDecodeError, TypeError):
            continue
    return jobs
