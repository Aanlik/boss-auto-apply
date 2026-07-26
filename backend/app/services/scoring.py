"""
综合评分与排序服务
- JD AI 解析
- 简历匹配度分析
- 公司得分 + 匹配度 = 综合排序
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from app.services.ai_client import get_ai_client
from app.services.workflow_persistence import _read_json, write_json_atomic

logger = logging.getLogger(__name__)
RANKING_SETTINGS_FILE = Path(__file__).resolve().parents[3] / "data" / "rankings" / "settings.json"
DEFAULT_RANKING_WEIGHTS = {"company_weight": 0.4, "match_weight": 0.6}


def normalize_ranking_weights(payload: dict | None = None) -> dict[str, float]:
    raw = payload or {}
    company = float(raw.get("company_weight", DEFAULT_RANKING_WEIGHTS["company_weight"]))
    match = float(raw.get("match_weight", DEFAULT_RANKING_WEIGHTS["match_weight"]))
    company = max(0.0, min(1.0, company))
    match = max(0.0, min(1.0, match))
    total = company + match
    if total <= 0:
        return dict(DEFAULT_RANKING_WEIGHTS)
    return {
        "company_weight": round(company / total, 4),
        "match_weight": round(match / total, 4),
    }


def load_ranking_weights() -> dict[str, float]:
    data = _read_json(RANKING_SETTINGS_FILE, {})
    return normalize_ranking_weights(data if isinstance(data, dict) else {})


def save_ranking_weights(payload: dict) -> dict[str, float]:
    weights = normalize_ranking_weights(payload)
    write_json_atomic(RANKING_SETTINGS_FILE, weights)
    return weights


async def analyze_jd_for_matching(job: dict) -> dict:
    """
    AI 深度解析 JD：核心要求、隐性要求、门槛标注
    """
    client = get_ai_client()
    if not client:
        return _fallback_jd_analysis(job)

    title = job.get("title", "")
    company = job.get("company", "")
    jd_text = job.get("jd_text", "")

    prompt = f"""分析以下岗位 JD，提取核心要求。以 JSON 返回：

岗位: {title}
公司: {company}
JD:
{jd_text[:3000]}

返回格式:
{{
  "core_requirements": ["核心技术/能力要求，按重要性排序"],
  "hard_requirements": ["硬性门槛（必须满足的，如学历、年限、证书）"],
  "nice_to_have": ["加分项（非必须但有利的）"],
  "experience_years": "要求的工作经验年限",
  "education_level": "学历要求",
  "key_responsibilities": ["3-5条主要职责概括"],
  "salary_range": "薪资范围"
}}

只返回 JSON，不要其他内容。"""

    try:
        response = await client.chat(prompt, temperature=0.2, max_tokens=600)
        return _parse_json(response)
    except Exception as e:
        logger.warning(f"JD 解析失败: {e}")
        return _fallback_jd_analysis(job)


async def match_resume_to_job(resume: dict, job: dict, jd_analysis: dict) -> dict:
    """
    AI 简历匹配度分析
    返回: { match_score, highlights, gaps, recommendation }
    """
    client = get_ai_client()
    if not client:
        return _fallback_match("")

    profile = json.dumps(resume, ensure_ascii=False, indent=2)
    jd_info = json.dumps(jd_analysis, ensure_ascii=False, indent=2)
    title = job.get("title", "")
    company = job.get("company", "")

    prompt = f"""对比求职者简历和岗位要求，分析匹配度。以 JSON 返回：

岗位: {title} @ {company}

岗位要求:
{jd_info}

求职者简历:
{profile}

返回格式:
{{
  "match_score": 0-100的匹配分数,
  "skill_match_rate": 技能匹配率(0.0-1.0),
  "experience_match": "经验匹配描述",
  "education_match": "学历匹配描述",
  "highlights": ["简历中超出岗位要求的亮点"],
  "gaps": ["不满足的硬性要求或明显缺口"],
  "recommendation": "strong/recommend/consider/not_recommend",
  "reason": "一句话说明推荐/不推荐原因"
}}

打分标准: 技能匹配占40%、经验匹配占30%、学历匹配占20%、综合素质占10%。
只返回 JSON，不要其他内容。"""

    try:
        response = await client.chat(prompt, temperature=0.2, max_tokens=500)
        result = _parse_json(response)
        if not result:
            return _fallback_match("")
        # 确保必要字段
        result.setdefault("match_score", 50)
        result.setdefault("highlights", [])
        result.setdefault("gaps", [])
        result.setdefault("recommendation", "consider")
        result.setdefault("reason", "匹配度一般")
        return result
    except Exception as e:
        logger.warning(f"简历匹配失败: {e}")
        return _fallback_match(str(e)[:100])


async def rank_jobs_ai(jobs: list, resume: dict, diligence_reports: dict, weights: dict | None = None) -> list:
    """
    综合排序：公司尽调分(40%) + AI简历匹配度(60%)
    """
    results = []
    diligence_index = _build_diligence_index(diligence_reports)
    active_weights = normalize_ranking_weights(weights or load_ranking_weights())
    for job in jobs:
        job_id = job.get("id", "")
        company = job.get("company", "")
        diligence = _find_diligence_for_job(job, diligence_reports, diligence_index)

        # 公司得分
        company_score = diligence.get("companyScore", 50)

        # JD 解析
        jd_analysis = await analyze_jd_for_matching(job)

        # 简历匹配
        match_result = await match_resume_to_job(resume, job, jd_analysis)
        match_score = match_result.get("match_score", 50)

        # 综合得分
        composite = round(
            company_score * active_weights["company_weight"]
            + match_score * active_weights["match_weight"]
        )

        results.append({
            "jobId": job_id,
            "jobTitle": job.get("title", ""),
            "company": company,
            "companyKey": job.get("company_key") or job.get("companyKey") or diligence.get("companyKey", ""),
            "salary": job.get("salary", ""),
            "companyScore": company_score,
            "matchScore": match_score,
            "compositeScore": composite,
            "recommendation": match_result.get("recommendation", "consider"),
            "reason": match_result.get("reason", ""),
            "matchHighlights": match_result.get("highlights", []),
            "matchGaps": match_result.get("gaps", []),
            "weights": active_weights,
        })

    # 按综合得分降序排列
    results.sort(key=lambda x: x["compositeScore"], reverse=True)
    return results


def _build_diligence_index(diligence_reports: dict) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for key, report in diligence_reports.items():
        if not isinstance(report, dict):
            continue
        for value in (
            key,
            report.get("companyName"),
            report.get("sourceCompanyName"),
            report.get("companyKey"),
        ):
            if value:
                index[str(value).strip()] = report
    return index


def _find_diligence_for_job(job: dict, diligence_reports: dict, diligence_index: dict[str, dict]) -> dict:
    for value in (
        job.get("company_key"),
        job.get("companyKey"),
        job.get("company"),
    ):
        if value and str(value).strip() in diligence_index:
            return diligence_index[str(value).strip()]
    return diligence_reports.get(job.get("company", ""), {})


def _parse_json(response: str) -> dict:
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{[\s\S]*\}', response)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {}


def _fallback_jd_analysis(job: dict) -> dict:
    title = job.get("title", "")
    return {
        "core_requirements": [title],
        "hard_requirements": ["相关工作经验"],
        "nice_to_have": [],
        "experience_years": "1-3年",
        "education_level": "本科及以上",
        "key_responsibilities": [f"负责{title}相关工作"],
        "salary_range": job.get("salary", ""),
    }


def _fallback_match(error_msg: str = "") -> dict:
    reason = f"AI 调用失败: {error_msg}" if error_msg else "匹配度分析待AI配置后更新（请在设置中配置API Key）"
    return {
        "match_score": 50,
        "skill_match_rate": 0.5,
        "experience_match": "待AI分析",
        "education_match": "待AI分析",
        "highlights": [],
        "gaps": [],
        "recommendation": "consider",
        "reason": reason,
    }
