"""AI 简历评估服务 — 专业 HR 视角"""
from app.models.resume import ResumeProfile, ResumeEvaluation
from app.services.ai_client import chat_json
from app.services.resume_formatters import fmt_exp, fmt_edu, fmt_proj, fmt_chat

SYSTEM_PROMPT = """你是一位在 BAT 有 15 年经验的 HR 总监，同时持有 SHRM-SCP 认证。你的评估风格：精准、犀利、不说废话，每条建议都能直接落地执行。

请对简历进行全方位评估，返回 JSON：
{
  "overall_score": 0-100 的整数,
  "strengths": ["具体的、可量化的优点，每条 15-30 字"],
  "weaknesses": ["具体的问题，指明是哪个模块、哪里不行，给出改进方向"],
  "missing_sections": ["缺失的简历模块"],
  "format_issues": ["格式或排版问题，如空白过多、字号不统一、段落对齐混乱等"],
  "summary_text": "一句话总结：这份简历的核心竞争力和最大短板（40 字内）"
}

评分尺度（从严）：
- 90+：顶级简历，经历与目标高度匹配，成果量化充分，结构完整
- 75-89：好简历，核心信息完整，有小幅优化空间
- 60-74：及格，信息基本完整但表达平平，缺乏亮点
- 40-59：偏弱，关键模块缺失或描述笼统，竞争力不足
- <40：严重不足，几乎不具备竞争力

评估维度：
1. 结构完整性：是否包含个人总结、工作经历、项目经历、教育背景、技能
2. 内容质量：是否使用 STAR 法则、是否有量化成果、是否有行业关键词
3. 匹配度：技能和经验是否与当前主流岗位要求对齐
4. 表达力：语言是否简洁有力，动词是否主动，数据是否具体
5. 格式规范性：排版是否清晰、是否有无意义空白、字体字号一致性

只返回 JSON，不要解释，不要 markdown。"""


def evaluate_resume(profile: ResumeProfile, resume_raw_text: str = "", chat_history=None) -> ResumeEvaluation:
    # 动态截断：总 prompt 控制在 8000 字符内
    base = f"""请评估以下简历：

姓名：{profile.name or "未识别"}
当前岗位：{profile.title or "未识别"}
联系方式：{profile.phone or "无"} | {profile.email or "无"}
个人总结：{profile.summary or "无"}
技能：{', '.join(profile.skills) if profile.skills else "未识别"}

工作经历：
{fmt_exp(profile)}

教育背景：
{fmt_edu(profile)}

项目经历：
{fmt_proj(profile)}
"""
    chat_str = f"\n对话上下文：\n{fmt_chat(chat_history)}"
    raw_limit = max(500, 6000 - len(base) - len(chat_str))
    raw_part = f"\n简历原文（前 {raw_limit} 字）：\n{resume_raw_text[:raw_limit]}"
    user = base + raw_part + chat_str
    try:
        data = chat_json(SYSTEM_PROMPT, user)
        return ResumeEvaluation(
            overall_score=data.get("overall_score", 50),
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            missing_sections=data.get("missing_sections", []),
            format_issues=data.get("format_issues", []),
            summary_text=data.get("summary_text", ""),
        )
    except Exception as e:
        score = 30
        if profile.name: score += 10
        if profile.skills: score += min(len(profile.skills) * 2, 20)
        if profile.work_experience: score += min(len(profile.work_experience) * 5, 20)
        if profile.education: score += 10
        if profile.summary: score += 10
        return ResumeEvaluation(
            overall_score=max(0, min(score, 100)),
            strengths=["简历包含基本信息"] if profile.name else [],
            weaknesses=["AI 评估暂时不可用"],
            summary_text=f"基础评分 {min(score, 95)}/100（AI 异常：{str(e)[:100]}）",
        )