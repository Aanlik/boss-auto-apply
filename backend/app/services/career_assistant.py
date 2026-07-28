from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


NOISE_WORDS = [
    "组织发展", "招聘", "人才发展", "教育", "医疗健康", "电商", "在线",
    "年会", "宝马", "总经理直管", "1100人", "11层楼", "成立15年",
]
RESPONSIBILITY_HINTS = ["负责", "职责", "岗位职责", "工作内容", "任职要求", "要求", "能力"]
COMMON_SKILLS = [
    "产品规划", "用户增长", "数据分析", "跨部门协作", "项目管理", "CRM", "SQL",
    "Python", "FastAPI", "运营", "招聘", "HRBP", "增长", "转化",
]


def application_strategy(job: dict, resume: dict, diligence: dict, ranking: dict) -> dict:
    company_score = _to_int(diligence.get("companyScore"), 50)
    match_score = _to_int(ranking.get("matchScore") or ranking.get("compositeScore"), 50)
    risk = str(diligence.get("riskLevel") or "").lower()
    decision = str(job.get("decision_status") or job.get("decisionStatus") or "")
    confidence = max(35, min(95, round(company_score * 0.45 + match_score * 0.55)))

    if risk in {"high", "高"} or decision == "risky" or company_score < 45:
        strategy = "needs_more_info"
        label = "需补充信息"
        next_actions = ["刷新工商与搜索证据", "准备风险追问", "暂缓批量投递"]
    elif confidence >= 75 or decision == "recommended":
        strategy = "priority_apply"
        label = "优先投递"
        next_actions = ["优先打招呼", "按 JD 关键词微调简历", "准备 3 个岗位相关案例"]
    elif confidence >= 60:
        strategy = "watch"
        label = "观察推进"
        next_actions = ["补齐 JD 详情", "复核公司尽调", "作为第二梯队投递"]
    else:
        strategy = "hold"
        label = "暂不推进"
        next_actions = ["保留岗位记录", "等待更多证据", "优先处理更匹配岗位"]

    return {
        "strategy": strategy,
        "label": label,
        "confidence": confidence,
        "reasons": [
            f"公司分 {company_score}",
            f"匹配分 {match_score}",
            f"风险等级 {diligence.get('riskLevel') or '未知'}",
        ],
        "nextActions": next_actions,
        "resumeFocus": _matched_keywords(job.get("jd_text", ""), resume)[:6],
    }


def jd_quality(job: dict) -> dict:
    jd_text = str(job.get("jd_text") or "")
    noise_hits = [word for word in NOISE_WORDS if word.lower() in jd_text.lower()]
    has_responsibility = any(word in jd_text for word in RESPONSIBILITY_HINTS)
    has_numbers = bool(re.search(r"\d+\s*(人|层|年|辆|%)", jd_text))
    short = len(jd_text.strip()) < 120
    score = 80
    signals = []
    if noise_hits:
        score -= min(35, len(noise_hits) * 5)
        signals.append(f"检测到疑似营销或页面噪音: {'、'.join(noise_hits[:6])}")
    if not has_responsibility:
        score -= 25
        signals.append("缺少清晰岗位职责或任职要求")
    if has_numbers and not has_responsibility:
        score -= 10
        signals.append("公司宣传数字多于岗位要求")
    if short:
        score -= 10
        signals.append("JD 文本过短，信息密度不足")

    score = max(15, min(95, score))
    if score < 45:
        noise_level = "high"
        authenticity = "weak"
    elif score < 65:
        noise_level = "medium"
        authenticity = "medium"
    else:
        noise_level = "low"
        authenticity = "strong"
    return {
        "qualityScore": score,
        "noiseLevel": noise_level,
        "authenticity": authenticity,
        "signals": signals or ["JD 结构相对清晰"],
        "cleaningAdvice": ["优先保留职责、要求、技能、业务目标", "删除公司宣传、福利堆叠和页面导航词"],
        "missingSections": [] if has_responsibility else ["岗位职责", "任职要求"],
    }


def resume_rewrite_advice(job: dict, resume: dict, diligence: dict | None = None) -> dict:
    jd_text = str(job.get("jd_text") or "")
    matched = _matched_keywords(jd_text, resume)
    missing = [skill for skill in _extract_keywords(jd_text) if skill not in matched][:6]
    title = job.get("title") or "目标岗位"
    return {
        "keywordEvidence": matched,
        "missingKeywords": missing,
        "rewriteFocus": [
            f"围绕「{title}」补充可量化结果",
            "把项目经历改写为动作、方法、结果三段式",
            "优先展示和 JD 命中的技能证据",
        ],
        "bulletSuggestions": [
            f"基于{matched[0] if matched else '岗位核心要求'}，推动业务目标拆解并形成可复用方案",
            "通过数据分析定位关键问题，沉淀指标看板并推动跨部门协作",
            "结合目标岗位要求补充项目规模、结果指标和个人贡献",
        ],
        "companyContext": (diligence or {}).get("companyName") or job.get("company") or "",
    }


def interview_prep(job: dict, resume: dict, diligence: dict | None = None) -> dict:
    company = job.get("company") or (diligence or {}).get("companyName") or "目标公司"
    title = job.get("title") or "目标岗位"
    industry = ((diligence or {}).get("businessInfo") or {}).get("industry") or "所在行业"
    return {
        "companyBrief": f"{company} 属于{industry}，面试前建议结合工商状态、业务范围和招聘 JD 交叉验证。",
        "questions": [
            f"你如何理解{title}在当前业务阶段的核心目标？",
            "请讲一个你用数据发现问题并推动结果改善的案例。",
            "当业务方、技术方和管理层目标不一致时，你如何推进？",
            "如果入职前三个月只能做一件事，你会如何判断优先级？",
        ],
        "answerAngles": [
            "用 STAR 结构回答，强调背景、动作、结果和复盘。",
            "把简历项目和 JD 关键词建立一一对应关系。",
            "遇到公司风险问题时，用证据和边界表达谨慎判断。",
        ],
        "reverseQuestions": [
            "这个岗位当前最急需解决的业务问题是什么？",
            "团队如何评价前三个月的成功？",
            "岗位协作方和决策链路分别是谁？",
        ],
    }


def followup_reminders(jobs: list[dict], send_records: list[dict]) -> dict:
    sent_ids = {record.get("jobId") for record in send_records if record.get("status") == "sent"}
    reminders = []
    for job in jobs:
        status = job.get("application_status") or "pending"
        if status not in {"greeted", "applied", "interviewing"}:
            continue
        priority = "normal"
        reason = "需要跟进求职状态"
        if job.get("id") in sent_ids or status == "greeted":
            priority = "high"
            reason = "已打招呼但尚未记录后续反馈"
        elif status == "interviewing":
            reason = "面试中，建议记录面试节点和后续动作"
        reminders.append({
            "jobId": job.get("id", ""),
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "status": status,
            "priority": priority,
            "reason": reason,
            "suggestedAction": "发送礼貌跟进或更新求职状态",
        })
    reminders.sort(key=lambda item: 0 if item["priority"] == "high" else 1)
    return {"reminders": reminders, "generatedAt": datetime.now(timezone.utc).isoformat()}


def risk_explanation(diligence: dict) -> dict:
    business = diligence.get("businessInfo") if isinstance(diligence.get("businessInfo"), dict) else {}
    sentiment = diligence.get("sentiment") if isinstance(diligence.get("sentiment"), dict) else {}
    risk_level = diligence.get("riskLevel") or "medium"
    risk_items = []
    for key in ("abnormalInfo", "penalties", "dishonestItems", "enforcedItems"):
        value = business.get(key)
        if isinstance(value, list):
            risk_items.extend([str(item) for item in value if item])
    if isinstance(sentiment.get("negative"), list):
        risk_items.extend([str(item) for item in sentiment.get("negative") if item])
    plain = "暂未发现明确高风险记录"
    if risk_items:
        plain = "该公司存在需要复核的风险信号，投递前应确认风险是否影响薪资、稳定性和岗位真实性。"
    return {
        "riskLevel": risk_level,
        "plainLanguage": plain,
        "riskItems": risk_items[:8],
        "impact": [
            "可能影响岗位稳定性",
            "可能影响薪资兑现或组织管理预期",
            "需要在面试中确认真实业务和团队情况",
        ] if risk_items else ["保持常规尽调即可"],
        "questionsToAsk": [
            "岗位招聘的直接原因是什么，是新增还是替换？",
            "团队当前业务目标和预算周期是什么？",
            "公司近期是否存在组织调整或经营异常影响？",
        ],
    }


def _to_int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _extract_keywords(text: str) -> list[str]:
    lowered = text.lower()
    found = []
    for skill in COMMON_SKILLS:
        if skill.lower() in lowered and skill not in found:
            found.append(skill)
    return found


def _matched_keywords(jd_text: str, resume: dict) -> list[str]:
    resume_text = str(resume)
    found = []
    for skill in _extract_keywords(jd_text):
        if skill.lower() in resume_text.lower():
            found.append(skill)
    return found
