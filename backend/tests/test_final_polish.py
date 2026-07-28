from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.models.job import JobRecord


client = TestClient(app)


def test_sqlite_primary_store_covers_rankings_and_diligence(tmp_path, monkeypatch):
    from app.services import maintenance_service, workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    client.post("/api/maintenance/storage/primary", json={"active_store": "sqlite"})

    saved_report = workflow_persistence.save_diligence_report({"companyName": "示例科技", "companyScore": 88})
    saved_rankings = workflow_persistence.save_rankings([{"jobId": "job-1", "compositeScore": 91}])

    assert saved_report["companyName"] == "示例科技"
    assert saved_rankings[0]["jobId"] == "job-1"
    assert workflow_persistence.load_diligence_reports()["示例科技"]["companyScore"] == 88
    assert workflow_persistence.load_rankings()[0]["compositeScore"] == 91
    with __import__("sqlite3").connect(tmp_path / "boss_workbench.sqlite3") as conn:
        rows = conn.execute("SELECT namespace, key FROM kv_store ORDER BY namespace, key").fetchall()
    assert ("diligence_by_name", "示例科技") in rows
    assert ("rankings", "latest") in rows


def test_dashboard_onboarding_and_review_center(monkeypatch):
    import app.routes.jobs as jobs_route

    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(id="job-1", title="产品经理", company="示例科技", application_status="greeted", decision_status="recommended", capture_batch_id="batch-a"),
        "job-2": JobRecord(id="job-2", title="运营", company="风险科技", application_status="rejected", decision_status="risky", capture_batch_id="batch-b"),
    })

    onboarding = client.get("/api/dashboard/onboarding").json()
    review = client.get("/api/dashboard/review-center").json()

    assert onboarding["steps"][0]["key"] == "configure"
    assert any(step["page"] == "jobs" for step in onboarding["steps"])
    assert review["summary"]["total"] == 2
    assert review["recommendations"]
    assert review["batches"]


def test_assistant_deep_report_can_be_edited_and_versioned(tmp_path, monkeypatch):
    from app.routes import assistant as assistant_route

    monkeypatch.setattr(assistant_route, "_results_file", lambda: tmp_path / "assistant" / "results.json")
    client.post("/api/assistant/deep-report", json={
        "job": {"id": "job-1", "title": "产品经理", "company": "示例科技", "jd_text": "负责产品规划"},
        "resume": {},
        "diligence": {},
        "ranking": {},
    })

    edited = client.post("/api/assistant/deep-report/edit", json={
        "job_id": "job-1",
        "summary": "人工复核后优先投递",
        "notes": ["确认业务方向匹配"],
    }).json()

    assert edited["record"]["result"]["manualReport"]["summary"] == "人工复核后优先投递"
    assert edited["record"]["result"]["manualReport"]["version"] == 1


def test_boss_detail_retry_task_replays_failed_job_ids(tmp_path, monkeypatch):
    from app.routes import jobs as jobs_route
    from app.services import workflow_tasks

    monkeypatch.setattr(workflow_tasks, "TASKS_FILE", tmp_path / "workflow" / "tasks.json")
    monkeypatch.setattr(jobs_route, "JOBS_FILE", tmp_path / "jobs" / "jobs.json")
    jobs_route._job_store.clear()
    jobs_route._job_store["job-1"] = JobRecord(id="job-1", title="产品经理", company="示例科技")

    task = workflow_tasks.start_task("jd_enrich", "获取 JD 详情", total=1, payload={"failed_job_ids": ["job-1"], "max_jobs": 1})
    workflow_tasks.fail_task(task["id"], "详情页失败", "JD_DETAIL_FAILED", "重试详情页", retryable=True)

    retried = client.post(f"/api/jobs/enrich-jd/retry-failed/{task['id']}")

    assert retried.status_code == 200
    assert retried.json()["job_ids"] == ["job-1"]


def test_security_audit_includes_dependency_and_export_privacy(tmp_path, monkeypatch):
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    (tmp_path / "resumes").mkdir(parents=True)
    (tmp_path / "resumes" / "resume-1.json").write_text('{"profile":{"phone":"13800138000","email":"a@example.com"}}', encoding="utf-8")

    audit = client.get("/api/maintenance/security/audit").json()

    keys = {item["key"] for item in audit["checks"]}
    assert "dependency_audit" in keys
    assert "export_privacy_scan" in keys


def test_release_acceptance_suite_privacy_scan_and_version_snapshot(tmp_path, monkeypatch):
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    (tmp_path / "resumes").mkdir(parents=True)
    (tmp_path / "resumes" / "active.json").write_text(
        '{"name":"张三","phone":"13800138000","email":"user@example.com"}',
        encoding="utf-8",
    )

    suite = client.get("/api/maintenance/release/acceptance-suite").json()
    privacy = client.get("/api/maintenance/security/privacy-scan").json()
    snapshot = client.get("/api/maintenance/release/version-snapshot").json()

    assert suite["kind"] == "release_acceptance_suite"
    assert any(item["key"] == "core_flow" for item in suite["sections"])
    assert privacy["summary"]["hits"] == 1
    assert privacy["suggestions"]
    assert snapshot["kind"] == "release_version_snapshot"
    assert snapshot["version"]


def test_jobs_import_template_can_be_downloaded():
    response = client.get("/api/jobs/import-wizard/template")

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "title,company,city" in response.text


def test_greeting_recovery_panel_groups_failed_send_records(tmp_path, monkeypatch):
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    (tmp_path / "resumes").mkdir(parents=True)
    (tmp_path / "resumes" / "active.json").write_text('{"phone":"13800138000"}', encoding="utf-8")
    workflow_persistence.save_send_record("job-1", "blocked", "检测到验证码或页面风控", message="你好")
    workflow_persistence.save_send_record("job-2", "failed", "未找到发送按钮", message="你好")

    body = client.get("/api/greetings/recovery-panel").json()

    assert body["summary"]["failed"] == 2
    categories = {item["category"] for item in body["groups"]}
    assert {"risk_control", "page_changed"} <= categories


def test_cleanup_dry_run_previews_without_deleting_data(tmp_path, monkeypatch):
    from app.routes import jobs as jobs_route
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(jobs_route, "JOBS_FILE", tmp_path / "jobs" / "jobs.json")
    jobs_route._job_store.clear()
    jobs_route._job_store["old"] = JobRecord(id="old", title="产品经理", company="示例科技", lifecycle_status="suspected_expired")
    (tmp_path / "resumes").mkdir(parents=True)
    (tmp_path / "resumes" / "chat-old.json").write_text("{}", encoding="utf-8")

    preview = client.get("/api/maintenance/cleanup/dry-run").json()

    assert preview["kind"] == "cleanup_dry_run"
    assert preview["summary"]["expiredJobs"] == 1
    assert preview["summary"]["resumeChats"] == 1
    assert "old" in jobs_route._job_store


def test_diagnostic_center_unifies_core_failure_sources(tmp_path, monkeypatch):
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    (tmp_path / "resumes").mkdir(parents=True)
    (tmp_path / "resumes" / "active.json").write_text('{"phone":"13800138000"}', encoding="utf-8")
    workflow_persistence.save_send_record("job-1", "blocked", "检测到验证码或页面风控", message="你好")

    body = client.get("/api/maintenance/diagnostics/center").json()

    assert body["kind"] == "diagnostic_center"
    keys = {item["key"] for item in body["checks"]}
    assert {"boss_login", "business_api", "ai_provider", "pdf_visual", "greeting_recovery"} <= keys
    assert body["summary"]["total"] == len(body["checks"])
    actions = {item["key"]: item["repairAction"] for item in body["checks"]}
    assert actions["boss_login"]["type"] == "navigate"
    assert actions["boss_login"]["page"] == "jobs"
    assert actions["business_api"]["page"] == "settings"
    assert actions["greeting_recovery"]["page"] == "greeting"
    assert any(item["key"] == "privacy_scan" and item["repairAction"]["type"] == "export_redacted_backup" for item in body["repairActions"])


def test_release_check_suite_cleanup_confirm_and_release_record(tmp_path, monkeypatch):
    from app.routes import jobs as jobs_route
    from app.services import workflow_persistence, workflow_tasks

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(jobs_route, "JOBS_FILE", tmp_path / "jobs" / "jobs.json")
    monkeypatch.setattr(workflow_tasks, "TASKS_FILE", tmp_path / "workflow" / "tasks.json")
    jobs_route._job_store.clear()
    jobs_route._job_store["old"] = JobRecord(id="old", title="产品经理", company="示例科技", lifecycle_status="suspected_expired")
    (tmp_path / "resumes").mkdir(parents=True)
    (tmp_path / "resumes" / "chat-old.json").write_text("{}", encoding="utf-8")

    check = client.get("/api/maintenance/release/check-suite").json()
    cleaned = client.post("/api/maintenance/cleanup/confirm", json={"archive_expired_jobs": True, "archive_resume_chats": True}).json()
    record = client.post("/api/maintenance/release/records", json={
        "version": "0.9.1-test",
        "operator": "测试人员",
        "decision": "ready",
        "notes": ["测试发布记录"],
    }).json()
    records = client.get("/api/maintenance/release/records").json()

    assert check["kind"] == "release_check_suite"
    assert {"diagnostics", "privacy", "backup", "frontend", "backend", "playwright"} <= {item["key"] for item in check["checks"]}
    assert cleaned["kind"] == "cleanup_confirm_result"
    assert cleaned["archivedJobs"] == 1
    assert "old" not in jobs_route._job_store
    assert record["record"]["version"] == "0.9.1-test"
    assert record["record"]["checkSuite"]["kind"] == "release_check_suite"
    assert records["records"][0]["operator"] == "测试人员"


def test_help_center_exposes_module_guides_and_repair_actions():
    body = client.get("/api/help/center").json()

    assert body["kind"] == "help_center"
    modules = {item["key"]: item for item in body["modules"]}
    assert {"dashboard", "jobs", "diligence", "ranking", "greeting", "settings"} <= set(modules)
    assert modules["jobs"]["commonFailures"]
    assert modules["greeting"]["repairActions"]
    assert any(action["page"] == "settings" for action in modules["settings"]["repairActions"])
    assert body["quickStart"][0]["page"] in modules
    for module in modules.values():
        assert len(module["whenToUse"]) >= 2
        assert len(module["steps"]) >= 3
        assert module["goodSignals"]
        assert module["safetyNotes"]
    assert any(item["term"] == "灰度模式" for item in body["glossary"])
    assert any(item["page"] == "greeting" for item in body["faq"])


def test_launcher_preflight_script_reports_required_runtime():
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "launcher_preflight.py")],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "python" in result.stdout.lower()
    assert "pnpm" in result.stdout.lower()
