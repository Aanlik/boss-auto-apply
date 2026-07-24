"""AI 岗位 JD 分析服务 — 专业招聘视角"""
from app.models.resume import JDAnalysis
from app.services.ai_client import chat_json

SYSTEM_PROMPT = """你是一位在头部互联网公司有 10 年经验的技术招聘经理（TA Manager），面过 3000+ 候选人，经手过 500+ 个 JD。

请深度拆解这份岗位 JD，返回 JSON：
{
  "must_have_skills": ["硬性必备技能/工具/语言，缺了基本没戏"],
  "nice_to_have_skills": ["加分项，有则锦上添花"],
  "experience_requirements": ["经验年限、领域、项目类型等硬性要求"],
  "soft_skills": ["沟通、领导力、自驱等软性要求"],
  "domain_knowledge": ["业务领域知识要求，如金融、教育、电商等"],
  "education_requirements": "学历硬门槛，如'本科及以上/硕士优先'，没有则填'未明确'",
  "summary_text": "用一段话概括这个岗位的真实画像：核心解决什么问题、团队在做什么方向、对候选人的核心期待（80 字内）"
}

分析原则：
1. 区分"写出来的要求"和"实际要求"——有些 JD 写得天花乱坠，真实需求可能在字里行间
2. 识别隐性要求：比如 JD 提到"高并发""海量数据"，实际要求的是分布式系统经验和大数据技术栈
3. 技能按重要性排序：最重要的放前面
4. 如果 JD 含糊（如"熟悉常用数据库"），明确列出行业标准（MySQL/PostgreSQL/Redis）

只返回 JSON，不要解释，不要 markdown。"""


def _fmt_chat(chat_history):
    if not chat_history: return "无"
    return "\n".join(f"{'用户' if m.get('role')=='user' else 'AI'}: {m.get('content','')[:200]}" for m in (chat_history or [])[-8:])


def analyze_jd(job_title: str, company: str, jd_text: str, chat_history=None) -> JDAnalysis:
    user = f"""分析以下岗位 JD：

岗位：{job_title}
公司：{company or '未知'}
JD 原文：
{jd_text[:3000]}

对话上下文：
{_fmt_chat(chat_history)}
"""
    try:
        data = chat_json(SYSTEM_PROMPT, user)
        return JDAnalysis(
            must_have_skills=data.get("must_have_skills", []),
            nice_to_have_skills=data.get("nice_to_have_skills", []),
            experience_requirements=data.get("experience_requirements", []),
            soft_skills=data.get("soft_skills", []),
            domain_knowledge=data.get("domain_knowledge", []),
            education_requirements=data.get("education_requirements", "未明确"),
            summary_text=data.get("summary_text", ""),
        )
    except Exception as e:
        return JDAnalysis(
            must_have_skills=[],
            summary_text=f"AI 分析不可用：{str(e)[:80]}",
        )
