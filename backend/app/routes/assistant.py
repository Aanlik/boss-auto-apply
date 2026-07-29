from __future__ import annotations

import json
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Response

from app.services.career_assistant import (
    application_strategy,
    followup_reminders,
    interview_prep,
    jd_quality,
    resume_rewrite_advice,
    risk_explanation,
)
from app.services.workflow_persistence import load_send_records
from app.services.workflow_persistence import _read_json, write_json_atomic
from app.services import workflow_persistence
from app.services.feedback_store import feedback_guidance
from app.services.preferences import load_preferences
from app.services.scoring import build_preference_signals


router = APIRouter(prefix="/api/assistant", tags=["assistant"])


def _results_file():
    return workflow_persistence.DATA_DIR / "assistant" / "results.json"


def _prompt_versions_file():
    return workflow_persistence.DATA_DIR / "assistant" / "prompt_versions.json"


def _save_prompt_version(job: dict, kind: str, prompt_version: str, system_prompt: str, payload: dict, guidance: dict) -> dict:
    rows = _read_json(_prompt_versions_file(), [])
    if not isinstance(rows, list):
        rows = []
    record = {
        "id": f"{kind}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "jobId": str(job.get("id") or ""),
        "company": str(job.get("company") or ""),
        "title": str(job.get("title") or ""),
        "kind": kind,
        "promptVersion": prompt_version,
        "promptPreview": system_prompt[:220],
        "payloadSummary": {
            "hasResume": bool(payload.get("rewrite") or payload.get("resume")),
            "hasDiligence": bool(payload.get("risk") or payload.get("diligence")),
            "preferenceSignals": len(payload.get("preferenceSignals") or []),
        },
        "feedbackGuidance": guidance,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    rows.append(record)
    write_json_atomic(_prompt_versions_file(), rows[-200:])
    return record


def _save_result(job: dict, kind: str, result: dict) -> dict:
    payload = _read_json(_results_file(), [])
    if not isinstance(payload, list):
        payload = []
    record = {
        "jobId": str(job.get("id") or ""),
        "company": str(job.get("company") or ""),
        "title": str(job.get("title") or ""),
        "kind": kind,
        "result": result,
    }
    payload.append(record)
    write_json_atomic(_results_file(), payload[-200:])
    return result


@router.post("/application-strategy")
def get_application_strategy(payload: dict) -> dict:
    job = payload.get("job") if isinstance(payload.get("job"), dict) else None
    if not job and payload.get("job_id"):
        from app.routes.jobs import _job_store
        stored = _job_store.get(str(payload.get("job_id")))
        job = stored.model_dump() if stored else None
    if not job:
        raise HTTPException(status_code=404, detail="岗位不存在")
    result = application_strategy(
        job=job,
        resume=payload.get("resume") if isinstance(payload.get("resume"), dict) else {},
        diligence=payload.get("diligence") if isinstance(payload.get("diligence"), dict) else {},
        ranking=payload.get("ranking") if isinstance(payload.get("ranking"), dict) else {},
    )
    return _save_result(job, "application_strategy", result)


@router.post("/jd-quality")
def analyze_jd_quality(payload: dict) -> dict:
    job = payload.get("job") if isinstance(payload.get("job"), dict) else payload
    job = job if isinstance(job, dict) else {}
    return _save_result(job, "jd_quality", jd_quality(job))


@router.post("/resume-rewrite-advice")
def get_resume_rewrite_advice(payload: dict) -> dict:
    job = payload.get("job") if isinstance(payload.get("job"), dict) else {}
    result = resume_rewrite_advice(
        job=job,
        resume=payload.get("resume") if isinstance(payload.get("resume"), dict) else {},
        diligence=payload.get("diligence") if isinstance(payload.get("diligence"), dict) else {},
    )
    return _save_result(job, "resume_rewrite", result)


@router.post("/interview-prep")
def get_interview_prep(payload: dict) -> dict:
    job = payload.get("job") if isinstance(payload.get("job"), dict) else {}
    result = interview_prep(
        job=job,
        resume=payload.get("resume") if isinstance(payload.get("resume"), dict) else {},
        diligence=payload.get("diligence") if isinstance(payload.get("diligence"), dict) else {},
    )
    return _save_result(job, "interview_prep", result)


@router.get("/followups")
def get_followups() -> dict:
    from app.routes.jobs import _all_jobs
    jobs = [job.model_dump() for job in _all_jobs()]
    return followup_reminders(jobs, load_send_records())


@router.post("/risk-explanation")
def explain_risk(payload: dict) -> dict:
    diligence = payload.get("diligence") if isinstance(payload.get("diligence"), dict) else payload
    result = risk_explanation(diligence if isinstance(diligence, dict) else {})
    return _save_result({"company": (diligence or {}).get("companyName", "") if isinstance(diligence, dict) else ""}, "risk_explanation", result)


@router.get("/results")
def get_assistant_results(job_id: str = "", kind: str = "") -> dict:
    rows = _read_json(_results_file(), [])
    if not isinstance(rows, list):
        rows = []
    if job_id:
        rows = [row for row in rows if row.get("jobId") == job_id]
    if kind:
        rows = [row for row in rows if row.get("kind") == kind]
    return {"results": list(reversed(rows))[:50]}


@router.get("/prompt-versions")
def get_prompt_versions(kind: str = "", job_id: str = "") -> dict:
    rows = _read_json(_prompt_versions_file(), [])
    if not isinstance(rows, list):
        rows = []
    if kind:
        rows = [row for row in rows if row.get("kind") == kind]
    if job_id:
        rows = [row for row in rows if row.get("jobId") == job_id]
    rows = list(reversed(rows))[:100]
    return {
        "summary": {
            "total": len(rows),
            "deepReport": sum(1 for row in rows if row.get("kind") == "deep_report"),
        },
        "versions": rows,
    }


@router.delete("/prompt-versions")
def clear_prompt_versions(kind: str = "", job_id: str = "") -> dict:
    rows = _read_json(_prompt_versions_file(), [])
    if not isinstance(rows, list):
        rows = []
    kept = [
        row for row in rows
        if (kind and row.get("kind") != kind) or (job_id and row.get("jobId") != job_id)
    ]
    if not kind and not job_id:
        kept = []
    deleted = len(rows) - len(kept)
    write_json_atomic(_prompt_versions_file(), kept)
    return {
        "deleted": deleted,
        "remaining": len(kept),
    }


@router.delete("/prompt-versions/{record_id}")
def delete_prompt_version(record_id: str) -> dict:
    rows = _read_json(_prompt_versions_file(), [])
    if not isinstance(rows, list):
        rows = []
    kept = [row for row in rows if str(row.get("id") or "") != record_id]
    if len(kept) == len(rows):
        raise HTTPException(status_code=404, detail="版本记录不存在")
    write_json_atomic(_prompt_versions_file(), kept)
    return {
        "deleted": True,
        "remaining": len(kept),
    }


@router.get("/prompt-versions/compare")
def compare_prompt_versions(job_id: str = "", kind: str = "deep_report") -> dict:
    rows = _read_json(_prompt_versions_file(), [])
    if not isinstance(rows, list):
        rows = []
    filtered = [row for row in rows if (not job_id or row.get("jobId") == job_id) and (not kind or row.get("kind") == kind)]
    latest = list(reversed(filtered))[:2]
    comparable = len(latest) == 2
    first = latest[0] if latest else {}
    second = latest[1] if len(latest) > 1 else {}
    return {
        "summary": {
            "jobId": job_id,
            "kind": kind,
            "totalVersions": len(filtered),
            "comparable": comparable,
        },
        "versions": latest,
        "differences": {
            "samePromptVersion": comparable and first.get("promptVersion") == second.get("promptVersion"),
            "preferenceSignalDelta": (
                int((first.get("payloadSummary") or {}).get("preferenceSignals") or 0)
                - int((second.get("payloadSummary") or {}).get("preferenceSignals") or 0)
            ) if comparable else 0,
            "latestFeedbackNotes": (first.get("feedbackGuidance") or {}).get("recentNotes") or [],
            "previousFeedbackNotes": (second.get("feedbackGuidance") or {}).get("recentNotes") or [],
        },
    }


def _latest_deep_report(job_id: str = "") -> dict | None:
    rows = _read_json(_results_file(), [])
    if not isinstance(rows, list):
        return None
    for row in reversed(rows):
        if row.get("kind") != "deep_report":
            continue
        if job_id and row.get("jobId") != job_id:
            continue
        return row
    return None


def _replace_deep_report(updated: dict) -> None:
    rows = _read_json(_results_file(), [])
    if not isinstance(rows, list):
        rows = []
    for idx in range(len(rows) - 1, -1, -1):
        row = rows[idx]
        if row.get("kind") == "deep_report" and row.get("jobId") == updated.get("jobId"):
            rows[idx] = updated
            write_json_atomic(_results_file(), rows[-200:])
            return
    rows.append(updated)
    write_json_atomic(_results_file(), rows[-200:])


def _score_deep_report_quality(record: dict) -> dict:
    result = record.get("result") if isinstance(record.get("result"), dict) else {}
    strategy = result.get("strategy") if isinstance(result.get("strategy"), dict) else {}
    jd_quality = result.get("jdQuality") if isinstance(result.get("jdQuality"), dict) else {}
    risk = result.get("risk") if isinstance(result.get("risk"), dict) else {}
    ai_report = result.get("aiReport") if isinstance(result.get("aiReport"), dict) else {}
    guidance = result.get("feedbackGuidance") if isinstance(result.get("feedbackGuidance"), dict) else {}
    checks = [
        {"key": "strategy", "label": "投递策略", "passed": bool(strategy.get("reasons") or strategy.get("nextActions"))},
        {"key": "jd", "label": "结合 JD", "passed": bool(jd_quality.get("signals") or jd_quality.get("cleaningAdvice"))},
        {"key": "risk", "label": "结合公司风险", "passed": bool(risk.get("impact") or risk.get("questionsToAsk") or risk.get("plainLanguage"))},
        {"key": "actions", "label": "行动建议", "passed": bool(strategy.get("nextActions") or ai_report.get("interviewAdvice") or ai_report.get("riskAdvice"))},
        {"key": "feedback", "label": "吸收反馈", "passed": bool((guidance.get("summary") or {}).get("total") or guidance.get("recentNotes"))},
    ]
    score = 40 + sum(12 for check in checks if check["passed"])
    return {
        "score": min(100, score),
        "level": "good" if score >= 80 else "usable" if score >= 60 else "needs_review",
        "checks": checks,
        "recommendations": [f"补强{check['label']}" for check in checks if not check["passed"]] or ["报告结构完整，可进入人工复核。"],
    }


@router.get("/deep-report/quality")
def get_deep_report_quality(job_id: str = "") -> dict:
    record = _latest_deep_report(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="深度报告不存在，请先生成")
    return _score_deep_report_quality(record)


def _deep_report_markdown(record: dict) -> str:
    result = record.get("result") if isinstance(record.get("result"), dict) else {}
    strategy = result.get("strategy") if isinstance(result.get("strategy"), dict) else {}
    jd_quality = result.get("jdQuality") if isinstance(result.get("jdQuality"), dict) else {}
    risk = result.get("risk") if isinstance(result.get("risk"), dict) else {}
    signals = result.get("preferenceSignals") if isinstance(result.get("preferenceSignals"), list) else []
    ai_report = result.get("aiReport") if isinstance(result.get("aiReport"), dict) else {}
    manual = result.get("manualReport") if isinstance(result.get("manualReport"), dict) else {}
    sections = manual.get("sections") if isinstance(manual.get("sections"), dict) else {}
    lines = [
        "# 求职深度报告",
        "",
        f"- 公司：{record.get('company') or '未命名公司'}",
        f"- 岗位：{record.get('title') or '未命名岗位'}",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        "",
        "## 总结",
        str(sections.get("summary") or ai_report.get("summary") or strategy.get("summary") or strategy.get("reason") or "暂无 AI 总结。"),
        "",
        "## 投递策略",
        str(sections.get("strategy") or f"建议：{strategy.get('strategy') or '待判断'}；置信度：{strategy.get('confidence', '未知')}"),
        "",
        "## JD 质量",
        str(sections.get("match") or f"质量分：{jd_quality.get('qualityScore', '未知')}；噪音等级：{jd_quality.get('noiseLevel', '未知')}"),
        "",
        "## 风险提示",
        str(sections.get("risk") or risk.get("plainLanguage") or f"风险等级：{risk.get('riskLevel', '未知')}"),
        "",
        "## 面试准备",
        str(sections.get("interview") or "暂无人工补充。"),
        "",
        "## 行动建议",
        str(sections.get("actions") or "暂无人工补充。"),
        "",
        "## 个人偏好命中",
    ]
    lines.extend([f"- {item}" for item in signals] or ["- 暂无明显偏好命中。"])
    return "\n".join(lines) + "\n"


@router.get("/deep-report/export")
def export_deep_report(job_id: str = "", format: str = "md"):
    record = _latest_deep_report(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="深度报告不存在，请先生成")
    safe_name = quote(f"{record.get('company') or 'company'}-{record.get('title') or 'job'}-deep-report")
    if format == "json":
        return Response(
            content=json.dumps(record, ensure_ascii=False, indent=2, default=str),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}.json"},
        )
    if format == "md":
        return Response(
            content=_deep_report_markdown(record),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}.md"},
        )
    if format == "pdf":
        from app.services.report_pdf_exporter import export_deep_report_pdf

        return Response(
            content=export_deep_report_pdf(record),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}.pdf"},
        )
    raise HTTPException(status_code=400, detail="导出格式必须是 md/json/pdf")


@router.post("/deep-report/edit")
def edit_deep_report(payload: dict) -> dict:
    job_id = str(payload.get("job_id") or payload.get("jobId") or "").strip()
    record = _latest_deep_report(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="深度报告不存在，请先生成")
    result = record.get("result") if isinstance(record.get("result"), dict) else {}
    versions = result.get("manualVersions") if isinstance(result.get("manualVersions"), list) else []
    sections = payload.get("sections") if isinstance(payload.get("sections"), dict) else {}
    cleaned_sections = {
        key: str(value).strip()
        for key, value in sections.items()
        if key in {"summary", "strategy", "match", "risk", "interview", "actions"} and str(value).strip()
    }
    summary = str(payload.get("summary") or cleaned_sections.get("summary") or "").strip()
    manual = {
        "version": len(versions) + 1,
        "summary": summary,
        "sections": cleaned_sections,
        "notes": [str(item).strip() for item in payload.get("notes", []) if str(item).strip()] if isinstance(payload.get("notes"), list) else [],
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
    }
    if not manual["summary"] and not manual["sections"]:
        raise HTTPException(status_code=400, detail="人工报告内容不能为空")
    versions.append(manual)
    result["manualReport"] = manual
    result["manualVersions"] = versions[-20:]
    record["result"] = result
    _replace_deep_report(record)
    return {"record": record}


@router.post("/deep-report")
def generate_deep_report(payload: dict) -> dict:
    job = payload.get("job") if isinstance(payload.get("job"), dict) else {}
    resume = payload.get("resume") if isinstance(payload.get("resume"), dict) else {}
    diligence = payload.get("diligence") if isinstance(payload.get("diligence"), dict) else {}
    preferences = load_preferences()
    preference_signals = build_preference_signals(job, diligence, preferences)
    prompt_version = "deep-report-v2"
    feedback = feedback_guidance({"ranking", "diligence", "jd_quality", "deep_report"})
    base = {
        "strategy": application_strategy(job, resume, diligence, payload.get("ranking") if isinstance(payload.get("ranking"), dict) else {}),
        "jdQuality": jd_quality(job),
        "rewrite": resume_rewrite_advice(job, resume, diligence),
        "interview": interview_prep(job, resume, diligence),
        "risk": risk_explanation(diligence),
        "preferences": preferences,
        "preferenceSignals": preference_signals,
        "feedbackGuidance": feedback,
        "promptVersion": prompt_version,
    }
    system_prompt = "你是资深求职策略顾问。请基于输入生成 JSON，字段包含 summary、priority、resumeAdvice、interviewAdvice、riskAdvice，并结合 preferences、preferenceSignals 与 feedbackGuidance 给出个性化取舍；对近期被标记需改的维度，要给出更具体证据和行动建议。"
    base["promptRecord"] = _save_prompt_version(job, "deep_report", prompt_version, system_prompt, base, feedback)
    try:
        from app.services.ai_client import chat_json
        ai = chat_json(
            system_prompt,
            str(base),
            temperature=0.2,
        )
        if isinstance(ai, dict) and not ai.get("error"):
            base["aiReport"] = ai
            base["mode"] = "ai"
        else:
            base["mode"] = "fallback"
    except Exception:
        base["mode"] = "fallback"
    base["quality"] = _score_deep_report_quality({"result": base})
    return _save_result(job, "deep_report", base)
