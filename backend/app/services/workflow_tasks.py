from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.services.workflow_persistence import DATA_DIR, _read_json, write_json_atomic


TASKS_FILE = DATA_DIR / "workflow" / "tasks.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_tasks(limit: int = 20) -> list[dict]:
    data = _read_json(TASKS_FILE, [])
    tasks = data if isinstance(data, list) else []
    return sorted(tasks, key=lambda item: item.get("updatedAt", ""), reverse=True)[:limit]


def _save_tasks(tasks: list[dict]) -> None:
    write_json_atomic(TASKS_FILE, tasks[-100:])


def start_task(task_type: str, title: str, total: int = 0, payload: dict | None = None) -> dict:
    tasks = load_tasks(limit=100)
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
        "createdAt": _now(),
        "updatedAt": _now(),
    }
    _save_tasks(tasks + [task])
    return task


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
