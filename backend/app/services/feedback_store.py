from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services import workflow_persistence


ALLOWED_DOMAINS = {
    "ranking",
    "diligence",
    "jd_quality",
    "greeting",
    "deep_report",
    "resume_pdf",
    "report_pdf",
}


def _feedback_file():
    return workflow_persistence.DATA_DIR / "feedback" / "items.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_domain(domain: str) -> str:
    value = str(domain or "").strip()
    if value not in ALLOWED_DOMAINS:
        raise ValueError("unsupported feedback domain")
    return value


def list_feedback(domain: str = "", target_id: str = "") -> list[dict[str, Any]]:
    data = workflow_persistence._read_json(_feedback_file(), [])
    records = data if isinstance(data, list) else []
    if domain:
        records = [item for item in records if item.get("domain") == domain]
    if target_id:
        records = [item for item in records if item.get("targetId") == target_id]
    return sorted(records, key=lambda item: str(item.get("updatedAt") or ""), reverse=True)


def save_feedback(
    domain: str,
    target_id: str,
    useful: bool,
    note: str = "",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_domain = _normalize_domain(domain)
    normalized_target = str(target_id or "").strip()
    if not normalized_target:
        raise ValueError("target_id is required")

    records = list_feedback()
    record_id = f"{normalized_domain}:{normalized_target}"
    existing = next((item for item in records if item.get("id") == record_id), {})
    record = {
        **existing,
        "id": record_id,
        "domain": normalized_domain,
        "targetId": normalized_target,
        "useful": bool(useful),
        "note": str(note or "").strip(),
        "context": context if isinstance(context, dict) else {},
        "updatedAt": _now(),
    }
    next_records = [item for item in records if item.get("id") != record_id] + [record]
    workflow_persistence.write_json_atomic(_feedback_file(), next_records)
    return record


def feedback_summary() -> dict[str, Any]:
    records = list_feedback()
    by_domain: dict[str, dict[str, int]] = {
        domain: {"total": 0, "useful": 0, "notUseful": 0} for domain in sorted(ALLOWED_DOMAINS)
    }
    for item in records:
        domain = str(item.get("domain") or "")
        if domain not in by_domain:
            by_domain[domain] = {"total": 0, "useful": 0, "notUseful": 0}
        by_domain[domain]["total"] += 1
        if item.get("useful") is True:
            by_domain[domain]["useful"] += 1
        else:
            by_domain[domain]["notUseful"] += 1
    return {
        "summary": {
            "total": len(records),
            "useful": sum(1 for item in records if item.get("useful") is True),
            "notUseful": sum(1 for item in records if item.get("useful") is not True),
        },
        "byDomain": by_domain,
        "recent": records[:10],
        "generatedAt": _now(),
    }


def feedback_guidance(domains: set[str] | None = None) -> dict[str, Any]:
    records = list_feedback()
    if domains:
        records = [item for item in records if item.get("domain") in domains]
    negative = [item for item in records if item.get("useful") is not True]
    notes = [str(item.get("note") or "").strip() for item in negative if str(item.get("note") or "").strip()]
    labels = {
        "ranking": "排序结论",
        "diligence": "公司尽调",
        "jd_quality": "JD 分析",
        "greeting": "打招呼语",
        "deep_report": "深度报告",
        "resume_pdf": "简历 PDF",
        "report_pdf": "报告 PDF",
    }
    signals = [
        f"{labels.get(str(item.get('domain') or ''), 'AI 输出')}近期有需改反馈，生成时应更具体、更可追溯。"
        for item in negative[:8]
    ]
    return {
        "summary": {
            "total": len(records),
            "useful": len(records) - len(negative),
            "notUseful": len(negative),
        },
        "recentNotes": notes[:5],
        "signals": list(dict.fromkeys(signals))[:5],
        "generatedAt": _now(),
    }


def preference_profile() -> dict[str, Any]:
    records = list_feedback()
    domains: dict[str, dict[str, int]] = {}
    weight_hints = {"company": 0, "match": 0}
    job_types: dict[str, int] = {}
    recent_needs: list[str] = []
    for item in records:
        domain = str(item.get("domain") or "")
        domains.setdefault(domain, {"total": 0, "useful": 0, "notUseful": 0})
        domains[domain]["total"] += 1
        if item.get("useful") is True:
            domains[domain]["useful"] += 1
        else:
            domains[domain]["notUseful"] += 1
            note = str(item.get("note") or "").strip()
            if note:
                recent_needs.append(note)
        context = item.get("context") if isinstance(item.get("context"), dict) else {}
        preference = str(context.get("weightPreference") or "").strip()
        if preference in weight_hints and item.get("useful") is not True:
            weight_hints[preference] += 1
        job_type = str(context.get("jobType") or context.get("title") or "").strip()
        if job_type:
            job_types[job_type] = job_types.get(job_type, 0) + 1
    dominant = "balanced"
    if weight_hints["company"] > weight_hints["match"]:
        dominant = "company_risk"
    elif weight_hints["match"] > weight_hints["company"]:
        dominant = "resume_match"
    return {
        "summary": feedback_summary()["summary"],
        "domains": domains,
        "weightHints": weight_hints,
        "dominantPreference": dominant,
        "jobTypes": job_types,
        "recentNeeds": recent_needs[:8],
        "generatedAt": _now(),
    }
