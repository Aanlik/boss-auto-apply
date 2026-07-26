"""
公司尽调服务 — 百度搜索 + AI 驱动

工作流：
  1. 百度 + AI 搜索公司基本信息（规模、融资、业务）
  2. 百度 + AI 搜索舆情与风险信号
  3. 百度 + AI 分析行业前景
  4. 分析招聘情况
  5. 综合打分 + 生成报告
"""

import asyncio
import json
import logging
from typing import Optional

from app.services.internet_search import (
    search_company_info,
    search_company_sentiment,
    search_industry_outlook,
)
from app.services.ai_client import get_ai_client
from app.services.business_info import query_business_info

logger = logging.getLogger(__name__)


async def run_full_diligence(
    company_name: str,
    job_title: str = "",
    jd_text: str = "",
    jd_analysis: Optional[dict] = None,
    chat_history: Optional[list] = None,
) -> dict:
    """执行完整的公司尽调，返回结构化报告"""
    info_task = search_company_info(company_name)
    sentiment_task = search_company_sentiment(company_name)
    biz_task = query_business_info(company_name)

    info, sentiment, biz_info = await asyncio.gather(info_task, sentiment_task, biz_task)

    business = info.get("business", "")
    analysis_company_name = company_name
    if biz_info and not biz_info.get("error"):
        analysis_company_name = biz_info.get("companyName") or company_name
    industry_subject = _industry_subject(business, biz_info)
    industry = await search_industry_outlook(analysis_company_name, industry_subject)

    recruitment = _analyze_recruitment(company_name, job_title, jd_text, jd_analysis)

    score, risk_level = _compute_company_score(info, sentiment, industry, recruitment, biz_info)

    one_liner = await _generate_one_liner(
        company_name, score, risk_level, info, sentiment, industry, chat_history, biz_info
    )

    return {
        "companyName": analysis_company_name,
        "sourceCompanyName": company_name,
        "companyKey": _company_key(company_name, biz_info),
        "companyScore": score,
        "riskLevel": risk_level,
        "businessInfo": biz_info,
        "basicInfo": {
            "scale": info.get("scale", "未知"),
            "funding": info.get("funding", "未知"),
            "founded": info.get("founded", "未知"),
            "business": info.get("business", "未知"),
        },
        "techStack": info.get("tech_stack", []),
        "industryPosition": info.get("industry_position", "未知"),
        "competitors": info.get("competitors", []),
        "sentiment": {
            "positive": sentiment.get("positive_signals", []),
            "negative": sentiment.get("negative_signals", []),
            "employeeFeedback": sentiment.get("employee_feedback", ""),
            "legalRisks": sentiment.get("legal_risks", []),
            "evidenceLinks": (
                info.get("evidence_links", [])
                + sentiment.get("evidence_links", [])
                + industry.get("evidence_links", [])
            ),
        },
        "recruitment": recruitment,
        "industryOutlook": {
            "industry": industry.get("industry", "未知"),
            "trend": industry.get("trend", "待分析"),
            "policy": industry.get("policy", "待分析"),
            "marketSpace": industry.get("market_space", "待分析"),
            "growthRate": industry.get("growth_rate", ""),
            "advantages": industry.get("advantages", []),
            "disadvantages": industry.get("disadvantages", []),
            "risks": industry.get("risks", []),
        },
        "oneLiner": one_liner,
        "userNotes": "",
        "completedAt": "",
    }


def _industry_subject(fallback_business: str, biz_info: Optional[dict]) -> str:
    if biz_info and not biz_info.get("error"):
        industry = biz_info.get("registeredIndustry") or biz_info.get("industry") or ""
        sub_industry = biz_info.get("registeredSubIndustry") or biz_info.get("subIndustry") or ""
        parts = [part for part in (industry, sub_industry) if part]
        if parts:
            return " / ".join(parts)
        if biz_info.get("businessScope"):
            return str(biz_info["businessScope"])[:300]
    return fallback_business or "未知业务"


def _company_key(company_name: str, biz_info: Optional[dict]) -> str:
    if biz_info and not biz_info.get("error"):
        return (
            str(biz_info.get("companyKey") or "").strip()
            or str(biz_info.get("unifiedCreditCode") or "").strip()
            or str(biz_info.get("companyName") or "").strip()
        )
    return company_name


def _analyze_recruitment(
    company_name: str,
    job_title: str,
    jd_text: str,
    jd_analysis: Optional[dict],
) -> dict:
    skills_count = 0
    if jd_analysis:
        skills_count = (
            len(jd_analysis.get("must_have_skills", []))
            + len(jd_analysis.get("nice_to_have_skills", []))
        )
    jd_quality = "良好"
    if len(jd_text) < 100:
        jd_quality = "简略"
    elif skills_count >= 8:
        jd_quality = "详细规范"
    return {
        "activePositions": 1,
        "salaryCompetitiveness": "待对比",
        "jdQuality": jd_quality,
        "requiredSkillsCount": skills_count,
    }


def _compute_company_score(
    info: dict, sentiment: dict, industry: dict, recruitment: dict, biz_info: Optional[dict] = None
) -> tuple:
    score = 50
    scale = info.get("scale", "").lower()
    funding = info.get("funding", "").lower()

    if "万人大厂" in scale or "5000" in scale:
        score += 15
    elif "500" in scale or "1000" in scale:
        score += 10
    elif "50" in scale or "200" in scale:
        score += 5

    if "上市" in funding:
        score += 15
    elif "c轮" in funding or "d轮" in funding:
        score += 12
    elif "b轮" in funding:
        score += 8
    elif "a轮" in funding:
        score += 5

    negative_count = len(sentiment.get("negative_signals", []))
    legal_count = len(sentiment.get("legal_risks", []))
    positive_count = len(sentiment.get("positive_signals", []))

    score -= negative_count * 10
    score -= legal_count * 15
    score += positive_count * 5

    trend = industry.get("trend", "").lower()
    policy = industry.get("policy", "").lower()
    market = industry.get("market_space", "").lower()

    if "快速上升" in trend or "高增长" in trend:
        score += 10
    elif "稳定增长" in trend or "上升期" in trend:
        score += 5
    elif "下行" in trend:
        score -= 10

    if "大力支持" in policy or "政策支持" in policy:
        score += 8
    elif "收紧" in policy:
        score -= 8

    if "千亿" in market:
        score += 7
    elif "百亿" in market:
        score += 4

    score += min(5, recruitment.get("requiredSkillsCount", 0))

    if biz_info and not biz_info.get("error"):
        score -= len(biz_info.get("abnormalInfo", [])) * 12
        score -= len(biz_info.get("penalties", [])) * 8
        score -= int(biz_info.get("dishonestCount", 0) or 0) * 25
        score -= int(biz_info.get("enforcedCount", 0) or 0) * 15
        score -= int(biz_info.get("pledgeCount", 0) or 0) * 3
        status = biz_info.get("businessStatus", "")
        if status and not any(token in status for token in ("存续", "开业", "在营", "正常")):
            score -= 20
        if biz_info.get("isOnStock") == "1":
            score += 8
        if any(str(level).endswith("：A") or str(level).upper() == "A" for level in biz_info.get("taxCreditLevels", [])):
            score += 5
        if not biz_info.get("abnormalInfo") and not biz_info.get("penalties") and not biz_info.get("dishonestCount") and not biz_info.get("enforcedCount"):
            score += 3

    score = max(0, min(100, score))

    if score >= 75:
        risk = "low"
    elif score >= 50:
        risk = "medium"
    else:
        risk = "high"

    return score, risk


async def _generate_one_liner(
    company_name: str,
    score: int,
    risk: str,
    info: dict,
    sentiment: dict,
    industry: dict,
    chat_history: Optional[list] = None,
    biz_info: Optional[dict] = None,
) -> str:
    client = get_ai_client()
    if not client:
        return _fallback_one_liner(score, risk)

    context = {
        "company": company_name,
        "score": score,
        "risk": risk,
        "scale": info.get("scale", "未知"),
        "funding": info.get("funding", "未知"),
        "business": info.get("business", ""),
        "trend": industry.get("trend", ""),
        "negatives": sentiment.get("negative_signals", []),
        "positives": sentiment.get("positive_signals", []),
    }

    # 加入工商硬指标
    if biz_info and not biz_info.get("error"):
        context["established"] = biz_info.get("establishedDate", "")
        context["regCapital"] = biz_info.get("registrationCapital", "")
        context["bizStatus"] = biz_info.get("businessStatus", "")
        context["abnormalCount"] = len(biz_info.get("abnormalInfo", []))
        context["penaltyCount"] = len(biz_info.get("penalties", []))

    chat_ctx = ""
    if chat_history and len(chat_history) > 0:
        chat_lines = []
        for m in chat_history[-6:]:
            role = "用户" if m.get("role") == "user" else "AI"
            chat_lines.append(f"{role}: {m.get('content', '')}")
        chat_ctx = "对话上下文:\n" + "\n".join(chat_lines) + "\n\n"

    prompt = (
        f"基于以下公司尽调数据，用一句话（30字以内）总结该公司的整体评价：\n\n"
        f"{chat_ctx}"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
        f"要求：客观、精炼、有信息量。只需返回一句话，不要有标点以外的其他内容。"
    )

    try:
        response = await client.chat(prompt, temperature=0.5, max_tokens=100)
        return response.strip().strip('"').strip("'")
    except Exception:
        return _fallback_one_liner(score, risk)


def _fallback_one_liner(score: int, risk: str) -> str:
    risk_label = {"low": "风险较低", "medium": "有一定风险", "high": "风险较高"}
    return f"综合评分{score}分，{risk_label.get(risk, '待评估')}。"
