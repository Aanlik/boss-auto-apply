from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models.job import JobRecord


client = TestClient(app)


def test_full_backup_export_restore_and_event_log(tmp_path, monkeypatch):
    from app.services import workflow_persistence as persistence

    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)
    source = tmp_path / "diligence" / "示例科技.json"
    source.parent.mkdir(parents=True)
    source.write_text('{"companyName":"示例科技"}', encoding="utf-8")

    exported = client.get("/api/maintenance/backup/export").json()

    assert exported["kind"] == "full_workspace_backup"
    assert exported["version"] == 1
    assert any(item["path"] == "diligence/示例科技.json" for item in exported["files"])

    source.unlink()
    restored = client.post("/api/maintenance/backup/import", json=exported)
    logs = client.get("/api/maintenance/logs?level=info").json()

    assert restored.status_code == 200
    assert restored.json()["restored"] >= 1
    assert source.exists()
    assert logs["events"]
    assert logs["events"][0]["category"] in {"backup", "restore"}


def test_retention_preview_and_cleanup_archives_expired_jobs(tmp_path, monkeypatch):
    import app.routes.jobs as jobs_route
    from app.services import workflow_persistence as persistence
    from app.services import workflow_tasks

    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(workflow_tasks, "TASKS_FILE", tmp_path / "workflow" / "tasks.json")
    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-old": JobRecord(id="job-old", title="旧岗位", company="示例科技", lifecycle_status="suspected_expired"),
        "job-active": JobRecord(id="job-active", title="新岗位", company="示例科技", lifecycle_status="active"),
    })
    workflow_tasks.start_task("ranking", "排序", payload={"x": 1})

    preview = client.get("/api/maintenance/retention/preview").json()
    cleaned = client.post("/api/maintenance/retention/cleanup", json={"archive_expired_jobs": True}).json()

    assert preview["expiredJobs"] == 1
    assert cleaned["archivedJobs"] == 1
    assert "job-old" not in jobs_route._job_store
    assert "job-active" in jobs_route._job_store
    assert (tmp_path / "archive" / "jobs.json").exists()


def test_dashboard_summary_combines_flow_metrics(monkeypatch):
    import app.routes.jobs as jobs_route
    from app.services import workflow_persistence as persistence

    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(id="job-1", title="产品经理", company="示例科技", jd_text="", decision_status="recommended"),
        "job-2": JobRecord(id="job-2", title="运营", company="风险科技", jd_text="岗位职责", decision_status="risky"),
    })
    monkeypatch.setattr(persistence, "load_diligence_reports", lambda: {"示例科技": {"companyName": "示例科技"}})
    monkeypatch.setattr(persistence, "load_rankings", lambda: [{"jobId": "job-1", "recommendation": "recommend"}])

    response = client.get("/api/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["jobs"]["total"] == 2
    assert body["jobs"]["missingJd"] == 1
    assert body["diligence"]["pendingCompanies"] == 1
    assert body["decisions"]["recommended"] == 1
    assert body["decisions"]["risky"] == 1
    assert body["readiness"]["stage"] == "complete_jd"
    assert body["readiness"]["nextAction"]["page"] == "jobs"
    assert body["readiness"]["nextAction"]["label"] == "补齐 JD 详情"
    assert body["readiness"]["blockers"][0]["key"] == "missing_jd"


def test_dashboard_summary_guides_empty_workspace_to_first_setup(monkeypatch):
    import app.routes.jobs as jobs_route
    from app.services import workflow_persistence as persistence

    monkeypatch.setattr(jobs_route, "_job_store", {})
    monkeypatch.setattr(persistence, "load_diligence_reports", lambda: {})
    monkeypatch.setattr(persistence, "load_rankings", lambda: [])

    body = client.get("/api/dashboard/summary").json()

    assert body["readiness"]["stage"] == "setup"
    assert body["readiness"]["nextAction"] == {
        "label": "完成基础配置并抓取第一批岗位",
        "page": "jobs",
        "reason": "岗位池为空，先登录 BOSS、配置 API 后抓取岗位。",
    }
    assert body["readiness"]["qualityScore"] < 50


def test_job_search_presets_crud(tmp_path, monkeypatch):
    import app.routes.jobs as jobs_route

    monkeypatch.setattr(jobs_route, "SEARCH_PRESETS_FILE", tmp_path / "search_presets.json")

    created = client.post("/api/jobs/search-presets", json={
        "name": "上海产品经理",
        "keyword": "产品经理",
        "city": "上海",
        "max_pages": 3,
        "filters": {"salary": "405"},
        "job_filters": {"application_status": "pending"},
    })
    listed = client.get("/api/jobs/search-presets")
    deleted = client.delete(f"/api/jobs/search-presets/{created.json()['preset']['id']}")

    assert created.status_code == 200
    assert created.json()["preset"]["name"] == "上海产品经理"
    assert listed.json()["presets"][0]["filters"]["salary"] == "405"
    assert deleted.json()["deleted"] == created.json()["preset"]["id"]


def test_storage_migration_status_exposes_sqlite_path(tmp_path, monkeypatch):
    from app.services import workflow_persistence as persistence

    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)

    response = client.get("/api/maintenance/storage")

    assert response.status_code == 200
    body = response.json()
    assert body["activeStore"] == "json"
    assert body["sqlite"]["path"].endswith("boss_workbench.sqlite3")
