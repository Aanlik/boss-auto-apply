from app.services.resume_optimizer import optimize_resume


def test_optimize_resume_uses_selected_job_jd():
    profile = {
        "title": "后端工程师",
        "skills": ["Python", "FastAPI"],
        "projects": ["支付系统"],
    }
    target_job = {
        "title": "Python 后端工程师",
        "company": "A 公司",
        "jd_text": "负责 Python、FastAPI、SQLAlchemy 和 Redis 的后端开发，要求有支付系统经验。",
    }

    result = optimize_resume(profile, target_job=target_job)

    assert "A 公司" in result.summary
    assert "FastAPI" in result.summary
    assert "Python" in result.matched_skills
    assert "Redis" in result.missing_skills
    assert len(result.bullets) >= 3


def test_optimize_resume_missing_many_skills():
    profile = {"title": "前端工程师", "skills": ["React"], "projects": []}
    target_job = {
        "title": "Python 后端工程师",
        "company": "B 公司",
        "jd_text": "要求 Python、Docker、Kubernetes、MySQL。",
    }

    result = optimize_resume(profile, target_job=target_job)

    assert len(result.matched_skills) == 0
    assert "Python" in result.missing_skills
    assert "Docker" in result.missing_skills


def test_optimize_resume_all_matched():
    profile = {"title": "全栈工程师", "skills": ["Python", "FastAPI", "Redis", "PostgreSQL", "Docker"], "projects": []}
    target_job = {
        "title": "Python 后端工程师",
        "jd_text": "要求 Python、FastAPI、Redis、PostgreSQL。",
    }

    result = optimize_resume(profile, target_job=target_job)

    assert len(result.missing_skills) == 0
    assert "Python" in result.matched_skills
    assert "匹配" in result.summary


def test_optimize_resume_with_soft_requirements():
    profile = {"title": "后端工程师", "skills": ["Python", "MySQL"], "projects": []}
    target_job = {
        "title": "高级后端工程师",
        "jd_text": "要求3年以上Python经验，本科及以上学历，有高并发系统设计经验。",
    }

    result = optimize_resume(profile, target_job=target_job)

    assert any("3年" in b or "学历" in b for b in result.bullets)
    assert "Python" in result.matched_skills
