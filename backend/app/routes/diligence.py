from fastapi import APIRouter, HTTPException
from app.services.company_diligence import run_full_diligence
from app.services.business_info import query_business_info
from app.services.workflow_persistence import find_diligence_report, load_diligence_reports, save_diligence_report
from app.services.workflow_tasks import complete_task, fail_task, start_task

router = APIRouter(prefix="/api/diligence", tags=["diligence"])


@router.get("/reports")
def get_diligence_reports() -> dict:
    return {"reports": load_diligence_reports()}


@router.post("/evaluate")
async def evaluate_company(payload: dict) -> dict:
    """
    对单家公司执行完整尽调
    输入: { company_name, job_title, jd_text, jd_analysis, chat_history }
    chat_history: [{role, content}] 可选，用于 AI 对话的上下文
    """
    company_name = payload.get("company_name", "")
    job_title = payload.get("job_title", "")
    jd_text = payload.get("jd_text", "")
    jd_analysis = payload.get("jd_analysis")
    chat_history = payload.get("chat_history")

    if not company_name:
        raise HTTPException(status_code=400, detail="缺少公司名称")

    task = start_task("diligence", "公司尽调", total=1, payload={"company_name": company_name, "job_title": job_title})
    try:
        report = await run_full_diligence(
            company_name=company_name,
            job_title=job_title,
            jd_text=jd_text,
            jd_analysis=jd_analysis,
            chat_history=chat_history,
        )
        saved = save_diligence_report(report)
        complete_task(task["id"], done=1, message=f"{saved.get('companyName') or company_name} 尽调完成")
        return saved
    except Exception as e:
        fail_task(task["id"], str(e), "DILIGENCE_FAILED", "检查工商 API、搜索和 AI 配置后重试")
        raise


@router.post("/refresh")
async def refresh_diligence_report(payload: dict) -> dict:
    company_name = str(payload.get("company_name", "")).strip()
    mode = str(payload.get("mode", "full")).strip() or "full"
    if not company_name:
        raise HTTPException(status_code=400, detail="缺少公司名称")
    if mode not in {"full", "business", "search"}:
        raise HTTPException(status_code=400, detail="刷新模式必须是 full/business/search")

    existing = find_diligence_report(company_name)
    if not existing and mode != "full":
        raise HTTPException(status_code=404, detail="尽调报告不存在")

    task = start_task("diligence_refresh", "刷新尽调证据", total=1, payload={"company_name": company_name, "mode": mode})
    if mode == "full":
        try:
            report = await run_full_diligence(
                company_name=company_name,
                job_title=str(payload.get("job_title", "")),
                jd_text=str(payload.get("jd_text", "")),
                jd_analysis=payload.get("jd_analysis"),
                chat_history=payload.get("chat_history"),
            )
            report["refreshMode"] = "full"
            saved = save_diligence_report(report)
            complete_task(task["id"], done=1, message="尽调证据刷新完成")
            return saved
        except Exception as e:
            fail_task(task["id"], str(e), "DILIGENCE_REFRESH_FAILED", "检查工商 API、搜索和 AI 配置后重试")
            raise

    if mode == "business":
        try:
            business_info = await query_business_info(company_name)
            report = dict(existing or {})
            report["businessInfo"] = business_info
            if business_info and not business_info.get("error"):
                report["companyName"] = business_info.get("companyName") or report.get("companyName") or company_name
                report["sourceCompanyName"] = business_info.get("sourceCompanyName") or report.get("sourceCompanyName") or company_name
                report["companyKey"] = business_info.get("companyKey") or report.get("companyKey") or company_name
                industry = business_info.get("registeredIndustry") or business_info.get("industry")
                sub_industry = business_info.get("registeredSubIndustry") or business_info.get("subIndustry")
                if industry:
                    outlook = dict(report.get("industryOutlook") or {})
                    outlook["industry"] = " / ".join([p for p in [industry, sub_industry] if p])
                    report["industryOutlook"] = outlook
            report["refreshMode"] = "business"
            saved = save_diligence_report(report)
            complete_task(task["id"], done=1, message="工商证据刷新完成")
            return saved
        except Exception as e:
            fail_task(task["id"], str(e), "BUSINESS_REFRESH_FAILED", "检查腾讯云工商 API 配置后重试")
            raise

    try:
        refreshed = await run_full_diligence(
            company_name=company_name,
            job_title=str(payload.get("job_title", "")),
            jd_text=str(payload.get("jd_text", "")),
            jd_analysis=payload.get("jd_analysis"),
            chat_history=payload.get("chat_history"),
        )
        report = dict(existing or {})
        for key in ("basicInfo", "sentiment", "recruitment", "industryOutlook", "oneLiner", "companyScore", "riskLevel"):
            if key in refreshed:
                report[key] = refreshed[key]
        report["businessInfo"] = existing.get("businessInfo") if existing else refreshed.get("businessInfo")
        report["refreshMode"] = "search"
        saved = save_diligence_report(report)
        complete_task(task["id"], done=1, message="搜索证据刷新完成")
        return saved
    except Exception as e:
        fail_task(task["id"], str(e), "SEARCH_REFRESH_FAILED", "检查百度搜索和 AI 配置后重试")
        raise


@router.post("/note")
def save_diligence_note(payload: dict) -> dict:
    company_name = payload.get("company_name", "")
    note = payload.get("note", "")
    report = find_diligence_report(company_name)
    if not report:
        raise HTTPException(status_code=404, detail="尽调报告不存在")
    report["userNotes"] = note
    return save_diligence_report(report)
