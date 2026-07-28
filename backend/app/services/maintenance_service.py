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


def export_full_backup() -> dict:
    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith("logs/events.jsonl"):
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        text = None
        encoding = "base64"
        if path.suffix.lower() in BACKUP_TEXT_SUFFIXES:
            try:
                text = raw.decode("utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError:
                pass
        files.append({
            "path": rel,
            "encoding": encoding,
            "content": text if text is not None else base64.b64encode(raw).decode("ascii"),
            "size": len(raw),
        })
    payload = {
        "kind": "full_workspace_backup",
        "version": 1,
        "exportedAt": _now(),
        "files": files,
        "total": len(files),
    }
    log_event("info", "backup", f"完整备份已生成，包含 {len(files)} 个文件", {"total": len(files)})
    return payload


def _redact_text(value: str) -> str:
    redacted = PHONE_RE.sub("[PHONE_REDACTED]", value)
    return EMAIL_RE.sub("[EMAIL_REDACTED]", redacted)


def _redact_json(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            key_lower = str(key).lower()
            if any(part in key_lower for part in SENSITIVE_FIELD_PARTS):
                cleaned[key] = "[SECRET_REDACTED]" if item else item
            elif any(part in key_lower for part in PRIVACY_FIELD_PARTS):
                cleaned[key] = "[PRIVACY_REDACTED]" if item else item
            else:
                cleaned[key] = _redact_json(item)
        return cleaned
    if isinstance(value, list):
        return [_redact_json(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def export_redacted_backup() -> dict:
    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    files = []
    skipped = []
    redacted_count = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith("logs/events.jsonl"):
            continue
        if path.suffix.lower() not in BACKUP_TEXT_SUFFIXES:
            skipped.append({"path": rel, "reason": "binary_file"})
            continue
        try:
            raw_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            skipped.append({"path": rel, "reason": "read_failed"})
            continue

        content = _redact_text(raw_text)
        if path.suffix.lower() == ".json":
            try:
                content = json.dumps(_redact_json(json.loads(raw_text)), ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                content = _redact_text(raw_text)
        elif path.suffix.lower() == ".jsonl":
            lines = []
            for line in raw_text.splitlines():
                try:
                    lines.append(json.dumps(_redact_json(json.loads(line)), ensure_ascii=False))
                except json.JSONDecodeError:
                    lines.append(_redact_text(line))
            content = "\n".join(lines)

        if content != raw_text:
            redacted_count += 1
        files.append({
            "path": rel,
            "encoding": "utf-8",
            "content": content,
            "size": len(content.encode("utf-8")),
        })

    payload = {
        "kind": "redacted_workspace_backup",
        "version": 1,
        "exportedAt": _now(),
        "files": files,
        "total": len(files),
        "redactedFiles": redacted_count,
        "skippedFiles": skipped,
    }
    log_event("info", "backup", f"脱敏备份已生成，包含 {len(files)} 个文本文件", {"total": len(files), "redactedFiles": redacted_count, "skippedFiles": len(skipped)})
    return payload


def import_full_backup(payload: dict) -> dict:
    if payload.get("kind") != "full_workspace_backup":
        raise ValueError("invalid backup kind")
    restored = 0
    skipped = 0
    root = data_dir()
    for item in payload.get("files") or []:
        try:
            rel = _safe_relative_path(str(item.get("path") or ""))
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            content = item.get("content", "")
            if item.get("encoding") == "base64":
                raw = base64.b64decode(str(content).encode("ascii"))
                target.write_bytes(raw)
            else:
                target.write_text(str(content), encoding="utf-8")
            restored += 1
        except Exception:
            skipped += 1
    log_event("info", "restore", f"完整备份恢复完成，恢复 {restored} 个文件", {"restored": restored, "skipped": skipped})
    return {"restored": restored, "skipped": skipped}


def restore_drill(payload: dict) -> dict[str, Any]:
    backup = payload.get("backup") if isinstance(payload.get("backup"), dict) else payload
    files = backup.get("files") if isinstance(backup, dict) else []
    if not isinstance(files, list):
        files = []
    valid = []
    rejected = []
    for item in files:
        if not isinstance(item, dict):
            rejected.append({"reason": "invalid_item"})
            continue
        try:
            rel = _safe_relative_path(str(item.get("path") or ""))
            target = data_dir() / rel
            valid.append({
                "path": rel.as_posix(),
                "exists": target.exists(),
                "willOverwrite": target.exists(),
                "encoding": item.get("encoding") or "text",
            })
        except ValueError:
            rejected.append({"path": item.get("path"), "reason": "invalid_path"})
    return {
        "kind": "restore_drill",
        "valid": len(rejected) == 0,
        "wouldRestore": len(valid),
        "wouldOverwrite": sum(1 for item in valid if item["willOverwrite"]),
        "files": valid[:200],
        "rejected": rejected[:50],
        "generatedAt": _now(),
    }


def retention_preview() -> dict:
    from app.routes import jobs as jobs_route
    from app.services import workflow_tasks

    expired_jobs = [job for job in jobs_route._all_jobs() if job.lifecycle_status == "suspected_expired"]
    failed_tasks = [
        task for task in workflow_tasks.load_tasks(limit=100)
        if task.get("status") in {"failed", "partial_failed"}
    ]
    resume_files = list((data_dir() / "resumes").glob("*.json")) if (data_dir() / "resumes").exists() else []
    return {
        "expiredJobs": len(expired_jobs),
        "failedTasks": len(failed_tasks),
        "resumeFiles": len(resume_files),
        "archivePath": str(data_dir() / "archive"),
    }


def cleanup_dry_run() -> dict[str, Any]:
    preview = retention_preview()
    root = data_dir()
    cache_files: list[str] = []
    for folder in ("visual-regression", "tmp", "cache"):
        scan_root = root / folder
        if not scan_root.exists():
            continue
        for path in scan_root.rglob("*"):
            if path.is_file():
                cache_files.append(path.relative_to(root).as_posix())
    return {
        "kind": "cleanup_dry_run",
        "status": "warn" if preview.get("expiredJobs") or preview.get("failedTasks") or preview.get("resumeFiles") or cache_files else "ok",
        "summary": {
            "expiredJobs": preview.get("expiredJobs", 0),
            "failedTasks": preview.get("failedTasks", 0),
            "resumeChats": preview.get("resumeFiles", 0),
            "cacheFiles": len(cache_files),
        },
        "targets": [
            {"key": "expired_jobs", "label": "疑似过期岗位", "count": preview.get("expiredJobs", 0), "action": "确认后归档，不会直接硬删除"},
            {"key": "failed_tasks", "label": "失败任务", "count": preview.get("failedTasks", 0), "action": "确认后归档旧失败任务"},
            {"key": "resume_chats", "label": "简历对话缓存", "count": preview.get("resumeFiles", 0), "action": "确认后归档旧对话缓存"},
            {"key": "cache_files", "label": "临时缓存文件", "count": len(cache_files), "action": "确认后清理临时渲染和缓存"},
        ],
        "sampleFiles": cache_files[:10],
        "archivePath": preview.get("archivePath", ""),
        "generatedAt": _now(),
    }


def cleanup_retention(options: dict | None = None) -> dict:
    from app.routes import jobs as jobs_route
    from app.services import workflow_tasks

    opts = options or {}
    archived_jobs = 0
    archived_tasks = 0
    archived_chats = 0
    if opts.get("archive_expired_jobs", True):
        expired = {
            jid: job.model_dump()
            for jid, job in list(jobs_route._job_store.items())
            if job.lifecycle_status == "suspected_expired"
        }
        if expired:
            archive_file = data_dir() / "archive" / "jobs.json"
            existing = _read_json(archive_file, {})
            if not isinstance(existing, dict):
                existing = {}
            existing.update(expired)
            write_json_atomic(archive_file, existing)
            for jid in expired:
                jobs_route._job_store.pop(jid, None)
            jobs_route._save_jobs()
            archived_jobs = len(expired)
    if opts.get("archive_failed_tasks", False):
        tasks = workflow_tasks.load_tasks(limit=100)
        failed = [task for task in tasks if task.get("status") in {"failed", "partial_failed"}]
        if failed:
            archive_file = data_dir() / "archive" / "tasks.json"
            existing = _read_json(archive_file, [])
            if not isinstance(existing, list):
                existing = []
            existing.extend(failed)
            write_json_atomic(archive_file, existing)
            remaining = [task for task in tasks if task.get("status") not in {"failed", "partial_failed"}]
            write_json_atomic(workflow_tasks.TASKS_FILE, remaining)
            archived_tasks = len(failed)
    if opts.get("archive_resume_chats", False):
        resume_dir = data_dir() / "resumes"
        archive_file = data_dir() / "archive" / "resume_chats.json"
        archived_payload = _read_json(archive_file, {})
        if not isinstance(archived_payload, dict):
            archived_payload = {}
        if resume_dir.exists():
            for path in resume_dir.glob("*.json"):
                entry = _read_json(path, {})
                chats = entry.get("chats") if isinstance(entry, dict) else {}
                if chats:
                    archived_payload[path.stem] = chats
                    entry["chats"] = {}
                    write_json_atomic(path, entry)
                    archived_chats += 1
            if archived_chats:
                write_json_atomic(archive_file, archived_payload)
    log_event("info", "retention", f"数据保留策略已执行，归档岗位 {archived_jobs} 个", {"archivedJobs": archived_jobs, "archivedTasks": archived_tasks, "archivedChats": archived_chats})
    return {"archivedJobs": archived_jobs, "archivedTasks": archived_tasks, "archivedChats": archived_chats, "preview": retention_preview()}


def cleanup_confirm(options: dict | None = None) -> dict[str, Any]:
    before = cleanup_dry_run()
    result = cleanup_retention(options or {})
    after = cleanup_dry_run()
    payload = {
        "kind": "cleanup_confirm_result",
        "generatedAt": _now(),
        "before": before,
        "after": after,
        **result,
    }
    log_event("warning", "cleanup", "已确认执行数据清理", {"before": before.get("summary"), "result": result})
    return payload


def retention_rules(options: dict | None = None) -> dict[str, Any]:
    opts = options or {}
    return {
        "suspectAfterDays": max(7, min(int(opts.get("suspect_after_days") or opts.get("suspectAfterDays") or 30), 365)),
        "archiveAfterDays": max(30, min(int(opts.get("archive_after_days") or opts.get("archiveAfterDays") or 90), 730)),
        "autoArchiveEnabled": bool(opts.get("auto_archive_enabled") or opts.get("autoArchiveEnabled") or False),
    }


def apply_retention_rules(options: dict | None = None) -> dict[str, Any]:
    from app.routes import jobs as jobs_route

    rules = retention_rules(options)
    now = datetime.now(timezone.utc)
    marked_suspected = 0
    for job in jobs_route._all_jobs():
        if job.lifecycle_status != "active":
            continue
        last_seen = _parse_time(job.fetched_at or job.captured_at)
        if not last_seen:
            continue
        if last_seen <= now - timedelta(days=rules["suspectAfterDays"]):
            job.lifecycle_status = "suspected_expired"
            job.expires_at = _now()
            job.stale_reason = f"{rules['suspectAfterDays']} 天未更新，待复核"
            if "疑似过期" not in job.tags:
                job.tags = [*job.tags, "疑似过期"]
            marked_suspected += 1
    if marked_suspected:
        jobs_route._save_jobs()
        log_event("info", "retention", f"长期维护规则标记疑似过期岗位 {marked_suspected} 个", {"rules": rules})
    cleanup = {"archivedJobs": 0, "archivedTasks": 0, "archivedChats": 0}
    if rules["autoArchiveEnabled"]:
        cleanup = cleanup_retention({"archive_expired_jobs": True, "archive_failed_tasks": False, "archive_resume_chats": False})
    return {
        "rules": rules,
        "markedSuspected": marked_suspected,
        "archivedJobs": cleanup.get("archivedJobs", 0),
        "preview": retention_preview(),
    }


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


def release_manifest() -> dict:
    import subprocess

    root = Path(__file__).resolve().parents[3]
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, text=True, capture_output=True, check=False).stdout.strip()
    except Exception:
        commit = ""
    return {
        "kind": "release_manifest",
        "version": 1,
        "generatedAt": _now(),
        "commit": commit,
        "storage": storage_status(),
        "qualityGates": [
            {"key": "backend_tests", "command": "pytest -q", "required": True},
            {"key": "frontend_validate", "command": "pnpm validate", "required": True},
            {"key": "diff_check", "command": "git diff --check", "required": True},
            {"key": "security_audit", "endpoint": "/api/maintenance/security/audit", "required": True},
        ],
    }


def release_notes() -> dict:
    return {
        "kind": "release_notes",
        "version": "1.0",
        "generatedAt": _now(),
        "phase": "1.0 正式版",
        "highlights": [
            "核心流程已闭环：简历、岗位、JD、尽调、排序、打招呼、跟进。",
            "上线维护能力已接入：发布体检、安全审计、脱敏备份、人工验收清单。",
            "长期维护能力已接入：SQLite 主存储、备份恢复、删除恢复、任务中心和投递时间线。",
        ],
        "knownRisks": [
            "真实 BOSS 页面结构可能变化，自动发送前需要先执行页面可用性检测。",
            "自动化不会绕过验证码或风控，遇到风险提示会停止并记录原因。",
            "完整备份包含敏感业务数据，演示或排查问题请使用脱敏备份。",
        ],
    }


def release_acceptance_checklist() -> dict:
    return {
        "kind": "release_acceptance_checklist",
        "version": 1,
        "generatedAt": _now(),
        "sections": [
            {
                "key": "core_flow",
                "title": "核心求职流程",
                "steps": [
                    "导入或解析一份简历，确认简历模块能展示基础信息和优化建议。",
                    "抓取一组真实岗位，确认城市、多维筛选、黑名单和重复岗位处理符合预期。",
                    "补全 JD 详情，抽查至少 3 个岗位，确认噪音已被过滤且岗位正文可读。",
                    "执行公司尽调，确认工商名称替换、行业分析、搜索证据和风险解释可追溯。",
                    "运行岗位排序，确认权重模板、推荐理由、简历缺口和下一步建议能解释排序结果。",
                ],
            },
            {
                "key": "greeting_flow",
                "title": "打招呼流程",
                "steps": [
                    "生成招呼语草稿，确认内容通过长度、中文、模板变量和异常话术校验。",
                    "执行发送前预检，确认未登录、Cookie 失效、页面风控、网络失败会显示清晰原因。",
                    "使用人工确认模式发送 1 条测试岗位，确认岗位状态、投递时间线和发送记录同步更新。",
                    "开启真实自动发送前，确认全局开关、频率模板、单批上限、今日上限和暂停/终止按钮可用。",
                ],
            },
            {
                "key": "release_safety",
                "title": "上线安全",
                "steps": [
                    "运行发布体检，确认无 error 项；warn 项需要有明确处理或接受理由。",
                    "导出完整备份并单独保存，再导出脱敏备份用于演示或问题排查。",
                    "执行安全审计，确认 API Key 未以明文残留，导出文件不包含手机号或邮箱等明显隐私。",
                    "运行后端测试、前端校验、端到端冒烟和差异格式检查。",
                ],
            },
        ],
    }


def security_audit() -> dict:
    root = data_dir()
    checks = []
    suspicious = []
    secret_files = [
        root / "provider.json",
        root / "baidu_config.json",
        root / "business_info_config.json",
    ]
    for path in secret_files:
        payload = _read_json(path, {})
        if not isinstance(payload, dict):
            continue
        for key in ("api_key", "secret_key", "secret_id"):
            value = str(payload.get(key) or "")
            encrypted = str(payload.get(f"{key}_encrypted") or "")
            if value and not encrypted:
                suspicious.append({"path": path.relative_to(root).as_posix(), "field": key})
    checks.append({
        "key": "plain_secret_scan",
        "label": "明文密钥扫描",
        "status": "warn" if suspicious else "ok",
        "message": f"发现 {len(suspicious)} 个疑似明文字段。" if suspicious else "未发现已知配置文件中的明文密钥。",
        "items": suspicious,
    })
    checks.append({
        "key": "local_secret_key",
        "label": "本地加密主密钥",
        "status": "ok" if (root / ".secret_key").exists() else "warn",
        "message": "已检测到本地加密主密钥。" if (root / ".secret_key").exists() else "未检测到 data/.secret_key；如使用环境变量主密钥可忽略。",
    })
    dependency_files = [
        Path(__file__).resolve().parents[3] / "backend" / "pyproject.toml",
        Path(__file__).resolve().parents[3] / "frontend" / "pnpm-lock.yaml",
    ]
    checks.append({
        "key": "dependency_audit",
        "label": "依赖审计准备度",
        "status": "ok" if all(path.exists() for path in dependency_files) else "warn",
        "message": "已检测到后端依赖声明和前端锁文件，可纳入发布审计。" if all(path.exists() for path in dependency_files) else "依赖声明不完整，发布前需要复核。",
    })
    privacy_hits = []
    phone_re = re.compile(r"1[3-9]\d{9}")
    email_re = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    for folder in ("resumes", "uploads", "greetings"):
        scan_root = root / folder
        if not scan_root.exists():
            continue
        for path in list(scan_root.rglob("*.json"))[:100]:
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            matches = []
            if phone_re.search(text):
                matches.append("phone")
            if email_re.search(text):
                matches.append("email")
            if matches:
                privacy_hits.append({"path": path.relative_to(root).as_posix(), "fields": matches})
    checks.append({
        "key": "export_privacy_scan",
        "label": "导出隐私扫描",
        "status": "warn" if privacy_hits else "ok",
        "message": f"发现 {len(privacy_hits)} 个可能包含个人信息的业务文件。" if privacy_hits else "未在常见导出目录发现手机号或邮箱。",
        "items": privacy_hits[:20],
    })
    status = "error" if any(item["status"] == "error" for item in checks) else ("warn" if any(item["status"] == "warn" for item in checks) else "ok")
    return {"status": status, "checks": checks, "generatedAt": _now()}


def privacy_scan() -> dict[str, Any]:
    root = data_dir()
    hits: list[dict[str, Any]] = []
    patterns = {
        "phone": re.compile(r"1[3-9]\d{9}"),
        "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        "idCard": re.compile(r"\d{17}[\dXx]"),
    }
    for folder in ("resumes", "uploads", "jobs", "greetings", "diligence", "assistant"):
        scan_root = root / folder
        if not scan_root.exists():
            continue
        for path in list(scan_root.rglob("*"))[:500]:
            if not path.is_file() or path.suffix.lower() not in {".json", ".jsonl", ".txt", ".md", ".csv"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            fields = [key for key, regex in patterns.items() if regex.search(text)]
            if fields:
                hits.append({"path": path.relative_to(root).as_posix(), "fields": fields})
    return {
        "kind": "privacy_scan",
        "status": "warn" if hits else "ok",
        "summary": {"hits": len(hits), "scannedRoots": 6},
        "hits": hits[:50],
        "suggestions": [
            "上线演示前优先导出脱敏备份，不使用完整备份文件演示。",
            "清理上传目录、测试简历和临时发送记录中的手机号、邮箱等个人信息。",
            "如需排查问题，优先使用脱敏备份或最小化样本。",
        ] if hits else ["当前未发现明显手机号、邮箱或身份证号残留。"],
        "generatedAt": _now(),
    }


def dependency_vulnerability_audit(dry_run: bool = False) -> dict:
    repo_root = Path(__file__).resolve().parents[3]
    checks = []
    planned = [
        {
            "key": "frontend_pnpm_audit",
            "label": "前端依赖漏洞审计",
            "command": ["pnpm", "audit", "--json"],
            "cwd": repo_root / "frontend",
            "available": (repo_root / "frontend" / "pnpm-lock.yaml").exists(),
        },
        {
            "key": "backend_pip_audit",
            "label": "后端依赖漏洞审计",
            "command": ["python3", "-m", "pip_audit", "--format", "json"],
            "cwd": repo_root,
            "available": importlib.util.find_spec("pip_audit") is not None,
        },
    ]
    for item in planned:
        if dry_run:
            checks.append({
                "key": item["key"],
                "label": item["label"],
                "status": "ok" if item["available"] else "warn",
                "message": "可执行真实依赖审计。" if item["available"] else "审计工具或锁文件不可用。",
                "command": " ".join(item["command"]),
            })
            continue
        if not item["available"]:
            checks.append({
                "key": item["key"],
                "label": item["label"],
                "status": "warn",
                "message": "审计工具或锁文件不可用，发布前需补齐后再执行。",
                "command": " ".join(item["command"]),
            })
            continue
        try:
            result = subprocess.run(
                item["command"],
                cwd=item["cwd"],
                text=True,
                capture_output=True,
                timeout=35,
                check=False,
            )
            output = (result.stdout or result.stderr or "").strip()
            vulnerable = result.returncode not in {0}
            message = "未发现阻断级漏洞。" if not vulnerable else "依赖审计发现风险，请查看命令输出并升级依赖。"
            checks.append({
                "key": item["key"],
                "label": item["label"],
                "status": "warn" if vulnerable else "ok",
                "message": message,
                "command": " ".join(item["command"]),
                "exitCode": result.returncode,
                "outputPreview": output[:1200],
            })
        except subprocess.TimeoutExpired:
            checks.append({
                "key": item["key"],
                "label": item["label"],
                "status": "warn",
                "message": "依赖审计超时，请在终端手动执行。",
                "command": " ".join(item["command"]),
            })
    status = "warn" if any(item["status"] != "ok" for item in checks) else "ok"
    return {"status": status, "checks": checks, "dryRun": dry_run, "generatedAt": _now()}


def release_preflight() -> dict:
    health = run_health_check()
    checks = list(health.get("checks") or [])
    storage = storage_status()
    preview = retention_preview()
    recent_errors = list_events(level="error", limit=5)

    checks.extend([
        {
            "key": "storage_backup",
            "label": "完整数据备份",
            "status": "warn",
            "message": "上线前建议导出完整备份，并保存在可信位置。",
            "action": "设置页执行完整备份导出",
        },
        {
            "key": "storage_mode",
            "label": "数据存储模式",
            "status": "ok" if storage["json"]["ready"] else "error",
            "message": storage["sqlite"]["message"],
            "action": "如需迁移，可先执行 SQLite 快照迁移",
        },
        {
            "key": "retention",
            "label": "数据保留策略",
            "status": "warn" if preview["expiredJobs"] or preview["failedTasks"] else "ok",
            "message": f"疑似过期岗位 {preview['expiredJobs']} 个，失败任务 {preview['failedTasks']} 个。",
            "action": "上线前归档疑似过期岗位和失败任务",
        },
        {
            "key": "recent_errors",
            "label": "近期错误日志",
            "status": "warn" if recent_errors else "ok",
            "message": f"最近发现 {len(recent_errors)} 条错误日志。" if recent_errors else "未发现近期错误日志。",
            "action": "打开维护日志复核错误详情" if recent_errors else "",
        },
    ])
    if any(item.get("status") == "error" for item in checks):
        status = "error"
    elif any(item.get("status") == "warn" for item in checks):
        status = "warn"
    else:
        status = "ok"
    return {
        "status": status,
        "summary": {
            "total": len(checks),
            "ok": sum(1 for item in checks if item.get("status") == "ok"),
            "warn": sum(1 for item in checks if item.get("status") == "warn"),
            "error": sum(1 for item in checks if item.get("status") == "error"),
        },
        "checks": checks,
        "generatedAt": _now(),
    }


def storage_migration_wizard() -> dict:
    storage = storage_status()
    sqlite_info = storage["sqlite"]
    backups = sqlite_info.get("backups") or []
    migrated = bool(sqlite_info.get("exists"))
    verified = sqlite_info.get("integrity", {}).get("status") == "ok"
    primary_sqlite = storage.get("activeStore") == "sqlite"
    steps = [
        {
            "key": "backup",
            "label": "创建迁移前备份",
            "status": "done" if backups else "todo",
            "action": "点击“创建数据库备份”或先导出完整数据。",
        },
        {
            "key": "migrate",
            "label": "执行 SQLite 快照迁移",
            "status": "done" if migrated else "todo",
            "action": "点击“执行快照迁移”。",
        },
        {
            "key": "verify",
            "label": "校验数据库完整性",
            "status": "done" if migrated and verified else ("todo" if migrated else "blocked"),
            "action": "迁移后查看完整性状态，必要时预览最近备份。",
        },
        {
            "key": "set_primary",
            "label": "设为主存储",
            "status": "done" if primary_sqlite else ("todo" if migrated and verified else "blocked"),
            "action": "校验正常后点击“设为主存储”。",
        },
        {
            "key": "rollback",
            "label": "保留回滚路径",
            "status": "available" if migrated else "blocked",
            "action": "如果迁移后异常，可点击“回滚 JSON”。",
        },
    ]
    if primary_sqlite and verified:
        next_step = {"label": "迁移已完成", "action": "保持定期备份即可。"}
    else:
        next_step = next(({"label": step["label"], "action": step["action"]} for step in steps if step["status"] == "todo"), {"label": "等待前置步骤", "action": "先完成未阻断的迁移步骤。"})
    return {
        "activeStore": storage["activeStore"],
        "sqlitePath": sqlite_info["path"],
        "steps": steps,
        "nextStep": next_step,
        "generatedAt": _now(),
    }


def migrate_to_sqlite() -> dict:
    from app.services import sqlite_kv_store

    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    sqlite_path = root / "boss_workbench.sqlite3"
    backup = sqlite_kv_store.create_backup() if sqlite_path.exists() else None
    conn = sqlite3.connect(sqlite_path)
    snapshot_count = 0
    resumes_imported = 0
    maintenance_events_imported = 0
    api_calls_imported = 0
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS json_snapshots (path TEXT PRIMARY KEY, content TEXT NOT NULL, updated_at TEXT NOT NULL)")
        for path in sorted(root.rglob("*.json")):
            if "archive" in path.relative_to(root).parts:
                continue
            rel = path.relative_to(root).as_posix()
            conn.execute(
                "INSERT OR REPLACE INTO json_snapshots(path, content, updated_at) VALUES (?, ?, ?)",
                (rel, path.read_text(encoding="utf-8"), _now()),
            )
            snapshot_count += 1
        conn.commit()
    finally:
        conn.close()

    for path in sorted((root / "resumes").glob("*.json")) if (root / "resumes").exists() else []:
        entry = _read_json(path, None)
        if isinstance(entry, dict):
            sqlite_kv_store.put("resumes", path.stem, entry)
            resumes_imported += 1

    def import_jsonl(path: Path, namespace: str) -> int:
        imported = 0
        if not path.exists():
            return imported
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict):
                continue
            key = str(item.get("id") or "").strip()
            if not key:
                continue
            sqlite_kv_store.put(namespace, key, item)
            imported += 1
        return imported

    maintenance_events_imported = import_jsonl(root / "logs" / "events.jsonl", "maintenance_events")
    api_calls_imported = import_jsonl(root / "logs" / "api_calls.jsonl", "api_calls")
    log_event(
        "info",
        "storage",
        f"SQLite 迁移完成，快照 {snapshot_count} 个文件、简历 {resumes_imported} 份、日志 {maintenance_events_imported + api_calls_imported} 条",
        {
            "snapshotTables": snapshot_count,
            "resumesImported": resumes_imported,
            "maintenanceEventsImported": maintenance_events_imported,
            "apiCallsImported": api_calls_imported,
        },
    )
    status = storage_status()
    status.update({
        "snapshotTables": snapshot_count,
        "resumesImported": resumes_imported,
        "maintenanceEventsImported": maintenance_events_imported,
        "apiCallsImported": api_calls_imported,
        "migrationBackup": backup,
    })
    return status


def rollback_sqlite_to_json() -> dict:
    sqlite_path = data_dir() / "boss_workbench.sqlite3"
    restored = 0
    if sqlite_path.exists():
        conn = sqlite3.connect(sqlite_path)
        try:
            rows = conn.execute("SELECT path, content FROM json_snapshots").fetchall()
            for rel, content in rows:
                target = data_dir() / _safe_relative_path(rel)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                restored += 1
        finally:
            conn.close()
    log_event("info", "storage", f"SQLite 快照回滚完成，恢复 {restored} 个 JSON 文件", {"restored": restored})
    status = storage_status()
    status["restored"] = restored
    return status


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
    missing_jd = [job for job in jobs if not (job.jd_text or "").strip()]
    low_quality_jd = [job for job in jobs if (job.jd_text or "").strip() and len((job.jd_text or "").strip()) < 80]
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


def production_guard() -> dict[str, Any]:
    from app.services.runtime_mode import get_runtime_mode

    mode = get_runtime_mode()
    preflight = release_preflight()
    redacted_ready = export_redacted_backup().get("kind") == "redacted_workspace_backup"
    checks = [
        {
            "key": "runtime_mode",
            "label": "运行模式",
            "status": "ok" if mode == "production" else "warn",
            "message": f"当前为 {mode} 模式",
            "action": "上线前建议使用 production 模式",
        },
        {
            "key": "preflight",
            "label": "上线体检",
            "status": "ok" if preflight.get("status") == "ok" else "warn",
            "message": f"体检状态：{preflight.get('status')}",
            "action": "处理体检中的 warn/error 项",
        },
        {
            "key": "redacted_backup",
            "label": "脱敏备份",
            "status": "ok" if redacted_ready else "warn",
            "message": "可生成脱敏备份" if redacted_ready else "脱敏备份不可用",
            "action": "上线前导出脱敏备份用于演示或交付",
        },
    ]
    status = "ok" if all(item["status"] == "ok" for item in checks) else "warn"
    return {
        "mode": mode,
        "status": status,
        "locked": status == "ok",
        "checks": checks,
        "summary": {
            "total": len(checks),
            "ok": sum(1 for item in checks if item["status"] == "ok"),
            "warn": sum(1 for item in checks if item["status"] == "warn"),
        },
        "generatedAt": _now(),
    }


def online_acceptance_report() -> dict[str, Any]:
    preflight = release_preflight()
    guard = production_guard()
    storage = storage_status()
    pdf_status = "unknown"
    try:
        from app.routes.maintenance import get_pdf_visual_regression

        pdf_status = str(get_pdf_visual_regression().get("status") or "unknown")
    except Exception:
        pdf_status = "error"
    checks = [
        {"key": "backend_tests", "label": "后端测试", "status": "manual", "command": "cd backend && pytest -q"},
        {"key": "frontend_validate", "label": "前端校验", "status": "manual", "command": "cd frontend && pnpm validate"},
        {"key": "playwright", "label": "端到端测试", "status": "manual", "command": "cd frontend && pnpm exec playwright test"},
        {"key": "release_preflight", "label": "上线体检", "status": preflight.get("status"), "summary": preflight.get("summary")},
        {"key": "production_guard", "label": "生产保护", "status": guard.get("status"), "summary": guard.get("summary")},
        {"key": "pdf_visual", "label": "PDF 渲染", "status": pdf_status},
        {"key": "storage", "label": "存储状态", "status": "ok" if storage.get("json", {}).get("ready") else "warn", "activeStore": storage.get("activeStore")},
    ]
    return {
        "kind": "online_acceptance_report",
        "version": "beta",
        "generatedAt": _now(),
        "status": "ok" if all(item.get("status") in {"ok", "manual"} for item in checks) else "warn",
        "checks": checks,
        "nextActions": [
            "上线前重新运行后端全量测试、前端校验和 Playwright。",
            "导出完整备份和脱敏备份。",
            "人工验收 BOSS 登录、抓取、JD、尽调、排序、PDF、打招呼链路。",
        ],
    }


def release_acceptance_suite() -> dict[str, Any]:
    checklist = release_acceptance_checklist()
    preflight = release_preflight()
    privacy = privacy_scan()
    guard = production_guard()
    sections = []
    for section in checklist.get("sections", []):
        steps = section.get("steps") if isinstance(section.get("steps"), list) else []
        sections.append({
            "key": section.get("key"),
            "title": section.get("title"),
            "status": "manual",
            "total": len(steps),
            "steps": [{"label": step, "status": "manual"} for step in steps],
        })
    machine_checks = [
        {"key": "release_preflight", "label": "上线体检", "status": preflight.get("status"), "summary": preflight.get("summary")},
        {"key": "production_guard", "label": "生产保护", "status": guard.get("status"), "summary": guard.get("summary")},
        {"key": "privacy_scan", "label": "隐私扫描", "status": privacy.get("status"), "summary": privacy.get("summary")},
    ]
    status = "error" if any(item.get("status") == "error" for item in machine_checks) else ("warn" if any(item.get("status") == "warn" for item in machine_checks) else "ok")
    return {
        "kind": "release_acceptance_suite",
        "status": status,
        "generatedAt": _now(),
        "sections": sections,
        "machineChecks": machine_checks,
        "nextActions": [
            "先处理机器检查中的 warn/error，再执行人工验收清单。",
            "真实 BOSS 链路使用灰度模式先验收单条，再放开批量。",
        ],
    }


def release_version_snapshot() -> dict[str, Any]:
    manifest = release_manifest()
    notes = release_notes()
    preflight = release_preflight()
    return {
        "kind": "release_version_snapshot",
        "version": notes.get("version") or "1.0",
        "commit": manifest.get("commit", ""),
        "generatedAt": _now(),
        "phase": notes.get("phase", ""),
        "status": preflight.get("status", "warn"),
        "summary": preflight.get("summary", {}),
        "highlights": notes.get("highlights", []),
        "knownRisks": notes.get("knownRisks", []),
        "qualityGates": manifest.get("qualityGates", []),
    }


def release_check_suite() -> dict[str, Any]:
    diagnostics = diagnostic_center()
    privacy = privacy_scan()
    cleanup = cleanup_dry_run()
    storage = storage_status()
    backup_ready = export_redacted_backup().get("kind") == "redacted_workspace_backup"
    checks = [
        {"key": "diagnostics", "label": "错误诊断中心", "status": diagnostics.get("status"), "summary": diagnostics.get("summary")},
        {"key": "privacy", "label": "隐私扫描", "status": privacy.get("status"), "summary": privacy.get("summary")},
        {"key": "cleanup", "label": "清理预演", "status": cleanup.get("status"), "summary": cleanup.get("summary")},
        {"key": "backup", "label": "脱敏备份", "status": "ok" if backup_ready else "warn", "summary": {"ready": backup_ready}},
        {"key": "storage", "label": "存储状态", "status": "ok" if storage.get("json", {}).get("ready") else "error", "summary": {"activeStore": storage.get("activeStore")}},
        {"key": "backend", "label": "后端测试", "status": "manual", "command": "cd backend && pytest -q"},
        {"key": "frontend", "label": "前端校验", "status": "manual", "command": "cd frontend && pnpm validate"},
        {"key": "playwright", "label": "浏览器验收", "status": "manual", "command": "cd frontend && pnpm exec playwright test"},
    ]
    machine = [item for item in checks if item.get("status") != "manual"]
    status = "error" if any(item.get("status") == "error" for item in machine) else ("warn" if any(item.get("status") == "warn" for item in machine) else "ok")
    return {
        "kind": "release_check_suite",
        "status": status,
        "generatedAt": _now(),
        "summary": {
            "total": len(checks),
            "ok": sum(1 for item in checks if item.get("status") == "ok"),
            "warn": sum(1 for item in checks if item.get("status") == "warn"),
            "error": sum(1 for item in checks if item.get("status") == "error"),
            "manual": sum(1 for item in checks if item.get("status") == "manual"),
        },
        "checks": checks,
        "nextActions": [
            "运行手动门禁：后端测试、前端校验和 Playwright。",
            "处理诊断、隐私扫描和清理预演中的 warn/error。",
            "通过后生成 Release Record。",
        ],
    }


def _release_records_file() -> Path:
    return data_dir() / "release" / "records.json"


def list_release_records(limit: int = 20) -> dict[str, Any]:
    rows = _read_json(_release_records_file(), [])
    if not isinstance(rows, list):
        rows = []
    return {"records": rows[: max(1, min(int(limit or 20), 100))], "total": len(rows)}


def create_release_record(payload: dict) -> dict[str, Any]:
    version = str(payload.get("version") or release_notes().get("version") or "1.0").strip()
    operator = str(payload.get("operator") or "").strip() or "未填写"
    decision = str(payload.get("decision") or "review").strip()
    notes = [str(item).strip() for item in payload.get("notes", []) if str(item).strip()] if isinstance(payload.get("notes"), list) else []
    record = {
        "id": f"release-{int(datetime.now().timestamp() * 1000)}",
        "version": version,
        "operator": operator,
        "decision": decision if decision in {"ready", "hold", "review"} else "review",
        "notes": notes,
        "createdAt": _now(),
        "snapshot": release_version_snapshot(),
        "checkSuite": release_check_suite(),
    }
    rows = _read_json(_release_records_file(), [])
    if not isinstance(rows, list):
        rows = []
    rows = [record, *rows][:100]
    write_json_atomic(_release_records_file(), rows)
    log_event("info", "release", f"发布记录已生成: {version}", {"recordId": record["id"], "decision": record["decision"]})
    return {"record": record, "total": len(rows)}


def diagnostic_center() -> dict[str, Any]:
    health = run_health_check()
    privacy = privacy_scan()
    storage = storage_status()
    try:
        from app.routes.greetings import greeting_recovery_panel

        recovery = greeting_recovery_panel()
    except Exception:
        recovery = {"summary": {"failed": 0, "retryable": 0}, "groups": []}
    try:
        from app.routes.maintenance import get_pdf_visual_regression

        pdf = get_pdf_visual_regression()
        pdf_status = str(pdf.get("status") or "warn")
        pdf_message = "PDF 真实渲染正常" if pdf_status == "ok" else "PDF 渲染检查需要关注"
    except Exception as exc:
        pdf_status = "warn"
        pdf_message = f"PDF 检查不可用: {str(exc)[:80]}"
    checks = list(health.get("checks") or [])
    checks.extend([
        {
            "key": "storage",
            "label": "存储状态",
            "status": "ok" if storage.get("json", {}).get("ready") else "error",
            "message": storage.get("sqlite", {}).get("message", ""),
            "action": "设置页查看存储迁移向导",
        },
        {
            "key": "privacy_scan",
            "label": "隐私扫描",
            "status": privacy.get("status", "warn"),
            "message": f"发现 {privacy.get('summary', {}).get('hits', 0)} 处明显隐私数据",
            "action": "使用脱敏备份或清理测试数据",
        },
        {
            "key": "pdf_visual",
            "label": "PDF 渲染",
            "status": pdf_status if pdf_status in {"ok", "warn", "error"} else "warn",
            "message": pdf_message,
            "action": "设置页刷新 PDF 真实渲染检查",
        },
        {
            "key": "greeting_recovery",
            "label": "打招呼失败恢复",
            "status": "warn" if int(recovery.get("summary", {}).get("failed", 0)) else "ok",
            "message": f"失败 {recovery.get('summary', {}).get('failed', 0)}，可重试 {recovery.get('summary', {}).get('retryable', 0)}",
            "action": "打招呼页查看失败恢复台",
        },
    ])
    for item in checks:
        item["repairAction"] = _diagnostic_repair_action(str(item.get("key") or ""))
    repair_actions = [item for item in checks if item.get("status") != "ok"]
    status = "error" if any(item.get("status") == "error" for item in checks) else ("warn" if any(item.get("status") == "warn" for item in checks) else "ok")
    return {
        "kind": "diagnostic_center",
        "status": status,
        "summary": {
            "total": len(checks),
            "ok": sum(1 for item in checks if item.get("status") == "ok"),
            "warn": sum(1 for item in checks if item.get("status") == "warn"),
            "error": sum(1 for item in checks if item.get("status") == "error"),
        },
        "checks": checks,
        "repairActions": [
            {
                "key": item.get("key"),
                "label": item.get("label"),
                "status": item.get("status"),
                "message": item.get("message"),
                "repairAction": item.get("repairAction"),
            }
            for item in repair_actions
        ],
        "generatedAt": _now(),
    }


def _diagnostic_repair_action(key: str) -> dict[str, Any]:
    mapping = {
        "runtime_mode": {"type": "navigate", "page": "settings", "label": "切换生产模式", "description": "在设置页的数据模式中切换为生产数据"},
        "ai_provider": {"type": "navigate", "page": "settings", "label": "配置 AI", "description": "在设置页补充 AI 供应商和 API Key"},
        "baidu_search": {"type": "navigate", "page": "settings", "label": "配置搜索", "description": "在设置页补充百度搜索 API Key"},
        "business_api": {"type": "navigate", "page": "settings", "label": "配置工商 API", "description": "在设置页补充腾讯云工商 API 凭证"},
        "boss_login": {"type": "navigate", "page": "jobs", "label": "检查 BOSS 登录", "description": "到岗位模块重新登录或检查 Cookie 状态"},
        "frontend_build": {"type": "command", "command": "cd frontend && pnpm validate", "label": "重新构建前端", "description": "运行前端校验并生成发布产物"},
        "data_dir": {"type": "manual", "page": "settings", "label": "检查数据目录权限", "description": "确认 data 目录可读写"},
        "storage": {"type": "navigate", "page": "settings", "label": "查看存储向导", "description": "在设置页查看 SQLite 迁移、备份和回滚状态"},
        "privacy_scan": {"type": "export_redacted_backup", "page": "settings", "label": "导出脱敏备份", "description": "先导出脱敏备份，再清理测试数据或个人信息"},
        "pdf_visual": {"type": "refresh_endpoint", "endpoint": "/api/maintenance/release/pdf-visual-regression", "page": "settings", "label": "刷新 PDF 检查", "description": "重新生成 PDF 真实渲染检查"},
        "greeting_recovery": {"type": "navigate", "page": "greeting", "label": "查看失败恢复台", "description": "按失败原因处理或转人工"},
    }
    return mapping.get(key, {"type": "manual", "page": "dashboard", "label": "查看详情", "description": "查看诊断详情后手动处理"})


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
