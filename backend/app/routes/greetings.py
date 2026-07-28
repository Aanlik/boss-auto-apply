from __future__ import annotations

from datetime import datetime
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import workflow_persistence
from app.services.greeting_workbench import (
    build_greeting_candidates,
    build_greeting_record,
    count_sent_today,
    generate_greeting,
    validate_greeting,
)
from app.services.workflow_persistence import (
    load_greetings,
    load_send_records,
    save_greetings,
    save_send_record,
)
from app.services.maintenance_service import log_event
from app.services.workflow_tasks import complete_task, get_task, partial_fail_task, start_task, update_task


router = APIRouter(prefix="/api/greetings", tags=["greetings"])


class GreetingCandidateRequest(BaseModel):
    job_ids: list[str] = Field(default_factory=list)


class GreetingValidateItem(BaseModel):
    job_id: str
    message: str


class GreetingValidateRequest(BaseModel):
    items: list[GreetingValidateItem] = Field(default_factory=list)


class GreetingDryRunRequest(BaseModel):
    job_ids: list[str] = Field(default_factory=list)
    resume_summary: str = ""
    style: str = "稳妥自然"


class GreetingSendRequest(BaseModel):
    job_ids: list[str] = Field(default_factory=list)
    messages: dict[str, str] = Field(default_factory=dict)
    confirm: bool = False
    mode: str = "manual_confirm"
    batch_limit: int = 5
    daily_limit: int = 15
    send_interval_seconds: int = 5
    stop_on_blocked: bool = True


class GreetingPreflightRequest(BaseModel):
    job_ids: list[str] = Field(default_factory=list)
    messages: dict[str, str] = Field(default_factory=dict)
    mode: str = "browser_auto"


class GreetingFinalConfirmationRequest(BaseModel):
    job_ids: list[str] = Field(default_factory=list)
    messages: dict[str, str] = Field(default_factory=dict)
    mode: str = "browser_auto"
    daily_limit: int = 15
    batch_limit: int = 5


class GreetingControlRequest(BaseModel):
    action: str


class GreetingSettingsRequest(BaseModel):
    auto_send_enabled: bool = False
    profile: str = "standard"
    gray_mode_enabled: bool = True
    gray_first_success_required: bool = True


class GreetingSelectorHealthRequest(BaseModel):
    job_id: str


class GreetingAcceptancePlanRequest(BaseModel):
    job_id: str


class GreetingAcceptanceRecordRequest(BaseModel):
    job_id: str = ""
    result: str = "passed"
    operator: str = ""
    note: str = ""
    checks: list[dict] = Field(default_factory=list)


class GreetingReplyRecordRequest(BaseModel):
    job_id: str = ""
    reply_type: str = "neutral"
    content: str = ""
    next_action: str = ""


def _all_jobs():
    from app.routes.jobs import _all_jobs as jobs_all

    return jobs_all()


def _jobs_by_id() -> dict:
    return {job.id: job for job in _all_jobs()}


FREQUENCY_PROFILES = [
    {"key": "conservative", "label": "保守", "batchLimit": 2, "intervalSeconds": 20, "dailyLimit": 10},
    {"key": "standard", "label": "标准", "batchLimit": 3, "intervalSeconds": 8, "dailyLimit": 15},
    {"key": "fast", "label": "快速", "batchLimit": 5, "intervalSeconds": 5, "dailyLimit": 25},
]


def _settings_file():
    return workflow_persistence.DATA_DIR / "greetings" / "auto_send_settings.json"


def _control_file():
    return workflow_persistence.DATA_DIR / "greetings" / "control.json"


def _acceptance_records_file():
    return workflow_persistence.DATA_DIR / "greetings" / "acceptance_records.json"


def _reply_records_file():
    return workflow_persistence.DATA_DIR / "greetings" / "reply_records.json"


def _load_settings() -> dict:
    data = workflow_persistence._read_json(_settings_file(), {})
    if not isinstance(data, dict):
        data = {}
    return {
        "auto_send_enabled": bool(data.get("auto_send_enabled", False)),
        "profile": str(data.get("profile") or "standard"),
        "gray_mode_enabled": bool(data.get("gray_mode_enabled", True)),
        "gray_first_success_required": bool(data.get("gray_first_success_required", True)),
    }


def _save_settings(settings: dict) -> dict:
    payload = {
        "auto_send_enabled": bool(settings.get("auto_send_enabled", False)),
        "profile": str(settings.get("profile") or "standard"),
        "gray_mode_enabled": bool(settings.get("gray_mode_enabled", True)),
        "gray_first_success_required": bool(settings.get("gray_first_success_required", True)),
        "updatedAt": datetime.now().isoformat(),
    }
    workflow_persistence.write_json_atomic(_settings_file(), payload)
    return payload


def _gray_mode_status(settings: dict | None = None, records: list[dict] | None = None) -> dict:
    settings = settings or _load_settings()
    records = records if records is not None else load_send_records()
    sent_today = count_sent_today()
    latest_status = ""
    for record in reversed(records):
        status = str(record.get("status") or "")
        if status in {"sent", "failed", "blocked"}:
            latest_status = status
            break
    enabled = bool(settings.get("gray_mode_enabled", True))
    requires_first = bool(settings.get("gray_first_success_required", True))
    locked = enabled and latest_status in {"failed", "blocked"} and sent_today == 0
    batch_allowed = (not enabled) or (not requires_first) or sent_today > 0
    return {
        "enabled": enabled,
        "requiresFirstSuccess": requires_first,
        "sentToday": sent_today,
        "latestStatus": latest_status,
        "batchAllowed": batch_allowed and not locked,
        "locked": locked,
        "message": "灰度模式已通过，可批量发送" if batch_allowed and not locked else "灰度模式要求先成功发送 1 个岗位，再开放批量真实发送",
    }


def _load_control() -> dict:
    data = workflow_persistence._read_json(_control_file(), {})
    if not isinstance(data, dict):
        data = {}
    return {
        "state": str(data.get("state") or "running"),
        "updatedAt": str(data.get("updatedAt") or ""),
        "reason": str(data.get("reason") or ""),
    }


def _save_control(state: str, reason: str = "") -> dict:
    payload = {"state": state, "reason": reason, "updatedAt": datetime.now().isoformat()}
    workflow_persistence.write_json_atomic(_control_file(), payload)
    return payload


def check_boss_login_status() -> dict:
    from app.services.boss_scraper import check_login_status

    return check_login_status()


def check_boss_selector_health(job_url: str) -> dict:
    from app.services.boss_scraper import check_boss_greeting_selectors_sync

    return check_boss_greeting_selectors_sync(job_url)


@router.get("/frequency-profiles")
def greeting_frequency_profiles() -> dict:
    return {"profiles": FREQUENCY_PROFILES}


@router.get("/auto-send-settings")
def get_auto_send_settings() -> dict:
    return {"settings": _load_settings(), "profiles": FREQUENCY_PROFILES}


@router.post("/auto-send-settings")
def save_auto_send_settings(payload: GreetingSettingsRequest) -> dict:
    return {"settings": _save_settings(payload.model_dump()), "profiles": FREQUENCY_PROFILES}


@router.post("/control")
def update_greeting_control(payload: GreetingControlRequest) -> dict:
    action = payload.action.strip()
    if action == "pause":
        state = "paused"
    elif action in {"resume", "continue"}:
        state = "running"
    elif action in {"stop", "terminate"}:
        state = "stopped"
    else:
        raise HTTPException(status_code=400, detail="未知控制指令")
    return {"control": _save_control(state, action)}


@router.get("/progress")
def greeting_progress() -> dict:
    from app.services.workflow_tasks import load_tasks

    tasks = [task for task in load_tasks(limit=20) if task.get("type") == "greeting_send"]
    return {"control": _load_control(), "task": tasks[0] if tasks else None, "recent": tasks[:5]}


@router.get("/safety-summary")
def greeting_safety_summary() -> dict:
    records = load_send_records()
    settings = _load_settings()
    sent_today = count_sent_today()
    gray = _gray_mode_status(settings, records)
    failed_streak = 0
    for record in reversed(records):
        if record.get("status") in {"failed", "blocked"}:
            failed_streak += 1
            continue
        if record.get("status") == "sent":
            break
    checks = [
        {
            "key": "auto_send_enabled",
            "status": "ok" if settings["auto_send_enabled"] else "warn",
            "message": "真实自动发送已开启" if settings["auto_send_enabled"] else "真实自动发送默认关闭",
            "action": "发送前手动开启总开关",
        },
        {
            "key": "daily_limit",
            "status": "warn" if sent_today >= 15 else "ok",
            "message": f"今日已发送 {sent_today} 条",
            "action": "接近上限时暂停批量发送",
        },
        {
            "key": "failure_streak",
            "status": "error" if failed_streak >= 3 else "ok",
            "message": f"连续失败 {failed_streak} 次",
            "action": "连续失败 3 次后先检查登录、风控和页面结构",
        },
        {
            "key": "gray_mode",
            "status": "ok" if gray["batchAllowed"] else "warn",
            "message": gray["message"],
            "action": "先选择 1 个岗位真实发送，通过后再批量发送",
        },
    ]
    status = "blocked" if any(item["status"] == "error" for item in checks) else ("warn" if any(item["status"] == "warn" for item in checks) else "ok")
    return {
        "status": status,
        "settings": settings,
        "summary": {"sentToday": sent_today, "failedStreak": failed_streak, "totalRecords": len(records), "grayMode": gray},
        "checks": checks,
        "recommendations": [
            "自动发送前先运行预检，并确认本批岗位、话术和发送上限。",
            "连续失败时暂停自动发送，优先处理登录、页面风控或选择器变化。",
        ],
    }


@router.post("/final-confirmation")
def greeting_final_confirmation(payload: GreetingFinalConfirmationRequest) -> dict:
    job_index = _jobs_by_id()
    jobs = [job_index[job_id] for job_id in payload.job_ids if job_id in job_index]
    safety = greeting_safety_summary()
    gray = safety["summary"].get("grayMode") or {}
    sent_today = int(safety["summary"]["sentToday"])
    daily_limit = max(1, min(int(payload.daily_limit or 15), 100))
    remaining = max(0, daily_limit - sent_today)
    items = []
    for job in jobs:
        message = str(payload.messages.get(job.id) or "").strip()
        validation = validate_greeting(message)
        items.append({
            "jobId": job.id,
            "company": job.company,
            "title": job.title,
            "messageLength": len(message),
            "url": job.source_url,
            "valid": validation.ok,
            "reasons": validation.reasons,
        })
    risk_items = []
    if safety["status"] == "blocked":
        risk_items.append("连续失败较多，建议先暂停并检查 BOSS 登录、风控或页面结构。")
    invalid_count = sum(1 for item in items if not item["valid"])
    if invalid_count:
        risk_items.append(f"{invalid_count} 条话术未通过校验。")
    if len(items) > remaining:
        risk_items.append(f"本批 {len(items)} 条超过今日剩余额度 {remaining} 条。")
    if payload.mode == "browser_auto" and len(items) > 1 and not gray.get("batchAllowed", True):
        risk_items.append("灰度模式下，今天需先成功真实发送 1 个岗位，再开放批量发送。")
    return {
        "status": "blocked" if risk_items else "ok",
        "mode": payload.mode,
        "summary": {
            "jobCount": len(items),
            "validMessages": sum(1 for item in items if item["valid"]),
            "sentToday": sent_today,
            "dailyLimit": daily_limit,
            "remaining": remaining,
            "batchLimit": max(1, min(int(payload.batch_limit or 5), 20)),
        },
        "items": items,
        "links": [item["url"] for item in items if item["url"]],
        "riskItems": risk_items,
        "confirmText": f"将处理 {len(items)} 个岗位，今日剩余额度 {remaining} 条。请确认公司、链接和话术后再继续。",
    }


@router.post("/preflight")
def greeting_preflight(payload: GreetingPreflightRequest) -> dict:
    settings = _load_settings()
    gray = _gray_mode_status(settings)
    candidates = build_greeting_candidates(_all_jobs(), payload.job_ids)
    validations = validate_greetings(GreetingValidateRequest(
        items=[GreetingValidateItem(job_id=job_id, message=message) for job_id, message in payload.messages.items()]
    ))
    login_status = check_boss_login_status() if payload.mode == "browser_auto" else {"logged_in": True, "message": "人工确认模式无需检测 BOSS 页面", "reason": "manual"}
    checks = [
        {
            "key": "auto_send_enabled",
            "status": "ok" if payload.mode != "browser_auto" or settings["auto_send_enabled"] else "error",
            "message": "真实自动发送已开启" if settings["auto_send_enabled"] else "真实自动发送未开启",
            "action": "在打招呼工作台开启自动发送总开关",
        },
        {
            "key": "boss_login",
            "status": "ok" if login_status.get("logged_in") else "error",
            "message": str(login_status.get("message") or ""),
            "action": str(login_status.get("action") or ""),
        },
        {
            "key": "candidate_jobs",
            "status": "ok" if candidates["summary"]["candidateCount"] > 0 else "error",
            "message": f"可发送 {candidates['summary']['candidateCount']} 条，跳过 {candidates['summary']['skippedCount']} 条",
            "action": "补全 JD、检查黑名单和已沟通状态",
        },
        {
            "key": "message_validation",
            "status": "ok" if validations["summary"]["failed"] == 0 and validations["summary"]["ok"] > 0 else "error",
            "message": f"通过 {validations['summary']['ok']} 条，失败 {validations['summary']['failed']} 条",
            "action": "先修正未通过的话术",
        },
        {
            "key": "gray_mode",
            "status": "ok" if payload.mode != "browser_auto" or len(payload.job_ids) <= 1 or gray["batchAllowed"] else "error",
            "message": gray["message"],
            "action": "灰度模式下先发送 1 个岗位，成功后再批量发送",
        },
    ]
    status = "error" if any(item["status"] == "error" for item in checks) else "ok"
    return {
        "status": status,
        "checks": checks,
        "summary": {
            "total": len(checks),
            "ok": sum(1 for item in checks if item["status"] == "ok"),
            "error": sum(1 for item in checks if item["status"] == "error"),
        },
        "candidates": candidates,
        "validation": validations,
    }


@router.get("/stats")
def greeting_stats() -> dict:
    records = load_send_records()
    replies = _load_reply_records()
    sent = [record for record in records if record.get("status") == "sent"]
    failed = [record for record in records if record.get("status") in {"failed", "blocked"}]
    status_counts: dict[str, int] = {}
    for job in _all_jobs():
        status_counts[job.application_status] = status_counts.get(job.application_status, 0) + 1
    return {
        "summary": {
            "totalRecords": len(records),
            "sent": len(sent),
            "failed": len(failed),
            "replies": len(replies),
            "positiveReplies": sum(1 for item in replies if item.get("replyType") == "positive"),
            "replyTrackingReady": bool(status_counts),
        },
        "applicationStatuses": status_counts,
        "recent": records[-20:],
    }


@router.post("/selector-health")
def greeting_selector_health(payload: GreetingSelectorHealthRequest) -> dict:
    job = _jobs_by_id().get(payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="岗位不存在")
    result = check_boss_selector_health(job.source_url)
    return {
        "jobId": job.id,
        "title": job.title,
        "company": job.company,
        **result,
    }


@router.post("/acceptance-plan")
def greeting_acceptance_plan(payload: GreetingAcceptancePlanRequest) -> dict:
    job = _jobs_by_id().get(payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="岗位不存在")
    steps = [
        {"key": "open_job", "label": "打开岗位详情", "description": f"打开 {job.company} · {job.title} 的 BOSS 详情页"},
        {"key": "check_button", "label": "检查沟通按钮", "description": "确认页面能找到立即沟通、立即投递或继续沟通按钮"},
        {"key": "paste_message", "label": "填入招呼语", "description": "把当前草稿填入聊天输入框"},
        {"key": "confirm_send", "label": "人工确认发送", "description": "人工观察页面状态后，再决定是否点击发送"},
        {"key": "record_result", "label": "记录结果", "description": "根据结果更新岗位状态、发送记录和投递时间线"},
    ]
    return {"jobId": job.id, "title": job.title, "company": job.company, "sourceUrl": job.source_url, "steps": steps}


def _load_acceptance_records() -> list[dict]:
    data = workflow_persistence._read_json(_acceptance_records_file(), [])
    return data if isinstance(data, list) else []


def _save_acceptance_record(payload: GreetingAcceptanceRecordRequest) -> dict:
    record = {
        "id": f"acceptance-{int(time.time() * 1000)}",
        "jobId": payload.job_id,
        "result": payload.result if payload.result in {"passed", "failed", "partial"} else "partial",
        "operator": payload.operator,
        "note": payload.note,
        "checks": payload.checks,
        "createdAt": datetime.now().isoformat(),
    }
    records = _load_acceptance_records()
    workflow_persistence.write_json_atomic(_acceptance_records_file(), [record, *records][:200])
    return record


@router.get("/acceptance-records")
def list_acceptance_records(job_id: str = "") -> dict:
    records = _load_acceptance_records()
    if job_id:
        records = [item for item in records if item.get("jobId") == job_id]
    return {"summary": {"total": len(records)}, "records": records}


@router.post("/acceptance-records")
def save_acceptance_record(payload: GreetingAcceptanceRecordRequest) -> dict:
    if not payload.job_id:
        raise HTTPException(status_code=400, detail="缺少 job_id")
    record = _save_acceptance_record(payload)
    log_event("info", "greeting_acceptance", f"记录打招呼人工验收：{payload.job_id}", {"record": record})
    return {"record": record}


def _load_reply_records() -> list[dict]:
    data = workflow_persistence._read_json(_reply_records_file(), [])
    return data if isinstance(data, list) else []


def _save_reply_record(payload: GreetingReplyRecordRequest) -> dict:
    record = {
        "id": f"reply-{int(time.time() * 1000)}",
        "jobId": payload.job_id,
        "replyType": payload.reply_type if payload.reply_type in {"positive", "neutral", "negative"} else "neutral",
        "content": payload.content,
        "nextAction": payload.next_action,
        "createdAt": datetime.now().isoformat(),
    }
    records = _load_reply_records()
    workflow_persistence.write_json_atomic(_reply_records_file(), [record, *records][:500])
    return record


@router.get("/replies")
def list_reply_records(job_id: str = "") -> dict:
    records = _load_reply_records()
    if job_id:
        records = [item for item in records if item.get("jobId") == job_id]
    return {
        "summary": {
            "total": len(records),
            "positive": sum(1 for item in records if item.get("replyType") == "positive"),
            "neutral": sum(1 for item in records if item.get("replyType") == "neutral"),
            "negative": sum(1 for item in records if item.get("replyType") == "negative"),
        },
        "records": records,
    }


@router.post("/replies")
def save_reply_record(payload: GreetingReplyRecordRequest) -> dict:
    if not payload.job_id:
        raise HTTPException(status_code=400, detail="缺少 job_id")
    record = _save_reply_record(payload)
    log_event("info", "greeting_reply", f"记录 BOSS 回复：{payload.job_id}", {"record": record})
    return {"record": record}


def _job_type(title: str) -> str:
    text = str(title or "")
    for key in ("产品", "运营", "后端", "前端", "数据", "销售", "市场", "HR", "设计"):
        if key.lower() in text.lower():
            return key
    return "其他"


@router.get("/template-effectiveness")
def greeting_template_effectiveness() -> dict:
    jobs = _jobs_by_id()
    sent_records = [record for record in load_send_records() if record.get("status") == "sent"]
    replies = _load_reply_records()
    replies_by_job: dict[str, list[dict]] = {}
    for reply in replies:
        replies_by_job.setdefault(str(reply.get("jobId") or ""), []).append(reply)

    groups: dict[str, dict] = {}
    for record in sent_records:
        job_id = str(record.get("jobId") or "")
        job = jobs.get(job_id)
        job_type = _job_type(job.title if job else "")
        group = groups.setdefault(job_type, {
            "jobType": job_type,
            "sent": 0,
            "replies": 0,
            "positiveReplies": 0,
            "replyRate": 0,
            "positiveRate": 0,
            "avgLength": 0,
        })
        group["sent"] += 1
        group["avgLength"] += len(str(record.get("message") or ""))
        job_replies = replies_by_job.get(job_id, [])
        if job_replies:
            group["replies"] += 1
        if any(reply.get("replyType") == "positive" for reply in job_replies):
            group["positiveReplies"] += 1

    for group in groups.values():
        group["replyRate"] = round(group["replies"] / group["sent"] * 100) if group["sent"] else 0
        group["positiveRate"] = round(group["positiveReplies"] / group["sent"] * 100) if group["sent"] else 0
        group["avgLength"] = round(group["avgLength"] / group["sent"]) if group["sent"] else 0

    sent = len(sent_records)
    replied_jobs = {str(reply.get("jobId") or "") for reply in replies}
    positive_jobs = {str(reply.get("jobId") or "") for reply in replies if reply.get("replyType") == "positive"}
    return {
        "summary": {
            "sent": sent,
            "replies": len(replied_jobs),
            "positiveReplies": len(positive_jobs),
            "replyRate": round(len(replied_jobs) / sent * 100) if sent else 0,
            "positiveRate": round(len(positive_jobs) / sent * 100) if sent else 0,
        },
        "byJobType": sorted(groups.values(), key=lambda item: (item["positiveRate"], item["replyRate"], item["sent"]), reverse=True),
        "recommendations": [
            "优先复用高回复率岗位类型的话术结构。",
            "低回复率类型建议缩短话术并突出 1 个岗位命中点。",
        ],
    }


@router.get("/followups")
def greeting_followups(now: str = "") -> dict:
    from datetime import timezone

    try:
        now_dt = datetime.fromisoformat(now.replace("Z", "+00:00")) if now else datetime.now(timezone.utc)
    except ValueError:
        now_dt = datetime.now(timezone.utc)
    jobs = _jobs_by_id()
    items = []
    for record in load_send_records():
        if record.get("status") != "sent":
            continue
        job = jobs.get(str(record.get("jobId") or ""))
        if not job or job.application_status not in {"greeted", "pending"}:
            continue
        try:
            sent_at = datetime.fromisoformat(str(record.get("updatedAt") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        hours = int((now_dt - sent_at).total_seconds() // 3600)
        if hours < 24:
            continue
        window = 72 if hours >= 72 else 48 if hours >= 48 else 24
        items.append({
            "jobId": job.id,
            "title": job.title,
            "company": job.company,
            "sentAt": record.get("updatedAt"),
            "windowHours": window,
            "status": "pending_followup",
            "suggestion": f"已发送 {hours} 小时暂无新状态，建议检查 BOSS 消息或更新求职状态",
        })
    return {"summary": {"pendingFollowups": len(items)}, "items": items}


def _failure_category(record: dict) -> tuple[str, str, str]:
    text = f"{record.get('failureCode') or ''} {record.get('note') or ''} {record.get('failureMessage') or ''}".lower()
    if any(key in text for key in ("risk", "captcha", "验证码", "风控")):
        return ("risk_control", "页面风控", "暂停自动发送，人工检查 BOSS 页面后再重试")
    if any(key in text for key in ("button", "selector", "输入框", "按钮", "页面结构")):
        return ("page_changed", "页面结构变化", "先运行页面可用性检测，再更新选择器或转人工")
    if any(key in text for key in ("login", "cookie", "未登录", "登录")):
        return ("login", "登录状态异常", "重新登录 BOSS 并刷新安全阈值")
    if any(key in text for key in ("network", "timeout", "网络", "超时")):
        return ("network", "网络失败", "检查网络后重试失败任务")
    if "validation" in text or "校验" in text:
        return ("validation", "话术校验失败", "修改招呼语后再发送")
    return ("unknown", "其他失败", "查看失败记录并选择重试或转人工")


@router.get("/recovery-panel")
def greeting_recovery_panel() -> dict:
    failed = [record for record in load_send_records() if record.get("status") in {"failed", "blocked"}]
    groups: dict[str, dict] = {}
    for record in failed:
        category, label, action = _failure_category(record)
        group = groups.setdefault(category, {
            "category": category,
            "label": label,
            "action": action,
            "count": 0,
            "retryable": 0,
            "records": [],
        })
        group["count"] += 1
        if category in {"network", "page_changed", "login", "unknown"}:
            group["retryable"] += 1
        group["records"].append(record)
    ordered = sorted(groups.values(), key=lambda item: (-item["count"], item["category"]))
    for group in ordered:
        group["records"] = group["records"][-10:]
    return {
        "summary": {
            "failed": len(failed),
            "groups": len(ordered),
            "retryable": sum(int(group["retryable"]) for group in ordered),
        },
        "groups": ordered,
        "recommendations": [
            "风控和验证码优先转人工，不连续重试。",
            "页面结构变化先做页面可用性检测，再决定是否继续自动发送。",
            "网络失败可在灰度模式下重试单条。",
        ],
    }


@router.post("/candidates")
def greeting_candidates(payload: GreetingCandidateRequest) -> dict:
    return build_greeting_candidates(_all_jobs(), payload.job_ids)


@router.post("/validate")
def validate_greetings(payload: GreetingValidateRequest) -> dict:
    recent_messages = [str(record.get("message") or "") for record in load_send_records()]
    results = []
    for item in payload.items:
        validation = validate_greeting(item.message, recent_messages=recent_messages)
        results.append({
            "jobId": item.job_id,
            "ok": validation.ok,
            "reasons": validation.reasons,
            "length": len(item.message or ""),
        })
    return {
        "results": results,
        "summary": {
            "total": len(results),
            "ok": sum(1 for item in results if item["ok"]),
            "failed": sum(1 for item in results if not item["ok"]),
        },
    }


@router.post("/dry-run")
def dry_run_greetings(payload: GreetingDryRunRequest) -> dict:
    job_index = _jobs_by_id()
    candidates = build_greeting_candidates(list(job_index.values()), payload.job_ids)
    drafts = load_greetings()
    records = []
    for candidate in candidates["candidates"]:
        job = job_index.get(candidate["jobId"])
        if not job:
            continue
        message = generate_greeting(job, resume_summary=payload.resume_summary, style=payload.style)
        record = build_greeting_record(job, message, status="draft", dry_run=True)
        drafts[job.id] = message
        save_send_record(job.id, record["status"], "dry-run 生成草稿，未真实发送", message=message, dry_run=True)
        records.append(record)
    save_greetings({str(k): str(v) for k, v in drafts.items()})
    return {
        "summary": {
            "total": candidates["summary"]["total"],
            "drafted": len(records),
            "sent": 0,
            "skipped": len(candidates["skipped"]),
            "failed": sum(1 for item in records if item["status"] == "failed"),
        },
        "records": records,
        "skipped": candidates["skipped"],
    }


def _append_application_history(job, status: str, previous: str, note: str) -> dict:
    entry = {
        "kind": "application",
        "status": status,
        "previous": previous,
        "note": note,
        "at": datetime.now().isoformat(),
    }
    job.status_history = [*(job.status_history or []), entry][-100:]
    return entry


def _save_jobs():
    from app.routes.jobs import _save_jobs as jobs_save

    jobs_save()


def execute_browser_greeting(job, message: str) -> dict:
    from app.services.boss_scraper import send_boss_greeting_sync

    return send_boss_greeting_sync(job.source_url, message)


def sleep_between_greetings(seconds: int) -> None:
    time.sleep(max(0, min(int(seconds or 0), 30)))


def _skip_item(job, reason: str) -> dict:
    return {
        "jobId": job.id,
        "title": job.title,
        "company": job.company,
        "city": job.city,
        "salary": job.salary,
        "decisionStatus": job.decision_status,
        "applicationStatus": job.application_status,
        "jdReady": bool((job.jd_text or "").strip()),
        "riskLevel": "high" if job.decision_status == "risky" else "normal",
        "reason": reason,
    }


@router.post("/send")
def send_greetings(payload: GreetingSendRequest) -> dict:
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="发送前必须人工确认")
    if payload.mode not in {"manual_confirm", "browser_auto"}:
        raise HTTPException(status_code=403, detail="未知发送模式")
    settings = _load_settings()
    if payload.mode == "browser_auto" and not settings["auto_send_enabled"]:
        raise HTTPException(status_code=403, detail="真实自动发送未开启，请先打开自动发送总开关")

    job_index = _jobs_by_id()
    requested_ids = [job_id for job_id in payload.job_ids if job_id in job_index]
    gray = _gray_mode_status(settings)
    if payload.mode == "browser_auto" and len(requested_ids) > 1 and not gray["batchAllowed"]:
        raise HTTPException(status_code=403, detail="灰度模式要求今天先成功真实发送 1 个岗位，再开放批量发送")
    task = start_task(
        "greeting_send",
        "确认打招呼",
        total=len(requested_ids),
        payload={"job_ids": requested_ids, "mode": payload.mode, "messages": payload.messages},
        idempotency_key=f"greeting_send:{','.join(sorted(requested_ids))}:{payload.mode}",
    )

    drafts = load_greetings()
    candidates = build_greeting_candidates(list(job_index.values()), requested_ids)
    candidate_ids = {item["jobId"] for item in candidates["candidates"]}
    skipped = list(candidates["skipped"])
    records = []
    sent = 0
    batch_limit = max(1, min(int(payload.batch_limit or 5), 20))
    daily_limit = max(1, min(int(payload.daily_limit or 15), 100))
    remaining = max(0, daily_limit - count_sent_today())
    send_interval_seconds = max(0, min(int(payload.send_interval_seconds or 0), 30))
    blocked_batch = False
    failed_job_ids: list[str] = []
    failed_messages: dict[str, str] = {}

    for index, job_id in enumerate(requested_ids):
        job = job_index[job_id]
        control = _load_control()
        if control["state"] in {"paused", "stopped"}:
            skipped.append(_skip_item(job, "paused_by_user" if control["state"] == "paused" else "stopped_by_user"))
            blocked_batch = True
            continue
        if blocked_batch:
            if job_id in candidate_ids:
                skipped.append(_skip_item(job, "paused_after_blocked"))
            continue
        if job_id not in candidate_ids:
            continue
        if sent >= batch_limit or sent >= remaining:
            skipped.append(_skip_item(job, "rate_limited"))
            continue

        message = (payload.messages.get(job_id) or drafts.get(job_id) or "").strip()
        validation = validate_greeting(message)
        if not validation.ok:
            record = build_greeting_record(job, message, status="failed", dry_run=False)
            record["failureCode"] = "validation_failed"
            record["failureMessage"] = "发送前校验未通过"
            save_send_record(job.id, "failed", "发送前校验未通过", message=message, dry_run=False)
            records.append(record)
            failed_job_ids.append(job.id)
            failed_messages[job.id] = message
            continue

        if payload.mode == "browser_auto":
            update_task(task["id"], done=sent, message=f"正在发送：{job.company} · {job.title}", payload={**(task.get("payload") or {}), "current_job_id": job.id})
            send_result = execute_browser_greeting(job, message)
            if not send_result.get("ok"):
                status = str(send_result.get("status") or "failed")
                record = build_greeting_record(job, message, status=status, dry_run=False)
                record["status"] = "blocked" if status == "blocked" else "failed"
                record["failureCode"] = str(send_result.get("failureCode") or "browser_send_failed")
                record["failureMessage"] = str(send_result.get("message") or "自动发送失败")
                save_send_record(job.id, record["status"], record["failureMessage"], message=message, dry_run=False)
                records.append(record)
                failed_job_ids.append(job.id)
                failed_messages[job.id] = message
                if record["status"] == "blocked" and payload.stop_on_blocked:
                    blocked_batch = True
                continue

        previous = job.application_status
        job.greeted = True
        job.application_status = "greeted"
        job.application_note = "自动发送已完成" if payload.mode == "browser_auto" else "人工确认已打招呼"
        job.application_updated_at = datetime.now().isoformat()
        entry = _append_application_history(job, "greeted", previous, job.application_note)
        record = build_greeting_record(job, message, status="sent", dry_run=False)
        save_send_record(job.id, "sent", job.application_note, message=message, dry_run=False)
        records.append(record)
        sent += 1
        update_task(task["id"], done=sent, message=f"已完成 {sent}/{len(requested_ids)}", payload={**(task.get("payload") or {}), "current_job_id": job.id})
        log_event("info", "greeting_send", f"确认已打招呼：{job.company} · {job.title}", {"jobId": job.id, "entry": entry})
        if payload.mode == "browser_auto" and send_interval_seconds and any(
            next_id in candidate_ids for next_id in requested_ids[index + 1:]
        ):
            sleep_between_greetings(send_interval_seconds)

    _save_jobs()
    failed = sum(1 for item in records if item["status"] in {"failed", "blocked"})
    summary = {
        "total": len(requested_ids),
        "sent": sent,
        "failed": failed,
        "skipped": len(skipped),
        "dailyLimit": daily_limit,
        "batchLimit": batch_limit,
        "remainingBeforeSend": remaining,
    }
    if failed or skipped:
        partial_fail_task(task["id"], sent, len(requested_ids), "打招呼确认部分完成", "GREETING_PARTIAL", "检查跳过和失败原因后重试")
        update_task(
            task["id"],
            payload={
                **(task.get("payload") or {}),
                "failed_job_ids": failed_job_ids,
                "failed_messages": failed_messages,
                "skipped": skipped,
            },
        )
    else:
        complete_task(task["id"], done=sent, message="打招呼确认完成")
    return {"summary": summary, "records": records, "skipped": skipped, "taskId": task["id"]}


@router.post("/retry-failed/{task_id}")
def retry_failed_greetings(task_id: str) -> dict:
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}
    failed_job_ids = payload.get("failed_job_ids") or []
    failed_messages = payload.get("failed_messages") if isinstance(payload.get("failed_messages"), dict) else {}
    if not failed_job_ids:
        raise HTTPException(status_code=400, detail="任务中没有可重试的失败岗位")
    return send_greetings(GreetingSendRequest(
        job_ids=[str(item) for item in failed_job_ids],
        messages={str(k): str(v) for k, v in failed_messages.items()},
        confirm=True,
        mode=str(payload.get("mode") or "browser_auto"),
        batch_limit=len(failed_job_ids),
        daily_limit=15,
        send_interval_seconds=5,
        stop_on_blocked=True,
    ))


@router.get("/drafts")
def get_greeting_drafts() -> dict:
    return {"greetings": load_greetings()}


@router.post("/drafts")
def save_greeting_drafts(payload: dict) -> dict:
    greetings = payload.get("greetings", {})
    if not isinstance(greetings, dict):
        raise HTTPException(status_code=400, detail="greetings 必须是对象")
    return {"greetings": save_greetings({str(k): str(v) for k, v in greetings.items()})}


@router.get("/send-records")
def get_send_records() -> dict:
    return {"records": load_send_records()}


@router.post("/send-records")
def confirm_send_record(payload: dict) -> dict:
    job_id = str(payload.get("job_id", "")).strip()
    status = str(payload.get("status", "sent")).strip() or "sent"
    note = str(payload.get("note", "")).strip()
    if not job_id:
        raise HTTPException(status_code=400, detail="缺少 job_id")
    return {"record": save_send_record(job_id, status, note)}
