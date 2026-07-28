from fastapi import APIRouter, HTTPException, Response

from app.services import workflow_tasks
from app.services.system_health import run_health_check


router = APIRouter(prefix="/api/workflow", tags=["workflow"])


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


@router.post("/tasks/{task_id}/retry", status_code=202)
def retry_workflow_task(task_id: str, response: Response) -> dict:
    try:
        task, source = workflow_tasks.queue_retry_task(task_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="任务不存在")
    except PermissionError:
        raise HTTPException(status_code=409, detail="该任务不支持重试")
    response.status_code = 202
    return {"task": task, "sourceTask": source}
