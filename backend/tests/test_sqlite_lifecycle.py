import sqlite3

import pytest


def test_new_database_records_schema_version(tmp_path, monkeypatch):
    from app.services import sqlite_kv_store, workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)

    sqlite_kv_store.put("test", "key", {"value": 1})

    status = sqlite_kv_store.schema_status()
    assert status["version"] == sqlite_kv_store.CURRENT_SCHEMA_VERSION
    assert status["version"] >= 1


def test_integrity_check_and_backup_listing_are_safe(tmp_path, monkeypatch):
    from app.services import sqlite_kv_store, workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    sqlite_kv_store.put("test", "key", {"value": 1})

    assert sqlite_kv_store.integrity_check()["status"] == "ok"
    backup = sqlite_kv_store.create_backup()
    assert backup["path"].startswith("storage/backups/")
    assert sqlite_kv_store.list_backups()[0]["path"] == backup["path"]


def test_restore_preview_validates_database_backup(tmp_path, monkeypatch):
    from app.services import sqlite_kv_store, workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    sqlite_kv_store.put("test", "key", {"value": 1})
    backup = sqlite_kv_store.create_backup()

    preview = sqlite_kv_store.restore_preview(backup["path"])

    assert preview["valid"] is True
    assert preview["integrity"] == "ok"
    assert preview["schemaVersion"] == sqlite_kv_store.CURRENT_SCHEMA_VERSION


def test_failed_migration_preserves_previous_schema_version(tmp_path, monkeypatch):
    from app.services import sqlite_kv_store, workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    sqlite_kv_store.put("test", "key", {"value": 1})
    previous = sqlite_kv_store.schema_status()["version"]

    def fail_migration(conn):
        conn.execute("CREATE TABLE should_rollback (value TEXT)")
        raise RuntimeError("migration failed")

    monkeypatch.setattr(
        sqlite_kv_store,
        "MIGRATIONS",
        [(previous + 1, fail_migration)],
    )

    with pytest.raises(RuntimeError, match="migration failed"):
        sqlite_kv_store.apply_pending_migrations()

    monkeypatch.setattr(sqlite_kv_store, "MIGRATIONS", [(1, sqlite_kv_store._migration_1)])
    assert sqlite_kv_store.schema_status()["version"] == previous
    with sqlite3.connect(tmp_path / "boss_workbench.sqlite3") as conn:
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='should_rollback'"
        ).fetchone() is None
