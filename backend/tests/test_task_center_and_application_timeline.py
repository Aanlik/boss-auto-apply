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


def test_clear_failed_workflow_tasks_keeps_active_and_completed_tasks(tmp_path, monkeypatch):
    from app.services import workflow_persistence, workflow_tasks

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(workflow_tasks, "TASKS_FILE", tmp_path / "workflow" / "tasks.json")
    running = workflow_tasks.start_task("boss_capture", "抓取岗位", total=10)
    completed = workflow_tasks.start_task("ranking", "岗位评分", total=1)
    workflow_tasks.complete_task(completed["id"], done=1, message="已完成")
    failed = workflow_tasks.start_task("greeting_send", "自动打招呼", total=1)
    workflow_tasks.fail_task(failed["id"], "未找到立即沟通按钮", error_code="button_not_found", retryable=True)
    partial = workflow_tasks.start_task("jd_enrich", "JD 分析", total=3)
    workflow_tasks.partial_fail_task(partial["id"], done=1, total=3, message="部分 JD 缺失", error_code="missing_jd")

    response = client.delete("/api/workflow/tasks/failed")

    assert response.status_code == 200
    body = response.json()
    assert body["removed"] == 2
    assert body["remaining"] == 2
    task_ids = {task["id"] for task in workflow_tasks.load_tasks(limit=100)}
    assert running["id"] in task_ids
    assert completed["id"] in task_ids
    assert failed["id"] not in task_ids
    assert partial["id"] not in task_ids


def test_retry_unsupported_workflow_task_does_not_create_stuck_queue(tmp_path, monkeypatch):
    from app.services import workflow_persistence, workflow_tasks

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(workflow_tasks, "TASKS_FILE", tmp_path / "workflow" / "tasks.json")
    failed = workflow_tasks.start_task("unknown_module", "未知任务", total=1)
    workflow_tasks.fail_task(failed["id"], "暂不支持自动重试", error_code="unknown", retryable=True)

    response = client.post(f"/api/workflow/tasks/{failed['id']}/retry")

    assert response.status_code == 409
    tasks = workflow_tasks.load_tasks(limit=100)
    assert len(tasks) == 1
    assert tasks[0]["id"] == failed["id"]
    assert tasks[0]["status"] == "failed"


def test_delete_stuck_queued_workflow_task(tmp_path, monkeypatch):
    from app.services import workflow_persistence, workflow_tasks

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(workflow_tasks, "TASKS_FILE", tmp_path / "workflow" / "tasks.json")
    source = workflow_tasks.start_task("unknown_module", "源任务", total=1)
    workflow_tasks.fail_task(source["id"], "失败", retryable=True)
    queued, _ = workflow_tasks.queue_retry_task(source["id"])
    running = workflow_tasks.start_task("boss_capture", "抓取中", total=3)

    response = client.delete(f"/api/workflow/tasks/{queued['id']}")
    running_response = client.delete(f"/api/workflow/tasks/{running['id']}")

    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert running_response.status_code == 409
    task_ids = {task["id"] for task in workflow_tasks.load_tasks(limit=100)}
    assert queued["id"] not in task_ids
    assert source["id"] in task_ids
    assert running["id"] in task_ids


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
