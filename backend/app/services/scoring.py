"""
综合评分与排序服务
- JD AI 解析
- 简历匹配度分析
- 公司得分 + 匹配度 = 综合排序
"""
from __future__ import annotations

import json
import asyncio
import hashlib
import logging
import threading
from pathlib import Path
from app.services import workflow_persistence
from app.services.ai_client import get_ai_client, get_model
from app.services.feedback_store import list_feedback
from app.services.preferences import load_preferences
from app.services.workflow_persistence import _read_json, write_json_atomic

logger = logging.getLogger(__name__)
RANKING_SETTINGS_FILE = workflow_persistence.DATA_DIR / "rankings" / "settings.json"
RANKING_CACHE_FILE = workflow_persistence.DATA_DIR / "rankings" / "ranking_cache.json"
RANKING_MAX_CONCURRENCY = 3
_RANKING_MEMORY_CACHE: dict[str, dict] = {}
_RANKING_CACHE_LOCK = threading.Lock()
DEFAULT_RANKING_WEIGHTS = {"company_weight": 0.4, "match_weight": 0.6}
RANKING_WEIGHT_TEMPLATES = {
    "balanced": {
        "name": "均衡推荐",
        "description": "兼顾公司质量和简历匹配，适合日常筛选。",
        "weights": {"company_weight": 0.4, "match_weight": 0.6},
    },
    "low_risk": {
        "name": "低风险优先",
        "description": "提高公司尽调权重，适合规避经营与舆情风险。",
        "weights": {"company_weight": 0.65, "match_weight": 0.35},
    },
    "high_match": {
        "name": "高匹配优先",
        "description": "提高简历匹配权重，适合优先冲击成功率。",
        "weights": {"company_weight": 0.25, "match_weight": 0.75},
    },
}


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


def load_feedback_adjusted_weights(base_weights: dict | None = None) -> dict:
    weights = normalize_ranking_weights(base_weights or load_ranking_weights())
    company_delta = 0.0
    match_delta = 0.0
    signals: list[str] = []
    for record in list_feedback(domain="ranking")[:30]:
        if record.get("useful") is True:
            continue
        context = record.get("context") if isinstance(record.get("context"), dict) else {}
        preference = str(context.get("weightPreference") or "").strip()
        if not preference:
            company_score = _safe_float(context.get("companyScore"))
            match_score = _safe_float(context.get("matchScore"))
            if company_score is not None and match_score is not None:
                if company_score + 10 < match_score:
                    preference = "company"
                elif match_score + 10 < company_score:
                    preference = "match"
        if preference == "company":
            company_delta += 0.03
            signals.append("近期排序反馈提示：公司风险权重应略微提高。")
        elif preference == "match":
            match_delta += 0.03
            signals.append("近期排序反馈提示：简历匹配权重应略微提高。")
    company_delta = min(0.15, company_delta)
    match_delta = min(0.15, match_delta)
    adjusted = normalize_ranking_weights({
        "company_weight": weights["company_weight"] + company_delta,
        "match_weight": weights["match_weight"] + match_delta,
    })
    if not signals:
        return adjusted
    return {**adjusted, "feedbackAdjusted": True, "feedbackSignals": list(dict.fromkeys(signals))[:4]}


def save_ranking_weights(payload: dict) -> dict[str, float]:
    weights = normalize_ranking_weights(payload)
    write_json_atomic(RANKING_SETTINGS_FILE, weights)
    return weights


def get_ranking_weight_templates() -> dict:
    return RANKING_WEIGHT_TEMPLATES


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


async def rank_jobs_ai(
    jobs: list,
    resume: dict,
    diligence_reports: dict,
    weights: dict | None = None,
    progress_callback=None,
) -> list:
    """
    综合排序：公司尽调分(40%) + AI简历匹配度(60%)
    """
    diligence_index = _build_diligence_index(diligence_reports)
    active_weights = load_feedback_adjusted_weights(weights or load_ranking_weights())
    preferences = load_preferences()
    semaphore = asyncio.Semaphore(RANKING_MAX_CONCURRENCY)
    progress_lock = asyncio.Lock()
    completed = 0

    async def rank_one(job: dict) -> dict:
        nonlocal completed
        async with semaphore:
            result = await _rank_one_job(
                job,
                resume,
                diligence_reports,
                diligence_index,
                active_weights,
                preferences,
            )
            if progress_callback:
                async with progress_lock:
                    completed += 1
                    try:
                        callback_result = progress_callback(completed, len(jobs), result)
                        if asyncio.iscoroutine(callback_result):
                            await callback_result
                    except Exception as exc:
                        logger.warning("排序进度回写失败: %s", exc)
            return result

    results = await asyncio.gather(*(rank_one(job) for job in jobs))

    # 按综合得分降序排列
    results.sort(key=lambda x: x["compositeScore"], reverse=True)
    return results


async def _rank_one_job(
    job: dict,
    resume: dict,
    diligence_reports: dict,
    diligence_index: dict[str, dict],
    active_weights: dict,
    preferences: dict,
) -> dict:
    job_id = job.get("id", "")
    company = job.get("company", "")
    diligence = _find_diligence_for_job(job, diligence_reports, diligence_index)

    # 公司得分
    company_score = diligence.get("companyScore", 50)

    jd_cache_key = _ranking_cache_key("jd", job=job)
    jd_analysis = _read_ranking_cache(jd_cache_key)
    if jd_analysis is None:
        jd_analysis = await analyze_jd_for_matching(job)
        _write_ranking_cache(jd_cache_key, jd_analysis)

    match_cache_key = _ranking_cache_key(
        "match",
        job=job,
        resume=resume,
        jd_analysis=jd_analysis,
    )
    match_result = _read_ranking_cache(match_cache_key)
    if match_result is None:
        match_result = await match_resume_to_job(resume, job, jd_analysis)
        _write_ranking_cache(match_cache_key, match_result)
    match_score = match_result.get("match_score", 50)

    # 综合得分
    composite = round(
        company_score * active_weights["company_weight"]
        + match_score * active_weights["match_weight"]
    )

    return {
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
        "explanation": _build_ranking_explanation(
            job=job,
            diligence=diligence,
            jd_analysis=jd_analysis,
            match_result=match_result,
            company_score=company_score,
            match_score=match_score,
            composite_score=composite,
            preferences=preferences,
        ),
    }


def _ranking_cache_key(stage: str, **payload) -> str:
    data = {"stage": stage, "model": get_model(), **payload}
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_ranking_cache(key: str) -> dict | None:
    cached = _RANKING_MEMORY_CACHE.get(key)
    if isinstance(cached, dict):
        return cached
    stored = _read_json(RANKING_CACHE_FILE, {})
    if not isinstance(stored, dict):
        return None
    value = stored.get(key)
    if isinstance(value, dict):
        _RANKING_MEMORY_CACHE[key] = value
        return value
    return None


def _write_ranking_cache(key: str, value: dict) -> None:
    if not isinstance(value, dict):
        return
    with _RANKING_CACHE_LOCK:
        _RANKING_MEMORY_CACHE[key] = value
        stored = _read_json(RANKING_CACHE_FILE, {})
        if not isinstance(stored, dict):
            stored = {}
        stored[key] = value
        # 只保留最近 500 条，避免长期运行导致缓存无限增长。
        if len(stored) > 500:
            stored = dict(list(stored.items())[-500:])
        write_json_atomic(RANKING_CACHE_FILE, stored)


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


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_ranking_explanation(
    job: dict,
    diligence: dict,
    jd_analysis: dict,
    match_result: dict,
    company_score: int | float,
    match_score: int | float,
    composite_score: int | float,
    preferences: dict | None = None,
) -> dict:
    highlights = match_result.get("highlights") if isinstance(match_result.get("highlights"), list) else []
    gaps = match_result.get("gaps") if isinstance(match_result.get("gaps"), list) else []
    risk_level = diligence.get("riskLevel") or "unknown"
    negative = []
    sentiment = diligence.get("sentiment") if isinstance(diligence.get("sentiment"), dict) else {}
    if isinstance(sentiment.get("negative"), list):
        negative = sentiment.get("negative")[:3]
    company_reason = "公司风险信息不足"
    if company_score >= 80:
        company_reason = "公司尽调得分较高"
    elif company_score >= 60:
        company_reason = "公司尽调风险中等"
    elif diligence:
        company_reason = "公司尽调风险偏高，建议复核证据"

    if composite_score >= 80:
        next_step = "优先投递，并结合尽调证据准备沟通重点"
    elif gaps:
        next_step = "投递前先补齐简历中的关键缺口"
    elif risk_level in {"high", "高", "risky"}:
        next_step = "先刷新尽调证据，再决定是否推进"
    else:
        next_step = "可作为备选岗位继续观察"
    preference_signals = _build_preference_signals(job, diligence, preferences or {})

    return {
        "matchReasons": highlights,
        "resumeGaps": gaps,
        "companyReason": company_reason,
        "riskSignals": negative,
        "jdSignals": {
            "coreRequirements": jd_analysis.get("core_requirements", []),
            "hardRequirements": jd_analysis.get("hard_requirements", []),
        },
        "scoreBreakdown": {
            "companyScore": company_score,
            "matchScore": match_score,
            "compositeScore": composite_score,
        },
        "nextStep": next_step,
        "preferenceSignals": preference_signals,
        "summary": match_result.get("reason") or company_reason,
        "jobSnapshot": {
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "salary": job.get("salary", ""),
        },
    }


def build_preference_signals(job: dict, diligence: dict, preferences: dict) -> list[str]:
    signals: list[str] = []
    stability = int(preferences.get("stability") or 0)
    salary = int(preferences.get("salary") or 0)
    growth = int(preferences.get("growth") or 0)
    match = int(preferences.get("match") or 0)
    if stability >= 80:
        signals.append("偏好稳定性：优先关注公司经营状态、风险等级和长期岗位有效性")
    if salary >= 80:
        signals.append(f"偏好薪资：当前薪资 {job.get('salary') or '未披露'} 需要重点比较市场水平")
    if growth >= 80:
        signals.append("偏好成长：建议结合行业趋势、业务空间和岗位职责成长性判断")
    if match >= 80:
        signals.append("偏好匹配度：当前排序更应重视简历命中 JD 核心要求")
    industry = str((diligence.get("industryOutlook") or {}).get("industry") or (diligence.get("businessInfo") or {}).get("industry") or "")
    avoid_industries = [str(item) for item in preferences.get("avoid_industries", []) if str(item)]
    if industry and any(item in industry for item in avoid_industries):
        signals.append(f"规避行业命中：{industry}")
    preferred_cities = [str(item) for item in preferences.get("preferred_cities", []) if str(item)]
    city = str(job.get("city") or "")
    if city and preferred_cities and city in preferred_cities:
        signals.append(f"偏好城市命中：{city}")
    return signals


_build_preference_signals = build_preference_signals
