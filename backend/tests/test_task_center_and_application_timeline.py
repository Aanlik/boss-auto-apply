from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models.job import JobRecord


client = TestClient(app)


def test_workflow_center_groups_running_failed_and_retryable_tasks(tmp_path, monkeypatch):
    from app.services import workflow_persistence, workflow_tasks

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(workflow_tasks, "TASKS_FILE", tmp_path / "workflow" / "tasks.json")
    running = workflow_tasks.start_task("boss_capture", "抓取岗位", total=10)
    failed = workflow_tasks.start_task("diligence", "公司尽调", total=3)
    workflow_tasks.fail_task(failed["id"], "工商 API 限流", error_code="rate_limit", action="稍后重试", retryable=True)

    from app.routes.workflow import workflow_center
    body = workflow_center()

    assert body["summary"]["running"] == 1
    assert body["summary"]["failed"] == 1
    assert body["summary"]["retryable"] == 1
    assert body["running"][0]["id"] == running["id"]
    assert body["recovery"][0]["id"] == failed["id"]


def test_application_timeline_aggregates_recent_job_status_history(monkeypatch):
    import app.routes.jobs as jobs_route

    jobs_route._job_store.clear()
    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        application_status="interviewing",
        status_history=[
            {"kind": "application", "status": "greeted", "previous": "pending", "note": "已打招呼", "at": "2026-07-20T10:00:00"},
            {"kind": "application", "status": "interviewing", "previous": "applied", "note": "约一面", "at": "2026-07-22T10:00:00"},
        ],
    )
    jobs_route._job_store["job-2"] = JobRecord(id="job-2", title="后端", company="另一家公司")

    body = jobs_route.application_timeline()

    assert body["summary"]["interviewing"] == 1
    assert body["events"][0]["jobId"] == "job-1"
    assert body["events"][0]["status"] == "interviewing"
    assert body["events"][0]["company"] == "示例科技"


def test_workflow_recovery_actions_are_button_ready(tmp_path, monkeypatch):
    from app.services import workflow_persistence, workflow_tasks

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(workflow_tasks, "TASKS_FILE", tmp_path / "workflow" / "tasks.json")
    task = workflow_tasks.start_task("greeting_send", "自动打招呼", total=1)
    workflow_tasks.fail_task(task["id"], "未登录", error_code="not_logged_in", retryable=True)

    from app.routes.workflow import workflow_center
    body = workflow_center()

    action = body["recoveryActions"][0]
    assert action["label"] == "重新登录 BOSS"
    assert action["page"] == "jobs"
    assert action["primary"] is True


def test_application_crm_board_groups_jobs_by_status(monkeypatch):
    import app.routes.jobs as jobs_route

    jobs_route._job_store.clear()
    jobs_route._job_store["job-1"] = JobRecord(id="job-1", title="产品经理", company="示例科技", application_status="greeted")
    jobs_route._job_store["job-2"] = JobRecord(id="job-2", title="后端", company="技术公司", application_status="interviewing")

    body = jobs_route.application_crm_board()

    assert body["summary"]["total"] == 2
    assert body["columns"]["greeted"]["count"] == 1
    assert body["columns"]["interviewing"]["jobs"][0]["company"] == "技术公司"


def test_application_board_move_updates_status_and_refreshes_board(monkeypatch):
    import app.routes.jobs as jobs_route

    jobs_route._job_store.clear()
    jobs_route._job_store["job-1"] = JobRecord(id="job-1", title="产品经理", company="示例科技", application_status="pending")

    response = client.post("/api/jobs/application-board/move", json={"job_id": "job-1", "status": "interviewing", "note": "CRM 看板拖拽"})

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == "job-1"
    assert body["application_status"] == "interviewing"
    assert body["board"]["columns"]["interviewing"]["count"] == 1
    assert jobs_route._job_store["job-1"].status_history[-1]["note"] == "CRM 看板拖拽"
