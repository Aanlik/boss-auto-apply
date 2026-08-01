from __future__ import annotations

import re
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher

from app.models.job import JobRecord
from app.services.company_blacklist import is_company_blacklisted
from app.services.ai_client import chat_json
from app.services.workflow_persistence import load_send_records


MIN_GREETING_LEN = 20
MAX_GREETING_LEN = 280
AI_ERROR_BLACKLIST = (
    "Error",
    "Traceback",
    "As an AI",
    "I'm an AI",
    "I cannot",
    "```",
    "抱歉，作为",
    "抱歉，我是",
)
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_TEMPLATE_RE = re.compile(r"(\{\{[^{}]+\}\}|\{[a-zA-Z_][^{}]*\})")


@dataclass
class GreetingValidation:
    ok: bool
    reasons: list[str] = field(default_factory=list)


def validate_greeting(message: str, recent_messages: list[str] | None = None) -> GreetingValidation:
    text = (message or "").strip()
    reasons: list[str] = []
    if not text:
        reasons.append("empty")
    if len(text) < MIN_GREETING_LEN:
        reasons.append(f"too_short:{len(text)}")
    if len(text) > MAX_GREETING_LEN:
        reasons.append(f"too_long:{len(text)}")
    if text and not _CJK_RE.search(text):
        reasons.append("no_chinese_characters")
    for needle in AI_ERROR_BLACKLIST:
        if needle in text:
            reasons.append(f"blacklist:{needle}")
            break
    if _TEMPLATE_RE.search(text):
        reasons.append("unresolved_template_variable")
    for previous in recent_messages or []:
        ratio = SequenceMatcher(None, text, previous or "").ratio()
        if text and previous and ratio >= 0.92:
            reasons.append("too_similar_to_recent_message")
            break
    return GreetingValidation(ok=not reasons, reasons=reasons)


def _sent_record_index() -> dict[str, dict]:
    return {str(record.get("jobId") or ""): record for record in load_send_records()}


def build_greeting_candidates(jobs: list[JobRecord], requested_ids: list[str] | None = None) -> dict:
    requested = {str(item) for item in requested_ids or [] if str(item)}
    sent_records = _sent_record_index()
    candidates: list[dict] = []
    skipped: list[dict] = []
    seen_company_title_hr: set[str] = set()

    for job in jobs:
        if requested and job.id not in requested:
            continue
        reason = ""
        if is_company_blacklisted(job.company) or job.lifecycle_status == "blacklisted":
            reason = "blacklisted_company"
        elif job.greeted or job.application_status in {"greeted", "applied", "interviewing"}:
            reason = "already_contacted"
        elif sent_records.get(job.id, {}).get("status") == "sent":
            reason = "already_contacted"
        elif not (job.jd_text or "").strip():
            reason = "missing_jd"
        elif not (job.source_url or "").strip():
            reason = "missing_job_url"
        else:
            dedupe_key = f"{job.company}|{job.title}|{job.city}".lower()
            if dedupe_key in seen_company_title_hr:
                reason = "duplicate_candidate"
            else:
                seen_company_title_hr.add(dedupe_key)

        item = {
            "jobId": job.id,
            "title": job.title,
            "company": job.company,
            "city": job.city,
            "salary": job.salary,
            "decisionStatus": job.decision_status,
            "applicationStatus": job.application_status,
            "jdReady": bool((job.jd_text or "").strip()),
            "riskLevel": "high" if job.decision_status == "risky" else "normal",
        }
        if reason:
            skipped.append({**item, "reason": reason})
        else:
            candidates.append(item)
    return {
        "candidates": candidates,
        "skipped": skipped,
        "summary": {
            "total": len(candidates) + len(skipped),
            "candidateCount": len(candidates),
            "skippedCount": len(skipped),
        },
    }


def generate_greeting(job: JobRecord, resume_summary: str = "", style: str = "稳妥自然") -> str:
    skills = "、".join((job.keywords or [])[:3])
    if not skills:
        jd_words = re.findall(r"[\u4e00-\u9fffA-Za-z]{2,}", job.jd_text or "")
        stop_words = {"负责", "岗位", "要求", "工作", "相关", "能力", "经验", "公司"}
        skills = "、".join([word for word in jd_words if word not in stop_words][:3])
    if not skills:
        skills = "岗位要求"
    resume_hint = ""
    if resume_summary:
        resume_hint = f"我的经历与{resume_summary[:28]}相关，"
    style_hint = "也很认可岗位方向" if style == "稳妥自然" else "希望更深入了解业务和团队"
    return (
        f"您好，我对贵司的「{job.title}」岗位很感兴趣。"
        f"{resume_hint}过往关注{skills}等内容，{style_hint}，"
        "希望有机会进一步沟通，谢谢。"
    )


def generate_greeting_with_ai(
    job: JobRecord,
    resume: dict | None = None,
    jd_analysis: dict | None = None,
    style: str = "稳妥自然",
) -> str:
    """根据岗位 JD、JD 分析和简历生成可直接发送的个性化话术。"""
    resume = resume if isinstance(resume, dict) else {}
    jd_analysis = jd_analysis if isinstance(jd_analysis, dict) else {}
    system = (
        "你是一名专业的求职沟通顾问。请根据岗位 JD、岗位分析和候选人简历，生成一条真实、"
        "简洁、自然的中文 BOSS 直聘首句打招呼话术。必须突出 1-2 个岗位要求与候选人经历的真实匹配点，"
        "不能编造简历中没有的经历，不能提及你是 AI，不要使用模板变量，不要写标题或解释。"
        "控制在 45-100 个汉字，结尾自然表达希望进一步沟通。"
    )
    user = json.dumps({
        "style": style,
        "job": {
            "title": job.title,
            "company": job.company,
            "jd": job.jd_text or "",
            "keywords": job.keywords or [],
        },
        "jd_analysis": jd_analysis,
        "resume": resume,
        "output_schema": {"message": "string"},
    }, ensure_ascii=False)
    result = chat_json(system, user, temperature=0.7)
    message = str(result.get("message") or result.get("greeting") or "").strip() if isinstance(result, dict) else ""
    validation = validate_greeting(message)
    if not validation.ok:
        raise ValueError(f"AI 生成的话术未通过校验: {', '.join(validation.reasons)}")
    return message


def build_greeting_record(job: JobRecord, message: str, status: str = "draft", dry_run: bool = True) -> dict:
    validation = validate_greeting(message)
    return {
        "jobId": job.id,
        "company": job.company,
        "title": job.title,
        "status": status if validation.ok else "failed",
        "message": message,
        "validationOk": validation.ok,
        "validationReasons": validation.reasons,
        "dryRun": dry_run,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


def count_sent_today(records: list[dict] | None = None) -> int:
    today = datetime.now(timezone.utc).date()
    total = 0
    for record in records if records is not None else load_send_records():
        if record.get("status") != "sent":
            continue
        updated_at = str(record.get("updatedAt") or "")
        try:
            if datetime.fromisoformat(updated_at.replace("Z", "+00:00")).date() == today:
                total += 1
        except ValueError:
            continue
    return total
