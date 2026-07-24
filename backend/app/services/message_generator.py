from app.models.message import MessageDraft


def generate_greeting(job_title: str, resume_summary: str, company_summary: str) -> str:
    if "产品" in job_title:
        opener = "我对产品方向很感兴趣"
    elif "前端" in job_title:
        opener = "我在前端工程方向有相关经验"
    elif "后端" in job_title:
        opener = "我在后端工程方向有较多实践"
    else:
        opener = "我对这个岗位很感兴趣"
    return f"您好，{opener}。我有 {resume_summary}，也关注贵司 {company_summary}，希望进一步沟通。"


def build_message_draft(job_title: str, resume_summary: str, company_summary: str) -> MessageDraft:
    return MessageDraft(job_title=job_title, draft=generate_greeting(job_title, resume_summary, company_summary))


def revise_greeting(draft: str, edit_hint: str) -> str:
    if not edit_hint.strip():
        return draft
    return f"{draft}（已按建议调整：{edit_hint.strip()}）"
