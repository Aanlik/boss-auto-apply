from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models.resume import ResumeProfile


client = TestClient(app)


def test_resume_pdf_preview_returns_inline_pdf():
    response = client.post("/api/resumes/preview-pdf", json={
        "profile": ResumeProfile(name="张三", title="产品经理", summary="负责产品规划与用户增长").model_dump(),
        "optimization": {},
        "company": "示例科技",
        "job_title": "产品经理",
        "template": "modern",
    })

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert response.headers["content-disposition"].startswith("inline")


def test_deep_report_can_be_exported_as_pdf(tmp_path, monkeypatch):
    from app.routes import assistant as assistant_route

    monkeypatch.setattr(assistant_route, "_results_file", lambda: tmp_path / "assistant" / "results.json")
    client.post("/api/assistant/deep-report", json={
        "job": {"id": "job-1", "title": "产品经理", "company": "示例科技", "jd_text": "负责产品规划"},
        "resume": {"skills": ["产品规划"]},
        "diligence": {"companyName": "示例科技", "companyScore": 85, "riskLevel": "low"},
        "ranking": {"matchScore": 88, "compositeScore": 86},
    })

    response = client.get("/api/assistant/deep-report/export?job_id=job-1&format=pdf")

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert "application/pdf" in response.headers["content-type"]


def test_resume_records_use_sqlite_when_primary_storage_enabled(tmp_path, monkeypatch):
    from app.routes import resumes as resumes_route
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(resumes_route, "STORE_DIR", tmp_path / "resumes")
    client.post("/api/maintenance/storage/primary", json={"active_store": "sqlite"})

    resumes_route._save_entry("resume-1", {"profile": ResumeProfile(name="张三", title="产品经理")})
    loaded = resumes_route._load_entry("resume-1")

    assert loaded is not None
    assert loaded["profile"].name == "张三"


def test_maintenance_logs_use_sqlite_when_primary_storage_enabled(tmp_path, monkeypatch):
    from app.services import maintenance_service, workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    client.post("/api/maintenance/storage/primary", json={"active_store": "sqlite"})

    maintenance_service.log_event("info", "test", "sqlite event")
    maintenance_service.log_api_call("test", "GET", "https://example.com", 200, 12)

    assert maintenance_service.list_events()[0]["message"] == "sqlite event"
    assert maintenance_service.list_api_calls()[0]["url"] == "https://example.com"


def test_sqlite_migration_imports_resume_and_log_history(tmp_path, monkeypatch):
    from app.routes import resumes as resumes_route
    from app.services import maintenance_service, sqlite_kv_store, workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(resumes_route, "STORE_DIR", tmp_path / "resumes")
    monkeypatch.setattr(resumes_route, "UPLOAD_DIR", tmp_path / "uploads")
    resumes_route.STORE_DIR.mkdir(parents=True)
    resumes_route.UPLOAD_DIR.mkdir(parents=True)
    (resumes_route.STORE_DIR / "resume-history.json").write_text(
        '{"profile":{"name":"李四","title":"后端工程师"},"raw_text":"历史简历"}',
        encoding="utf-8",
    )
    (resumes_route.UPLOAD_DIR / "resume-history.pdf").write_bytes(b"resume")
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "events.jsonl").write_text(
        '{"id":"event-history","time":"2026-01-01T00:00:00+00:00","level":"info","category":"test","message":"历史事件","detail":{}}\n',
        encoding="utf-8",
    )
    (logs / "api_calls.jsonl").write_text(
        '{"id":"api-history","time":"2026-01-01T00:00:00+00:00","category":"test","method":"GET","url":"https://example.com/history","statusCode":200,"durationMs":1,"detail":{}}\n',
        encoding="utf-8",
    )

    status = maintenance_service.migrate_to_sqlite()
    client.post("/api/maintenance/storage/primary", json={"active_store": "sqlite"})
    resumes_route._load_all_entries()

    assert status["resumesImported"] == 1
    assert status["maintenanceEventsImported"] == 1
    assert status["apiCallsImported"] == 1
    assert sqlite_kv_store.get("resumes", "resume-history")["raw_text"] == "历史简历"
    assert resumes_route._load_entry("resume-history")["profile"].name == "李四"
    assert any(item["id"] == "event-history" for item in maintenance_service.list_events())
    assert any(item["id"] == "api-history" for item in maintenance_service.list_api_calls())
    assert resumes_route._uploaded_files[0]["id"] == "resume-history"


def test_resume_retention_deletes_sqlite_copy(tmp_path, monkeypatch):
    from app.routes import resumes as resumes_route
    from app.services import sqlite_kv_store, workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(resumes_route, "STORE_DIR", tmp_path / "resumes")
    monkeypatch.setattr(resumes_route, "UPLOAD_DIR", tmp_path / "uploads")
    workflow_persistence.write_json_atomic(tmp_path / "storage" / "config.json", {"activeStore": "sqlite"})
    sqlite_kv_store.put("resumes", "expired-resume", {"profile": {"name": "过期简历"}})

    resumes_route._delete_entry("expired-resume")

    assert sqlite_kv_store.get("resumes", "expired-resume") is None
