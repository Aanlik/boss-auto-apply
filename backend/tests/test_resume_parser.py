from app.services.resume_parser import parse_resume_text, parse_resume_bytes


def test_parse_resume_text_extracts_basic_fields():
    text = (
        "张三\n"
        "Python 后端工程师\n"
        "## 技能\n"
        "Python, FastAPI, SQLAlchemy, Docker, MySQL, Redis, Linux, Git\n"
        "## 工作经历\n"
        "2020.06 - 2023.08 | A 公司 | 后端工程师\n"
        "负责支付系统开发，使用 FastAPI 和 SQLAlchemy\n"
        "2023.09 - 至今 | B 公司 | 高级后端工程师\n"
        "主导订单系统重构，引入 Redis 缓存\n"
        "## 项目经历\n"
        "支付网关项目\n"
        "基于 FastAPI 实现三方支付对接\n"
        "## 教育经历\n"
        "清华大学 | 计算机科学 | 本科\n"
    )
    profile = parse_resume_text(text)

    assert profile.name == "张三"
    assert profile.title == "后端工程师"
    assert "Python" in profile.skills
    assert "FastAPI" in profile.skills
    assert "Docker" in profile.skills

    assert len(profile.work_experience) >= 1
    assert any("A 公司" in exp.company for exp in profile.work_experience)

    assert len(profile.projects) >= 1
    assert any("支付网关" in proj.name for proj in profile.projects)

    assert len(profile.education) >= 1
    assert any("清华大学" in edu.institution for edu in profile.education)


def test_parse_resume_bytes_handles_utf8():
    data = "李四\n前端工程师\n技能: React, TypeScript, Vue".encode("utf-8")
    profile = parse_resume_bytes(data)
    assert profile.title == "前端工程师"
    assert "React" in profile.skills


def test_parse_compact_resume():
    text = (
        "王五\n"
        "全栈工程师\n"
        "技能：Python, React, PostgreSQL, Docker\n"
        "工作经历：2021 - 至今 C 公司 全栈工程师\n"
        "教育：北京大学 软件工程 硕士\n"
    )
    profile = parse_resume_text(text)
    assert profile.name == "王五"
    assert "Python" in profile.skills
    assert "React" in profile.skills
