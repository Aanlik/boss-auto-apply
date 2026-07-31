from fastapi import APIRouter, HTTPException, Response

from app.services import workflow_tasks
from app.services.system_health import run_health_check


router = APIRouter(prefix="/api/workflow", tags=["workflow"])
RETRY_EXECUTORS = {"greeting_send", "jd_enrich"}


@router.get("/tasks")
def list_workflow_tasks() -> dict:
    return {"tasks": workflow_tasks.load_tasks()}


@router.get("/center")
def workflow_center() -> dict:
    tasks = workflow_tasks.load_tasks(limit=100)
    running = [task for task in tasks if task.get("status") in {"queued", "running"}]
    recovery = [task for task in tasks if task.get("status") in {"failed", "partial_failed"}]
    retryable = [task for task in recovery if task.get("retryable")]
    completed = [task for task in tasks if task.get("status") == "completed"]
    attention = sorted(
        recovery,
        key=lambda item: (
            0 if item.get("retryable") else 1,
            str(item.get("updatedAt") or ""),
        ),
        reverse=True,
    )
    return {
        "summary": {
            "total": len(tasks),
            "running": len(running),
            "failed": len(recovery),
            "retryable": len(retryable),
            "completed": len(completed),
        },
        "running": running[:8],
        "recovery": attention[:8],
        "recoveryGroups": workflow_tasks.recovery_groups(recovery),
        "recoveryActions": _recovery_actions(workflow_tasks.recovery_groups(recovery)),
        "recent": tasks[:12],
    }


def _recovery_actions(groups: list[dict]) -> list[dict]:
    mapping = {
        "auth": {"label": "重新登录 BOSS", "page": "jobs", "action": "打开登录检查"},
        "risk_control": {"label": "暂停并人工检查", "page": "greeting", "action": "查看风控原因"},
        "network": {"label": "稍后重试", "page": "dashboard", "action": "刷新任务中心"},
        "page_changed": {"label": "检测页面可用性", "page": "greeting", "action": "运行选择器检查"},
        "data_missing": {"label": "补齐缺失数据", "page": "jobs", "action": "补 JD 或岗位链接"},
        "unknown": {"label": "查看详情", "page": "dashboard", "action": "查看任务详情"},
    }
    actions = []
    for index, group in enumerate(groups):
        config = mapping.get(group.get("category"), mapping["unknown"])
        actions.append({
            "category": group.get("category"),
            "label": config["label"],
            "page": config["page"],
            "action": config["action"],
            "count": group.get("count", 0),
            "retryable": group.get("retryable", 0),
            "taskIds": group.get("taskIds", []),
            "primary": index == 0,
        })
    return actions


@router.get("/recovery-summary")
def workflow_recovery_summary() -> dict:
    tasks = workflow_tasks.load_tasks(limit=100)
    recovery = [task for task in tasks if task.get("status") in {"failed", "partial_failed"}]
    return {
        "summary": {
            "failed": len(recovery),
            "retryable": sum(1 for task in recovery if task.get("retryable")),
        },
        "groups": workflow_tasks.recovery_groups(recovery),
        "generatedAt": workflow_tasks._now(),
    }


@router.get("/health-check")
def workflow_health_check() -> dict:
    return run_health_check()


@router.delete("/tasks/failed")
def clear_failed_workflow_tasks() -> dict:
    return workflow_tasks.clear_recovery_tasks()


@router.delete("/tasks/{task_id}")
def delete_workflow_task(task_id: str) -> dict:
    try:
        return workflow_tasks.delete_task(task_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="任务不存在")
    except PermissionError:
        raise HTTPException(status_code=409, detail="运行中的任务不能删除，请先终止或等待完成")


@router.post("/tasks/{task_id}/retry", status_code=202)
def retry_workflow_task(task_id: str, response: Response) -> dict:
    try:
        source = workflow_tasks.get_task(task_id)
        if not source:
            raise ValueError("task not found")
        if not source.get("retryable"):
            raise PermissionError("task is not retryable")
        if source.get("type") not in RETRY_EXECUTORS:
            raise NotImplementedError("task retry executor not found")
        task = workflow_tasks.restart_task(task_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="任务不存在")
    except PermissionError:
        raise HTTPException(status_code=409, detail="该任务不支持重试")
    except NotImplementedError:
        raise HTTPException(status_code=409, detail="该任务暂不支持自动重试，请处理后删除或清空")
    result = None
    try:
        if source.get("type") == "greeting_send":
            from app.routes.greetings import retry_failed_greetings

            result = retry_failed_greetings(task_id, reuse_task_id=task_id)
        elif source.get("type") == "jd_enrich":
            from app.routes.jobs import retry_failed_jd_details

            result = retry_failed_jd_details(task_id, reuse_task_id=task_id)
    except HTTPException as exc:
        workflow_tasks.fail_task(
            task_id,
            str(exc.detail),
            error_code="RETRY_FAILED",
            action="检查失败原因后再次重试",
        )
        raise
    except Exception as exc:
        workflow_tasks.fail_task(task_id, str(exc), error_code="RETRY_FAILED", action="检查失败原因后再次重试")
        raise HTTPException(status_code=500, detail=f"重试执行失败: {exc}")
    task = workflow_tasks.get_task(task_id) or task
    response.status_code = 202
    return {"task": task, "sourceTask": source, "result": result}


@router.get("/selection")
def get_selection() -> dict:
    from app.services.workflow_persistence import load_selection
    return {"selectedJobIds": load_selection()}


@router.post("/selection")
def save_selection(payload: dict) -> dict:
    from app.services.workflow_persistence import save_selection as _save
    ids = payload.get("selectedJobIds", [])
    if not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="selectedJobIds must be a list")
    return {"selectedJobIds": _save([str(i) for i in ids])}
