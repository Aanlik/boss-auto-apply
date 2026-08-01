from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.services.workflow_persistence import DATA_DIR, _read_json, write_json_atomic


TASKS_FILE = DATA_DIR / "workflow" / "tasks.json"
FAILURE_CATEGORIES = {
    "auth": {
        "label": "登录或凭据",
        "action": "重新登录 BOSS 或检查 API Key 后重试",
        "codes": {"not_logged_in", "cookie_expired", "auth_failed", "unauthorized", "forbidden"},
    },
    "risk_control": {
        "label": "页面风控",
        "action": "暂停自动化，人工打开页面确认验证码或风控提示",
        "codes": {"risk_control", "captcha", "rate_limited"},
    },
    "network": {
        "label": "网络或供应商",
        "action": "检查网络和供应商状态，稍后重试",
        "codes": {"network_error", "timeout", "provider_error", "browser_start_failed", "browser_error"},
    },
    "page_changed": {
        "label": "页面结构变化",
        "action": "运行页面可用性检测，确认按钮和输入框是否变化",
        "codes": {"page_changed", "button_not_found", "input_not_found", "send_button_not_found", "page_script_failed", "page_script_invalid"},
    },
    "data_missing": {
        "label": "数据缺失",
        "action": "补齐 JD、岗位链接、工商信息或简历后重试",
        "codes": {"missing_job_url", "empty_message", "missing_jd", "missing_resume", "validation_failed"},
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify_failure(task: dict) -> dict:
    code = str(task.get("errorCode") or task.get("failureCode") or "").strip()
    message = str(task.get("message") or "").lower()
    task_type = str(task.get("type") or "").lower()
    for key, config in FAILURE_CATEGORIES.items():
        if code in config["codes"]:
            return {
                "category": key,
                "label": config["label"],
                "action": task.get("action") or config["action"],
            }
    if any(word in message for word in ("登录", "cookie", "unauthorized", "forbidden")):
        key = "auth"
    elif any(word in message for word in ("验证码", "风控", "频率", "risk", "captcha")):
        key = "risk_control"
    elif any(word in message for word in ("网络", "timeout", "超时", "连接")):
        key = "network"
    elif any(word in message for word in ("按钮", "输入框", "页面", "selector")) or "boss" in task_type:
        key = "page_changed"
    elif any(word in message for word in ("缺少", "为空", "校验")):
        key = "data_missing"
    else:
        return {
            "category": "unknown",
            "label": "其他失败",
            "action": task.get("action") or "查看任务详情并按提示处理",
        }
    config = FAILURE_CATEGORIES[key]
    return {
        "category": key,
        "label": config["label"],
        "action": task.get("action") or config["action"],
    }


def recovery_groups(tasks: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for task in tasks:
        if task.get("status") not in {"failed", "partial_failed"}:
            continue
        classified = classify_failure(task)
        key = classified["category"]
        group = grouped.setdefault(key, {
            "category": key,
            "label": classified["label"],
            "count": 0,
            "retryable": 0,
            "action": classified["action"],
            "taskIds": [],
        })
        group["count"] += 1
        if task.get("retryable"):
            group["retryable"] += 1
        group["taskIds"].append(task.get("id"))
    return sorted(grouped.values(), key=lambda item: (item["retryable"], item["count"]), reverse=True)


def load_tasks(limit: int = 20) -> list[dict]:
    data = _read_json(TASKS_FILE, [])
    tasks = data if isinstance(data, list) else []
    return sorted(tasks, key=lambda item: item.get("updatedAt", ""), reverse=True)[:limit]


def _save_tasks(tasks: list[dict]) -> None:
    write_json_atomic(TASKS_FILE, tasks[-100:])


def start_task(
    task_type: str,
    title: str,
    total: int = 0,
    payload: dict | None = None,
    idempotency_key: str = "",
) -> dict:
    tasks = load_tasks(limit=100)
    if idempotency_key:
        for existing in tasks:
            if (
                existing.get("idempotencyKey") == idempotency_key
                and existing.get("status") in {"queued", "running"}
            ):
                return existing
    task = {
        "id": uuid4().hex,
        "type": task_type,
        "title": title,
        "status": "running",
        "done": 0,
        "total": max(0, int(total or 0)),
        "message": "",
        "errorCode": "",
        "action": "",
        "retryable": False,
        "payload": payload or {},
        "idempotencyKey": idempotency_key,
        "createdAt": _now(),
        "updatedAt": _now(),
    }
    _save_tasks(tasks + [task])
    return task


def get_task(task_id: str) -> dict | None:
    for task in load_tasks(limit=100):
        if task.get("id") == task_id:
            return task
    return None


def find_running_task(idempotency_key: str) -> dict | None:
    if not idempotency_key:
        return None
    return next(
        (
            task
            for task in load_tasks(limit=100)
            if task.get("idempotencyKey") == idempotency_key
            and task.get("status") in {"queued", "running"}
        ),
        None,
    )


def restart_task(task_id: str) -> dict:
    """Reuse a failed task record for a new execution attempt."""
    task = get_task(task_id)
    if not task:
        raise ValueError("task not found")
    if not task.get("retryable"):
        raise PermissionError("task is not retryable")
    return update_task(
        task_id,
        status="running",
        done=0,
        message="正在重试",
        errorCode="",
        action="",
        retryable=False,
    )


def clear_recovery_tasks() -> dict:
    tasks = load_tasks(limit=100)
    remaining = [task for task in tasks if task.get("status") not in {"failed", "partial_failed"}]
    removed = len(tasks) - len(remaining)
    _save_tasks(remaining)
    return {"removed": removed, "remaining": len(remaining)}


def delete_task(task_id: str) -> dict:
    tasks = load_tasks(limit=100)
    target = next((task for task in tasks if task.get("id") == task_id), None)
    if not target:
        raise ValueError("task not found")
    if target.get("status") == "running":
        raise PermissionError("running task cannot be deleted")
    remaining = [task for task in tasks if task.get("id") != task_id]
    _save_tasks(remaining)
    return {"deleted": True, "task": target, "remaining": len(remaining)}


def update_task(task_id: str, **updates) -> dict:
    tasks = load_tasks(limit=100)
    for task in tasks:
        if task.get("id") == task_id:
            task.update(updates)
            task["updatedAt"] = _now()
            _save_tasks(tasks)
            return task
    raise ValueError("task not found")


def complete_task(task_id: str, done: int | None = None, message: str = "") -> dict:
    updates = {"status": "completed", "message": message, "action": "", "retryable": False}
    if done is not None:
        updates["done"] = done
    return update_task(task_id, **updates)


def partial_fail_task(task_id: str, done: int, total: int, message: str, error_code: str = "", action: str = "") -> dict:
    return update_task(
        task_id,
        status="partial_failed",
        done=max(0, int(done or 0)),
        total=max(0, int(total or 0)),
        message=message,
        errorCode=error_code,
        action=action,
        retryable=True,
    )


def fail_task(task_id: str, message: str, error_code: str = "", action: str = "", retryable: bool = True) -> dict:
    return update_task(
        task_id,
        status="failed",
        message=message,
        errorCode=error_code,
        action=action,
        retryable=retryable,
    )
