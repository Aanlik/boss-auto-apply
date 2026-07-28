from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services import workflow_persistence


CURRENT_SCHEMA_VERSION = 1


def _migration_1(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS kv_store (
            namespace TEXT NOT NULL,
            key TEXT NOT NULL,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(namespace, key)
        )
        """
    )


MIGRATIONS = [(1, _migration_1)]


def sqlite_path() -> Path:
    return workflow_persistence.DATA_DIR / "boss_workbench.sqlite3"


def _open_raw() -> sqlite3.Connection:
    path = sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _prepare_schema_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
    return int(row["version"] or 0) if row else 0


def _apply_pending(conn: sqlite3.Connection) -> int:
    _prepare_schema_table(conn)
    current = _schema_version(conn)
    for version, migration in sorted(MIGRATIONS, key=lambda item: item[0]):
        if version <= current:
            continue
        try:
            conn.execute("BEGIN")
            migration(conn)
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (version, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        current = version
    return current


def connect() -> sqlite3.Connection:
    conn = _open_raw()
    try:
        _apply_pending(conn)
        return conn
    except Exception:
        conn.close()
        raise


def apply_pending_migrations() -> dict[str, Any]:
    conn = _open_raw()
    try:
        version = _apply_pending(conn)
        return {"version": version, "applied": True}
    finally:
        conn.close()


def schema_status() -> dict[str, Any]:
    conn = connect()
    try:
        return {
            "version": _schema_version(conn),
            "targetVersion": CURRENT_SCHEMA_VERSION,
            "path": str(sqlite_path()),
        }
    finally:
        conn.close()


def integrity_check() -> dict[str, Any]:
    path = sqlite_path()
    if not path.exists():
        return {"status": "missing", "message": "SQLite 数据库尚未创建"}
    try:
        conn = connect()
        try:
            result = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
            return {"status": "ok" if result.lower() == "ok" else "error", "message": result}
        finally:
            conn.close()
    except Exception as exc:
        return {"status": "error", "message": str(exc)[:200]}


def _backup_dir() -> Path:
    return workflow_persistence.DATA_DIR / "storage" / "backups"


def create_backup() -> dict[str, Any]:
    source = sqlite_path()
    connect().close()
    backup_dir = _backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)
    filename = f"boss_workbench-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.sqlite3"
    target = backup_dir / filename
    source_conn = sqlite3.connect(source)
    target_conn = sqlite3.connect(target)
    try:
        source_conn.backup(target_conn)
        target_conn.commit()
    finally:
        source_conn.close()
        target_conn.close()
    return {
        "path": target.relative_to(workflow_persistence.DATA_DIR).as_posix(),
        "size": target.stat().st_size,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }


def list_backups() -> list[dict[str, Any]]:
    root = _backup_dir()
    if not root.exists():
        return []
    return [
        {
            "path": path.relative_to(workflow_persistence.DATA_DIR).as_posix(),
            "size": path.stat().st_size,
            "updatedAt": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        }
        for path in sorted(root.glob("*.sqlite3"), key=lambda item: item.stat().st_mtime, reverse=True)
    ]


def restore_preview(relative_path: str) -> dict[str, Any]:
    backup_root = _backup_dir().resolve()
    target = (workflow_persistence.DATA_DIR / str(relative_path or "")).resolve()
    if backup_root not in target.parents or target.suffix != ".sqlite3" or not target.exists():
        raise ValueError("invalid SQLite backup path")
    try:
        conn = sqlite3.connect(target)
        try:
            integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
            row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
            version = int(row[0] or 0) if row else 0
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        return {"valid": False, "path": relative_path, "integrity": "error", "message": str(exc)[:200]}
    return {
        "valid": integrity.lower() == "ok",
        "path": target.relative_to(workflow_persistence.DATA_DIR).as_posix(),
        "integrity": integrity.lower(),
        "schemaVersion": version,
    }


def put(namespace: str, key: str, payload: Any) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO kv_store(namespace, key, payload, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (namespace, key, json.dumps(payload, ensure_ascii=False, default=str)),
        )
        conn.commit()


def get(namespace: str, key: str, default: Any = None) -> Any:
    path = sqlite_path()
    if not path.exists():
        return default
    with connect() as conn:
        row = conn.execute("SELECT payload FROM kv_store WHERE namespace = ? AND key = ?", (namespace, key)).fetchone()
    if not row:
        return default
    try:
        return json.loads(row["payload"])
    except (json.JSONDecodeError, TypeError):
        return default


def delete(namespace: str, key: str) -> None:
    path = sqlite_path()
    if not path.exists():
        return
    with connect() as conn:
        conn.execute("DELETE FROM kv_store WHERE namespace = ? AND key = ?", (namespace, key))
        conn.commit()


def all(namespace: str) -> dict[str, Any]:
    path = sqlite_path()
    if not path.exists():
        return {}
    with connect() as conn:
        rows = conn.execute("SELECT key, payload FROM kv_store WHERE namespace = ?", (namespace,)).fetchall()
    result: dict[str, Any] = {}
    for row in rows:
        try:
            result[str(row["key"])] = json.loads(row["payload"])
        except (json.JSONDecodeError, TypeError):
            continue
    return result
