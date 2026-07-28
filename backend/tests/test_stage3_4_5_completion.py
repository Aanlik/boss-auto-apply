from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_sqlite_migration_and_rollback_create_reversible_snapshot(tmp_path, monkeypatch):
    from app.services import workflow_persistence as persistence

    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)
    (tmp_path / "jobs").mkdir(parents=True)
    (tmp_path / "jobs" / "jobs.json").write_text('{"job-1":{"title":"产品经理"}}', encoding="utf-8")

    migrated = client.post("/api/maintenance/storage/migrate").json()
    rolled_back = client.post("/api/maintenance/storage/rollback").json()
    status = client.get("/api/maintenance/storage").json()

    assert migrated["sqlite"]["exists"] is True
    assert migrated["snapshotTables"] >= 1
    assert rolled_back["activeStore"] == "json"
    assert status["sqlite"]["exists"] is True


def test_api_call_logs_are_queryable_by_category(tmp_path, monkeypatch):
    from app.services import workflow_persistence as persistence
    from app.services.maintenance_service import log_api_call

    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)
    log_api_call("business", "POST", "https://example.com/business", 200, 128, {"company": "示例"})
    log_api_call("ai", "POST", "https://example.com/ai", 500, 20, {"model": "demo"})

    response = client.get("/api/maintenance/api-logs?category=business")

    assert response.status_code == 200
    logs = response.json()["logs"]
    assert len(logs) == 1
    assert logs[0]["category"] == "business"
    assert logs[0]["statusCode"] == 200


def test_release_preflight_combines_health_storage_and_logs(tmp_path, monkeypatch):
    from app.services import workflow_persistence as persistence
    from app.services import maintenance_service

    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(maintenance_service, "run_health_check", lambda: {
        "status": "warn",
        "checks": [
            {"key": "frontend_build", "label": "前端构建产物", "status": "ok", "message": "已检测到可发布页面", "action": ""},
            {"key": "ai_provider", "label": "AI 配置", "status": "warn", "message": "AI Key 未配置", "action": "在设置页补充 AI 配置"},
        ],
    })

    body = client.get("/api/maintenance/release/preflight").json()

    assert body["status"] == "warn"
    assert body["summary"]["total"] >= 4
    assert any(item["key"] == "ai_provider" and item["status"] == "warn" for item in body["checks"])
    assert any(item["key"] == "storage_backup" for item in body["checks"])


def test_retention_cleanup_archives_failed_tasks_and_resume_chats(tmp_path, monkeypatch):
    from app.services import workflow_persistence as persistence
    from app.services import workflow_tasks

    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(workflow_tasks, "TASKS_FILE", tmp_path / "workflow" / "tasks.json")
    task = workflow_tasks.start_task("ai", "失败任务")
    workflow_tasks.fail_task(task["id"], "失败", retryable=True)
    resume_file = tmp_path / "resumes" / "resume-1.json"
    resume_file.parent.mkdir(parents=True)
    resume_file.write_text('{"profile":{"name":"张三"},"chats":{"a":[{"role":"user","content":"hi"}]}}', encoding="utf-8")

    cleaned = client.post("/api/maintenance/retention/cleanup", json={
        "archive_failed_tasks": True,
        "archive_resume_chats": True,
    }).json()

    assert cleaned["archivedTasks"] == 1
    assert cleaned["archivedChats"] == 1
    assert (tmp_path / "archive" / "tasks.json").exists()
    assert '"chats": {}' in resume_file.read_text(encoding="utf-8")


def test_pdf_template_recommendation_and_resume_versions(tmp_path, monkeypatch):
    import app.routes.resumes as resumes_route

    monkeypatch.setattr(resumes_route, "STORE_DIR", tmp_path / "resumes")
    monkeypatch.setattr(resumes_route, "UPLOAD_DIR", tmp_path / "uploads")
    resumes_route.STORE_DIR.mkdir(parents=True)
    resumes_route.UPLOAD_DIR.mkdir(parents=True)
    monkeypatch.setattr(resumes_route, "_active_file_id", "resume-1")
    resumes_route._save_entry("resume-1", {
        "profile": {"name": "张三", "title": "产品经理", "skills": ["数据分析"], "summary": "旧总结"},
        "raw_text": "old",
    })

    recommendation = client.post("/api/resumes/pdf-template/recommend", json={"job_title": "后端工程师"}).json()
    saved = client.post("/api/resumes/versions", json={
        "label": "优化后",
        "profile": {"name": "张三", "title": "产品经理", "skills": ["数据分析", "增长"], "summary": "新总结"},
    }).json()
    compared = client.post("/api/resumes/versions/compare", json={"from_index": 0, "to_index": 1}).json()

    assert recommendation["template"] == "ats"
    assert saved["versions"][-1]["label"] == "优化后"
    assert "skills" in compared["changedFields"]


def test_assistant_results_are_persisted(tmp_path, monkeypatch):
    from app.services import workflow_persistence as persistence

    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)

    result = client.post("/api/assistant/jd-quality", json={"job": {"id": "job-1", "title": "产品", "jd_text": "负责数据分析"}}).json()
    saved = client.get("/api/assistant/results?job_id=job-1").json()

    assert result["qualityScore"] > 0
    assert saved["results"]
    assert saved["results"][0]["jobId"] == "job-1"


def test_workflow_task_idempotency_reuses_active_task(tmp_path, monkeypatch):
    from app.services import workflow_tasks

    monkeypatch.setattr(workflow_tasks, "TASKS_FILE", tmp_path / "workflow" / "tasks.json")

    first = workflow_tasks.start_task("job_capture", "抓取岗位", idempotency_key="capture:上海:产品经理")
    second = workflow_tasks.start_task("job_capture", "抓取岗位", idempotency_key="capture:上海:产品经理")

    assert second["id"] == first["id"]
    assert len(workflow_tasks.load_tasks(limit=10)) == 1


def test_release_check_script_lists_required_quality_gates():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "release_check.py"

    result = subprocess.run(
        [sys.executable, str(script), "--dry-run"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "pytest -q" in result.stdout
    assert "pnpm validate" in result.stdout
    assert "git diff --check" in result.stdout
    assert "local secret scan" in result.stdout
