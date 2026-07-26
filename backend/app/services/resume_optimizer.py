"""AI 驱动的简历优化服务 — 顶级简历顾问"""
from app.models.resume import (
    ResumeOptimizationResult, OptimizedExperience, OptimizedProject,
)
import re

from app.services.ai_client import chat_json
from app.services.resume_formatters import fmt_exp, fmt_edu, fmt_proj, fmt_chat

SYSTEM_PROMPT = """你是顶级简历顾问，曾为 500+ 位 BAT/TMD 候选人优化简历，平均投递回复率提升 3 倍。你服务的候选人拿到了字节、腾讯、阿里的 offer。

你的核心方法论——"JD 逆向工程"：
1. 从 JD 反推面试官最看重的 3 个能力维度
2. 用候选人的真实经历去映射这 3 个维度
3. 每个 bullet 都用量化数据 + 技术深度 + 业务影响力三重包装
4. 绝不编造经历，但可以把真实经历用 JD 的语言重新讲述

返回 JSON（每个字段都不能省略）：
{
  "summary": "优化策略一句话（20 字内）",
  "tailored_summary": "针对该岗位重写的个人总结，直接用 JD 关键词回应当前岗位要什么，突出你最匹配的经历（100-180 字）",
  "skills_display": ["技能重排序，JD 要求的放最前面，总数不超过 12 个"],
  "work_experience": [
    {
      "company": "原公司名",
      "title": "原职位",
      "duration": "原时间",
      "bullets": ["量化 bullet 1 — 结构：做了什么 + 用了什么技术 + 达成了什么量化成果 + 为什么对目标岗位有价值"]
    }
  ],
  "projects": [
    {
      "name": "项目名",
      "description": "针对 JD 重写的项目描述，突出与目标岗位相关的技术挑战和成果（60-100 字）",
      "technologies": ["相关技术"]
    }
  ],
  "matched_skills": ["与 JD 高匹配的技能"],
  "missing_skills": ["JD 硬性要求但确实没有的技能，诚实标注"],
  "section_advice": ["1-2 条关键排版/结构建议"],
  "gap_strategies": ["针对确实的技能给出可操作的弥补策略，每条约 30 字"],
  "optimized_bullets": []
}

STAR + 量化原则：
- 每个 bullet = 动作动词 + 技术手段 + 量化结果 + 业务价值
- 示例：❌"负责系统性能优化" → ✅"通过引入 Redis 缓存层和 SQL 索引优化，将 API 响应时间从 800ms 降至 80ms，支撑双十一峰值 QPS 从 5000 提升至 50000"
- 数字要真实可信，不要夸张

只返回 JSON，不要解释，不要 markdown 包裹。"""


def _clean_missing_skills(values) -> list[str]:
    cleaned = []
    empty_markers = ("无", "没有", "暂无", "完全匹配", "不缺", "无明显")
    for value in values or []:
        text = str(value).strip()
        if not text:
            continue
        if any(marker in text for marker in empty_markers):
            continue
        cleaned.append(text)
    return cleaned


def _extract_jd_skills(jd_text: str) -> list[str]:
    return [
        s for s in _FALLBACK_SKILL_POOL
        if re.search(rf"(?<![a-zA-Z]){re.escape(s)}(?![a-zA-Z])", jd_text or "", re.I)
    ]


def _merge_unique(*groups) -> list[str]:
    result = []
    seen = set()
    for group in groups:
        for item in group or []:
            text = str(item).strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(text)
    return result


def optimize_resume(profile, evaluation, jd_analysis, job_title="", company="", jd_text="", chat_history=None):
    eval_text = ""
    if evaluation:
        eval_text = f"""简历评估：{evaluation.overall_score}/100
优点：{'；'.join(evaluation.strengths or ['无'])}
不足：{'；'.join(evaluation.weaknesses or ['无'])}"""

    jd_block = ""
    if jd_analysis:
        jd_block = f"""JD 分析：
必备技能：{', '.join(jd_analysis.must_have_skills or ['未识别'])}
加分技能：{', '.join(jd_analysis.nice_to_have_skills or ['无'])}
经验要求：{', '.join(jd_analysis.experience_requirements or ['未识别'])}
核心总结：{jd_analysis.summary_text}"""

    chat_str = fmt_chat(chat_history)
    base_prompt = f"""=== 目标岗位 ===
{job_title} @ {company or '未知'}

{eval_text}
{jd_block}

=== 候选人原始简历 ===
姓名：{profile.name or '未识别'} | 当前岗位：{profile.title or '未识别'}
联系方式：{getattr(profile, 'phone', '') or '无'} | {getattr(profile, 'email', '') or '无'}
技能：{', '.join(profile.skills) if profile.skills else '未识别'}
个人总结：{profile.summary or '无'}
"""
    # 动态分配剩余空间给简历详情和 JD
    exp_str = fmt_exp(profile)
    edu_str = fmt_edu(profile)
    proj_str = fmt_proj(profile)
    remaining = 6000 - len(base_prompt) - len(chat_str)
    jd_part = jd_text[:max(800, remaining // 3)]
    detail_limit = max(500, remaining - len(jd_part))
    detail = f"工作经历：\n{exp_str[:detail_limit]}\n\n教育背景：\n{edu_str[:detail_limit//2]}\n\n项目经历：\n{proj_str[:detail_limit//2]}"
    
    user = f"""{base_prompt}JD 描述：{jd_part}

{detail}

对话上下文（用户补充要求）：
{chat_str}

请生成针对该岗位的定制化完整简历。每段工作经历至少生成 2 条量化 bullets。"""

    try:
        data = chat_json(SYSTEM_PROMPT, user)
        work_exp = []
        for exp in (data.get("work_experience") or []):
            if isinstance(exp, dict):
                work_exp.append(OptimizedExperience(
                    company=str(exp.get("company", "")), title=str(exp.get("title", "")),
                    duration=str(exp.get("duration", "")),
                    bullets=[str(b) for b in (exp.get("bullets") or []) if b],
                ))
        projects = []
        for proj in (data.get("projects") or []):
            if isinstance(proj, dict):
                projects.append(OptimizedProject(
                    name=str(proj.get("name", "")), description=str(proj.get("description", "")),
                    technologies=[str(t) for t in (proj.get("technologies") or []) if t],
                ))
        resume_skill_keys = {str(s).lower() for s in (profile.skills or [])}
        jd_skills = _extract_jd_skills(jd_text)
        deterministic_matched = [s for s in jd_skills if s.lower() in resume_skill_keys]
        deterministic_missing = [s for s in jd_skills if s.lower() not in resume_skill_keys]
        matched_skills = _merge_unique(data.get("matched_skills"), deterministic_matched)
        missing_skills = _merge_unique(_clean_missing_skills(data.get("missing_skills")), deterministic_missing)

        return ResumeOptimizationResult(
            summary=str(data.get("summary", "")),
            tailored_summary=str(data.get("tailored_summary", "")),
            skills_display=[str(s) for s in (data.get("skills_display") or []) if s],
            optimized_bullets=[str(b) for b in (data.get("optimized_bullets") or []) if b],
            work_experience=work_exp, projects=projects,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            section_advice=[str(a) for a in (data.get("section_advice") or []) if a],
            gap_strategies=[str(g) for g in (data.get("gap_strategies") or []) if g],
        )
    except Exception as e:
        return _fallback(profile, jd_analysis, job_title, company, jd_text, str(e))


# 技能池 — 从 resume_parser 共享
from app.services.resume_parser import SKILL_POOL as _FALLBACK_SKILL_POOL

def _fallback(profile, jd_analysis, job_title, company, jd_text, error):
    resume_skills = [s.lower() for s in profile.skills]
    jd_skills = _extract_jd_skills(jd_text)
    matched = [s for s in jd_skills if s.lower() in resume_skills]
    missing = [s for s in jd_skills if s.lower() not in resume_skills]
    fexp = []
    for e in (profile.work_experience or []):
        fexp.append(OptimizedExperience(company=e.company, title=e.title, duration=e.duration,
            bullets=[f"在 {e.company} 担任 {e.title}，积累了 {e.duration} 的实战经验",
                      f"运用 {', '.join(matched[:3]) or '专业技能'} 推动项目交付"] if matched else [e.description or f"{e.title} @ {e.company}"]))
    fproj = [OptimizedProject(name=p.name, description=p.description, technologies=p.technologies) for p in (profile.projects or [])]
    return ResumeOptimizationResult(
        summary=f"面向 {job_title} 的基础优化（AI 不可用：{error[:80]}）",
        tailored_summary=profile.summary or f"{', '.join(profile.skills[:5])} 背景，寻求 {job_title} 机会",
        skills_display=list(dict.fromkeys(matched + profile.skills)),
        work_experience=fexp, projects=fproj,
        matched_skills=matched, missing_skills=missing,
        section_advice=["建议配置 AI Key 获得精准优化"],
        gap_strategies=[f"{s} 可通过在线课程补充" for s in missing[:3]],
    )
