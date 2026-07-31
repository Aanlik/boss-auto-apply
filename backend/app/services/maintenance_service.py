from __future__ import annotations

import base64
import importlib.util
import json
import re
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.services import workflow_persistence
from app.services.system_health import run_health_check
from app.services.workflow_persistence import _read_json, write_json_atomic


BACKUP_TEXT_SUFFIXES = {".json", ".txt", ".md", ".csv", ".log", ".jsonl"}
SENSITIVE_FIELD_PARTS = {
    "api_key",
    "apikey",
    "secret",
    "secret_id",
    "secret_key",
    "token",
    "password",
    "credential",
}
PRIVACY_FIELD_PARTS = {
    "phone",
    "mobile",
    "email",
    "id_card",
    "idcard",
    "wechat",
}
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")



def _now() -> str:
    return datetime.now(timezone.utc).isoformat()



def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)



def _within_days(value: Any, days: int) -> bool:
    parsed = _parse_time(value)
    if not parsed:
        return False
    return parsed >= datetime.now(timezone.utc) - timedelta(days=max(1, int(days or 7)))



def data_dir() -> Path:
    return workflow_persistence.DATA_DIR



def storage_config_file() -> Path:
    return data_dir() / "storage" / "config.json"



def active_store() -> str:
    cfg = _read_json(storage_config_file(), {})
    store = str((cfg if isinstance(cfg, dict) else {}).get("activeStore") or "json").lower()
    return "sqlite" if store == "sqlite" else "json"



def _safe_relative_path(value: str) -> Path:
    rel = Path(str(value or ""))
    if rel.is_absolute() or ".." in rel.parts or not str(rel):
        raise ValueError("invalid backup path")
    return rel



def log_event(level: str, category: str, message: str, detail: dict | None = None) -> dict:
    event = {
        "id": f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        "time": _now(),
        "level": level if level in {"info", "warning", "error"} else "info",
        "category": category,
        "message": message,
        "detail": detail or {},
    }
    path = data_dir() / "logs" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    if active_store() == "sqlite":
        from app.services import sqlite_kv_store
        sqlite_kv_store.put("maintenance_events", event["id"], event)
    return event



def list_events(level: str = "", limit: int = 50) -> list[dict]:
    if active_store() == "sqlite":
        from app.services import sqlite_kv_store
        rows = list(sqlite_kv_store.all("maintenance_events").values())
        if rows:
            filtered = [item for item in rows if isinstance(item, dict) and (not level or item.get("level") == level)]
            return sorted(filtered, key=lambda item: item.get("time", ""), reverse=True)[: max(1, min(int(limit or 50), 200))]
    path = data_dir() / "logs" / "events.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if level and item.get("level") != level:
            continue
        rows.append(item)
    return list(reversed(rows))[: max(1, min(int(limit or 50), 200))]



def log_api_call(category: str, method: str, url: str, status_code: int, duration_ms: int, detail: dict | None = None) -> dict:
    item = {
        "id": f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        "time": _now(),
        "category": category,
        "method": method,
        "url": url,
        "statusCode": int(status_code or 0),
        "durationMs": int(duration_ms or 0),
        "detail": detail or {},
    }
    path = data_dir() / "logs" / "api_calls.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    if active_store() == "sqlite":
        from app.services import sqlite_kv_store
        sqlite_kv_store.put("api_calls", item["id"], item)
    return item



def list_api_calls(category: str = "", limit: int = 100) -> list[dict]:
    if active_store() == "sqlite":
        from app.services import sqlite_kv_store
        rows = list(sqlite_kv_store.all("api_calls").values())
        if rows:
            filtered = [item for item in rows if isinstance(item, dict) and (not category or item.get("category") == category)]
            return sorted(filtered, key=lambda item: item.get("time", ""), reverse=True)[: max(1, min(int(limit or 100), 500))]
    path = data_dir() / "logs" / "api_calls.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if category and item.get("category") != category:
            continue
        rows.append(item)
    return list(reversed(rows))[: max(1, min(int(limit or 100), 500))]



def storage_status() -> dict:
    from app.services import sqlite_kv_store

    sqlite_path = data_dir() / "boss_workbench.sqlite3"
    store = active_store()
    if sqlite_path.exists():
        lifecycle = {
            "schemaVersion": sqlite_kv_store.schema_status()["version"],
            "targetSchemaVersion": sqlite_kv_store.CURRENT_SCHEMA_VERSION,
            "integrity": sqlite_kv_store.integrity_check(),
            "backups": sqlite_kv_store.list_backups(),
        }
    else:
        lifecycle = {
            "schemaVersion": 0,
            "targetSchemaVersion": sqlite_kv_store.CURRENT_SCHEMA_VERSION,
            "integrity": {"status": "missing", "message": "SQLite 数据库尚未创建"},
            "backups": [],
        }
    return {
        "activeStore": store,
        "json": {"path": str(data_dir()), "ready": data_dir().exists()},
        "sqlite": {
            "path": str(sqlite_path),
            "exists": sqlite_path.exists(),
            "migrationReady": True,
            "message": "当前岗位池主读写使用 SQLite。" if store == "sqlite" else "当前仍使用 JSON 存储；可执行 SQLite 快照迁移并支持回滚。",
            **lifecycle,
        },
    }



def set_primary_storage(active_store_name: str) -> dict:
    store = str(active_store_name or "").lower().strip()
    if store not in {"json", "sqlite"}:
        raise ValueError("active_store must be json or sqlite")
    write_json_atomic(storage_config_file(), {"activeStore": store, "updatedAt": _now()})
    if store == "sqlite":
        from app.routes import jobs as jobs_route
        from app.services import job_sqlite_store

        job_sqlite_store.save_jobs(jobs_route._job_store)
    log_event("info", "storage", f"主存储已切换为 {store}", {"activeStore": store})
    return storage_status()



def weekly_report(days: int = 7) -> dict[str, Any]:
    from app.routes import jobs as jobs_route
    from app.services import workflow_tasks

    window_days = max(1, min(int(days or 7), 30))
    jobs = jobs_route._all_jobs()
    reports = workflow_persistence.load_diligence_reports()
    send_records = workflow_persistence.load_send_records()
    tasks = workflow_tasks.load_tasks(limit=100)
    status_events = []
    for job in jobs:
        for entry in job.status_history or []:
            if not _within_days(entry.get("at"), window_days):
                continue
            status_events.append({
                "jobId": job.id,
                "title": job.title,
                "company": job.company,
                "status": entry.get("status") or "",
                "kind": entry.get("kind") or "",
                "at": entry.get("at") or "",
            })
    application_events = [item for item in status_events if item["kind"] == "application"]
    contacted = sum(1 for item in application_events if item["status"] in {"greeted", "applied", "interviewing"})
    interviewing = sum(1 for item in application_events if item["status"] == "interviewing")
    rejected = sum(1 for item in application_events if item["status"] == "rejected")
    sent = sum(1 for record in send_records if record.get("status") == "sent" and _within_days(record.get("updatedAt"), window_days))
    captured = sum(1 for job in jobs if _within_days(job.captured_at or job.fetched_at, window_days))
    jd_ready = sum(1 for job in jobs if (job.jd_text or "").strip() and _within_days(job.fetched_at or job.captured_at, window_days))
    diligence_done = sum(1 for report in reports.values() if isinstance(report, dict) and _within_days(report.get("completedAt"), window_days))
    failed_tasks = [task for task in tasks if task.get("status") in {"failed", "partial_failed"} and _within_days(task.get("updatedAt"), window_days)]
    recommendations: list[str] = []
    if captured == 0:
        recommendations.append("本周没有新增岗位，建议补充 1-2 组关键词或城市继续扩池。")
    if captured and jd_ready < captured:
        recommendations.append(f"本周新增岗位中还有 {captured - jd_ready} 个缺少 JD，建议先补详情再排序。")
    if sent and interviewing == 0:
        recommendations.append("已有触达但暂无面试推进，建议复盘招呼语和岗位匹配度。")
    if rejected > interviewing:
        recommendations.append("拒绝数高于面试推进，建议收紧筛选条件或调整简历关键词。")
    if failed_tasks:
        recommendations.append(f"本周有 {len(failed_tasks)} 个失败任务，建议先处理恢复中心再继续批量操作。")
    return {
        "windowDays": window_days,
        "range": {
            "from": (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat(),
            "to": _now(),
        },
        "summary": {
            "capturedJobs": captured,
            "jdReady": jd_ready,
            "diligenceDone": diligence_done,
            "greetingsSent": sent,
            "contacted": contacted,
            "interviewing": interviewing,
            "rejected": rejected,
            "failedTasks": len(failed_tasks),
        },
        "conversion": {
            "jdReadyRate": round(jd_ready / captured * 100) if captured else 0,
            "interviewRate": round(interviewing / max(1, contacted or sent) * 100),
            "rejectionRate": round(rejected / max(1, contacted or sent) * 100),
        },
        "failureGroups": workflow_tasks.recovery_groups(failed_tasks),
        "recentEvents": sorted(status_events, key=lambda item: item.get("at") or "", reverse=True)[:10],
        "recommendations": recommendations or ["本周流程整体健康，可以继续围绕推荐岗位推进触达和面试准备。"],
        "generatedAt": _now(),
    }



def _date_key(value: Any) -> str:
    parsed = _parse_time(value) or datetime.now(timezone.utc)
    return parsed.date().isoformat()



def _empty_day_series(window_days: int) -> list[dict[str, Any]]:
    today = datetime.now(timezone.utc).date()
    return [
        {
            "date": (today - timedelta(days=offset)).isoformat(),
            "capturedJobs": 0,
            "jdReady": 0,
            "diligenceDone": 0,
            "greetingsSent": 0,
            "replies": 0,
            "positiveReplies": 0,
            "interviewing": 0,
        }
        for offset in range(window_days - 1, -1, -1)
    ]



def trend_report(days: int = 30) -> dict[str, Any]:
    from app.routes import jobs as jobs_route
    from app.routes import greetings as greetings_route

    window_days = max(1, min(int(days or 30), 90))
    series = _empty_day_series(window_days)
    by_day = {item["date"]: item for item in series}
    jobs = jobs_route._all_jobs()
    reports = workflow_persistence.load_diligence_reports()
    send_records = workflow_persistence.load_send_records()
    replies = greetings_route._load_reply_records()

    for job in jobs:
        captured_at = job.captured_at or job.fetched_at
        if _within_days(captured_at, window_days):
            bucket = by_day.get(_date_key(captured_at))
            if bucket is not None:
                bucket["capturedJobs"] += 1
                if (job.jd_text or "").strip():
                    bucket["jdReady"] += 1
        for entry in job.status_history or []:
            if entry.get("kind") == "application" and entry.get("status") == "interviewing" and _within_days(entry.get("at"), window_days):
                bucket = by_day.get(_date_key(entry.get("at")))
                if bucket is not None:
                    bucket["interviewing"] += 1

    for report in reports.values():
        if isinstance(report, dict) and _within_days(report.get("completedAt") or report.get("generatedAt"), window_days):
            bucket = by_day.get(_date_key(report.get("completedAt") or report.get("generatedAt")))
            if bucket is not None:
                bucket["diligenceDone"] += 1

    for record in send_records:
        if record.get("status") == "sent" and _within_days(record.get("updatedAt"), window_days):
            bucket = by_day.get(_date_key(record.get("updatedAt")))
            if bucket is not None:
                bucket["greetingsSent"] += 1

    for reply in replies:
        created_at = reply.get("createdAt") or reply.get("updatedAt")
        if _within_days(created_at, window_days):
            bucket = by_day.get(_date_key(created_at))
            if bucket is not None:
                bucket["replies"] += 1
                if reply.get("replyType") == "positive":
                    bucket["positiveReplies"] += 1

    totals = {
        "capturedJobs": sum(item["capturedJobs"] for item in series),
        "jdReady": sum(item["jdReady"] for item in series),
        "diligenceDone": sum(item["diligenceDone"] for item in series),
        "greetingsSent": sum(item["greetingsSent"] for item in series),
        "replies": sum(item["replies"] for item in series),
        "positiveReplies": sum(item["positiveReplies"] for item in series),
        "interviewing": sum(item["interviewing"] for item in series),
    }
    return {
        "windowDays": window_days,
        "series": series,
        "summary": {
            **totals,
            "jdReadyRate": round(totals["jdReady"] / totals["capturedJobs"] * 100) if totals["capturedJobs"] else 0,
            "replyRate": round(totals["replies"] / totals["greetingsSent"] * 100) if totals["greetingsSent"] else 0,
            "positiveReplyRate": round(totals["positiveReplies"] / totals["greetingsSent"] * 100) if totals["greetingsSent"] else 0,
            "interviewRate": round(totals["interviewing"] / max(1, totals["greetingsSent"]) * 100),
        },
        "generatedAt": _now(),
    }



def _quality_action(key: str, label: str, page: str, reason: str, count: int, severity: str = "warn") -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "count": count,
        "severity": severity if severity in {"info", "warn", "error"} else "warn",
        "page": page,
        "action": label,
        "reason": reason,
    }



def data_quality_center() -> dict[str, Any]:
    from app.routes import jobs as jobs_route

    jobs = jobs_route._all_jobs()
    rankings = workflow_persistence.load_rankings()
    ranked_ids = {str(item.get("jobId") or item.get("job_id") or "") for item in rankings if isinstance(item, dict)}
    seen: set[tuple[str, str, str]] = set()
    duplicate_ids: set[str] = set()
    for job in jobs:
        key = ((job.company or "").strip(), (job.title or "").strip(), (job.city or "").strip())
        if key in seen:
            duplicate_ids.add(job.id)
        else:
            seen.add(key)
    missing_jd = [job for job in jobs if not ((job.jd_text or "").strip() and (getattr(job, "jd_detail_fetched_at", "") or "").strip())]
    low_quality_jd = [
        job for job in jobs
        if (job.jd_text or "").strip()
        and (getattr(job, "jd_detail_fetched_at", "") or "").strip()
        and len((job.jd_text or "").strip()) < 80
    ]
    suspected_expired = [job for job in jobs if job.lifecycle_status == "suspected_expired"]
    blacklisted = [job for job in jobs if job.lifecycle_status == "blacklisted"]
    missing_business_name = [
        job for job in jobs
        if not (str(getattr(job, "company_key", "") or "").strip()) and "有限公司" not in (job.company or "")
    ]
    no_rankings = [job for job in jobs if job.id not in ranked_ids]
    checks = [
        _quality_action("missing_jd", "补齐 JD", "jobs", "缺少 JD 会影响简历匹配、排序和招呼语质量。", len(missing_jd), "error"),
        _quality_action("duplicate_jobs", "治理重复岗位", "jobs", "重复岗位会干扰排序和投递统计。", len(duplicate_ids), "warn"),
        _quality_action("suspected_expired", "复核疑似过期", "jobs", "疑似过期岗位建议确认后保留、归档或删除。", len(suspected_expired), "warn"),
        _quality_action("blacklisted", "复核黑名单岗位", "jobs", "黑名单岗位不会进入推荐流程，建议定期确认名单。", len(blacklisted), "warn"),
        _quality_action("missing_business_name", "补工商名称", "diligence", "缺少工商注册名称会降低公司尽调和黑名单命中准确度。", len(missing_business_name), "warn"),
        _quality_action("low_quality_jd", "清理 JD 噪音", "jobs", "过短或噪音较重的 JD 会让 AI 判断失真。", len(low_quality_jd), "warn"),
        _quality_action("no_rankings", "重新排序", "ranking", "未进入排序的岗位无法参与最终投递优先级。", len(no_rankings), "info"),
    ]
    issue_count = sum(item["count"] for item in checks)
    return {
        "summary": {
            "totalJobs": len(jobs),
            "issues": issue_count,
            "errors": sum(item["count"] for item in checks if item["severity"] == "error"),
            "warnings": sum(item["count"] for item in checks if item["severity"] == "warn"),
            "score": max(0, 100 - sum(item["count"] * (12 if item["severity"] == "error" else 6) for item in checks)),
        },
        "checks": checks,
        "generatedAt": _now(),
    }



def repair_data_quality(actions: list[str] | None = None) -> dict[str, Any]:
    from app.routes import jobs as jobs_route

    selected = set(actions or [])
    if not selected:
        selected = {"tag_missing_jd", "tag_low_quality_jd", "tag_suspected_expired"}
    updated = 0
    details: list[dict[str, Any]] = []
    for job in jobs_route._all_jobs():
        before = set(job.tags or [])
        if "tag_missing_jd" in selected and not (job.jd_text or "").strip():
            before.add("缺少JD")
        if "tag_low_quality_jd" in selected and (job.jd_text or "").strip() and len((job.jd_text or "").strip()) < 80:
            before.add("JD待清理")
        if "tag_suspected_expired" in selected and job.lifecycle_status == "suspected_expired":
            before.add("疑似过期")
        next_tags = list(before)
        if next_tags != (job.tags or []):
            job.tags = next_tags
            updated += 1
            details.append({"jobId": job.id, "company": job.company, "title": job.title, "tags": job.tags})
    if updated:
        jobs_route._save_jobs()
        log_event("info", "data_quality", f"数据质量一键修复更新 {updated} 个岗位", {"actions": sorted(selected), "updated": updated})
    return {"updated": updated, "actions": sorted(selected), "details": details[:50], "quality": data_quality_center()}



def dashboard_summary() -> dict[str, Any]:
    from app.routes import jobs as jobs_route
    from app.services import workflow_persistence as persistence

    jobs = jobs_route._all_jobs()
    companies = {job.company for job in jobs if job.company}
    reports = persistence.load_diligence_reports()
    report_keys = set(reports.keys())
    rankings = persistence.load_rankings()
    jobs_summary = {
        "total": len(jobs),
        "missingJd": sum(1 for job in jobs if not (job.jd_text or "").strip()),
        "withJd": sum(1 for job in jobs if (job.jd_text or "").strip()),
        "suspectedExpired": sum(1 for job in jobs if job.lifecycle_status == "suspected_expired"),
        "blacklisted": sum(1 for job in jobs if job.lifecycle_status == "blacklisted"),
    }
    diligence_summary = {
        "completedCompanies": len(report_keys),
        "pendingCompanies": len([company for company in companies if company not in report_keys]),
    }
    ranking_summary = {
        "total": len(rankings),
        "recommended": sum(1 for item in rankings if item.get("recommendation") in {"strong", "recommend"}),
    }
    decisions_summary = {
        "recommended": sum(1 for job in jobs if job.decision_status == "recommended"),
        "watching": sum(1 for job in jobs if job.decision_status == "watching"),
        "risky": sum(1 for job in jobs if job.decision_status == "risky"),
        "abandoned": sum(1 for job in jobs if job.decision_status == "abandoned"),
    }
    return {
        "jobs": {
            **jobs_summary,
        },
        "diligence": {
            **diligence_summary,
        },
        "ranking": {
            **ranking_summary,
        },
        "decisions": {
            **decisions_summary,
        },
        "readiness": _dashboard_readiness(jobs_summary, diligence_summary, ranking_summary, decisions_summary),
        "generatedAt": _now(),
    }



def onboarding_guide() -> dict[str, Any]:
    summary = dashboard_summary()
    steps = [
        {
            "key": "configure",
            "label": "完成基础配置",
            "page": "settings",
            "status": "done" if summary["jobs"]["total"] > 0 or summary["diligence"]["completedCompanies"] > 0 else "todo",
            "reason": "配置 AI、搜索和工商 API 后，后续建议更完整。",
            "action": "打开设置",
        },
        {
            "key": "capture_jobs",
            "label": "抓取第一批岗位",
            "page": "jobs",
            "status": "done" if summary["jobs"]["total"] > 0 else "todo",
            "reason": "岗位池是尽调、排序和招呼语的基础。",
            "action": "去抓取",
        },
        {
            "key": "complete_jd",
            "label": "补齐 JD 详情",
            "page": "jobs",
            "status": "done" if summary["jobs"]["total"] > 0 and summary["jobs"]["missingJd"] == 0 else "todo",
            "reason": "JD 完整度会影响简历匹配和 AI 建议。",
            "action": "补 JD",
        },
        {
            "key": "diligence",
            "label": "完成公司尽调",
            "page": "diligence",
            "status": "done" if summary["diligence"]["pendingCompanies"] == 0 and summary["jobs"]["total"] > 0 else "todo",
            "reason": "尽调用于识别公司风险和行业趋势。",
            "action": "去尽调",
        },
        {
            "key": "ranking",
            "label": "生成综合排序",
            "page": "ranking",
            "status": "done" if summary["ranking"]["total"] > 0 else "todo",
            "reason": "排序帮助确定优先投递顺序。",
            "action": "去排序",
        },
        {
            "key": "greeting",
            "label": "生成并确认招呼语",
            "page": "greeting",
            "status": "done" if summary["decisions"]["recommended"] > 0 else "todo",
            "reason": "最终进入人工确认和投递跟进。",
            "action": "去打招呼",
        },
    ]
    next_step = next((step for step in steps if step["status"] != "done"), steps[-1])
    done = sum(1 for step in steps if step["status"] == "done")
    return {
        "steps": steps,
        "nextStep": next_step,
        "progress": {"done": done, "total": len(steps), "percent": round(done / len(steps) * 100) if steps else 0},
        "primaryAction": next_step.get("action", ""),
        "primaryPage": next_step.get("page", ""),
        "generatedAt": _now(),
    }



def onboarding_wizard() -> dict[str, Any]:
    guide = onboarding_guide()
    next_key = guide.get("nextStep", {}).get("key")
    steps = []
    for index, step in enumerate(guide.get("steps", []), start=1):
        status = step.get("status") or "todo"
        steps.append({
            **step,
            "index": index,
            "stateLabel": "已完成" if status == "done" else "待完成",
            "blockers": [] if status == "done" else [step.get("reason")],
            "primary": step.get("key") == next_key,
        })
    return {
        "kind": "onboarding_wizard",
        "title": "首次使用向导",
        "progress": guide.get("progress", {}),
        "nextStep": guide.get("nextStep", {}),
        "primaryAction": guide.get("primaryAction", ""),
        "primaryPage": guide.get("primaryPage", ""),
        "steps": steps,
        "tips": [
            "先完成配置和岗位池，再进入尽调、排序和打招呼。",
            "真实自动发送前建议先使用灰度模式跑 1 个岗位。",
        ],
        "generatedAt": _now(),
    }



def review_center() -> dict[str, Any]:
    from app.routes import jobs as jobs_route

    funnel = jobs_route.application_funnel()
    jobs = jobs_route._all_jobs()
    risky = [job for job in jobs if job.decision_status == "risky" or job.lifecycle_status == "blacklisted"]
    missing_jd = [job for job in jobs if not (job.jd_text or "").strip()]
    recommendations = list(funnel.get("recommendations") or [])
    if missing_jd:
        recommendations.append(f"还有 {len(missing_jd)} 个岗位缺少 JD，建议补齐后再复盘排序。")
    if risky:
        recommendations.append(f"有 {len(risky)} 个风险岗位，建议复核后再投递。")
    return {
        "summary": funnel.get("summary", {}),
        "statusCounts": funnel.get("statusCounts", {}),
        "batches": funnel.get("batches", []),
        "riskCompanies": [{"id": job.id, "company": job.company, "title": job.title} for job in risky[:10]],
        "missingJdJobs": [{"id": job.id, "company": job.company, "title": job.title} for job in missing_jd[:10]],
        "recommendations": recommendations or ["当前流程健康，可以继续跟进推荐岗位。"],
        "generatedAt": _now(),
    }



def _readiness_action(label: str, page: str, reason: str) -> dict[str, str]:
    return {"label": label, "page": page, "reason": reason}



def _dashboard_readiness(
    jobs: dict[str, int],
    diligence: dict[str, int],
    ranking: dict[str, int],
    decisions: dict[str, int],
) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    if jobs["total"] <= 0:
        blockers.append({"key": "empty_jobs", "label": "岗位池为空", "count": 1, "severity": "high"})
        return {
            "stage": "setup",
            "qualityScore": 20,
            "nextAction": _readiness_action("完成基础配置并抓取第一批岗位", "jobs", "岗位池为空，先登录 BOSS、配置 API 后抓取岗位。"),
            "blockers": blockers,
        }

    if jobs["missingJd"] > 0:
        blockers.append({"key": "missing_jd", "label": "岗位缺少 JD", "count": jobs["missingJd"], "severity": "high"})
    if diligence["pendingCompanies"] > 0:
        blockers.append({"key": "missing_diligence", "label": "公司尽调未完成", "count": diligence["pendingCompanies"], "severity": "medium"})
    if ranking["total"] <= 0:
        blockers.append({"key": "missing_ranking", "label": "综合排序未生成", "count": 1, "severity": "medium"})
    if jobs["suspectedExpired"] > 0:
        blockers.append({"key": "suspected_expired", "label": "存在疑似过期岗位", "count": jobs["suspectedExpired"], "severity": "medium"})
    if jobs["blacklisted"] > 0 or decisions["risky"] > 0:
        blockers.append({"key": "risk_review", "label": "风险岗位待复核", "count": jobs["blacklisted"] + decisions["risky"], "severity": "medium"})

    if jobs["missingJd"] > 0:
        stage = "complete_jd"
        next_action = _readiness_action("补齐 JD 详情", "jobs", "JD 不完整会影响尽调、匹配排序和招呼语质量。")
    elif diligence["pendingCompanies"] > 0:
        stage = "diligence"
        next_action = _readiness_action("完成公司尽调", "diligence", "尽调缺失会降低风险判断可信度。")
    elif ranking["total"] <= 0:
        stage = "ranking"
        next_action = _readiness_action("生成综合排序", "ranking", "排序完成后才能稳定决定优先投递顺序。")
    elif decisions["recommended"] <= 0:
        stage = "decision"
        next_action = _readiness_action("标记推荐岗位", "ranking", "先筛出值得投递的岗位，再进入打招呼。")
    else:
        stage = "ready"
        next_action = _readiness_action("进入打招呼", "greeting", "核心数据已准备好，可以开始生成招呼语并人工确认。")

    penalty = jobs["missingJd"] * 12 + diligence["pendingCompanies"] * 10 + jobs["suspectedExpired"] * 6 + jobs["blacklisted"] * 8
    if ranking["total"] <= 0:
        penalty += 14
    quality_score = max(0, min(100, 100 - penalty))
    return {
        "stage": stage,
        "qualityScore": quality_score,
        "nextAction": next_action,
        "blockers": blockers,
    }
