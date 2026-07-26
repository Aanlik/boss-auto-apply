"""简历格式化工具 — 供 evaluator / optimizer / parser 共享使用"""

def fmt_exp(profile) -> str:
    """格式化工作经历"""
    if not profile.work_experience:
        return "无"
    return "\n".join(
        f"- {e.title} @ {e.company} ({e.duration}): {e.description}"
        for e in profile.work_experience
    )

def fmt_edu(profile) -> str:
    """格式化教育背景"""
    if not profile.education:
        return "无"
    return "\n".join(
        f"- {e.institution} | {e.degree} | {e.major} | {e.graduation}"
        for e in profile.education
    )

def fmt_proj(profile) -> str:
    """格式化项目经历"""
    if not profile.projects:
        return "无"
    return "\n".join(
        f"- {x.name} ({', '.join(x.technologies)}): {x.description}"
        for x in profile.projects
    )

def fmt_chat(chat_history) -> str:
    """格式化对话历史（Unicode 安全截断）"""
    if not chat_history:
        return "无"
    result = []
    for m in (chat_history or [])[-8:]:
        content = m.get('content', '') or ''
        # 安全截断：在 200 字符边界处查找完整的 Unicode 码点
        if len(content) > 200:
            truncated = content[:200]
            # 确保不在代理对中间切断
            while truncated and ord(truncated[-1]) >= 0xD800 and ord(truncated[-1]) <= 0xDFFF:
                truncated = truncated[:-1]
            content = truncated
        role = '用户' if m.get('role') == 'user' else 'AI'
        result.append(f"{role}: {content}")
    return "\n".join(result)
