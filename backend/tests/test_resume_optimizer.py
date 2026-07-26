from app.services.resume_optimizer import optimize_resume


def test_optimize_resume_uses_selected_job_jd():
    from app.models.resume import ResumeProfile
    profile = ResumeProfile(
        title="后端工程师",
        skills=["Python", "FastAPI"],
    )
    result = optimize_resume(
        profile, evaluation=None, jd_analysis=None,
        job_title="Python 后端工程师", company="A 公司",
        jd_text="负责 Python、FastAPI、SQLAlchemy 和 Redis 的后端开发，要求有支付系统经验。",
    )
    assert result.summary and len(result.summary) > 0, f"summary should not be empty, got: {result.summary}"
    # note: when AI is unavailable, fallback uses keyword matching
    assert "Python" in result.matched_skills or "Python" in str(result.skills_display)


def test_optimize_resume_missing_many_skills():
    from app.models.resume import ResumeProfile
    profile = ResumeProfile(title="前端工程师", skills=["React"])
    result = optimize_resume(
        profile, evaluation=None, jd_analysis=None,
        job_title="Python 后端工程师", company="B 公司",
        jd_text="要求 Python、Docker、Kubernetes、MySQL。",
    )
    # AI 输出不稳定，只验证返回了合理的缺失技能列表
    assert len(result.missing_skills) >= 2, f"Expected at least 2 missing skills for a React frontend applying to Python backend, got {len(result.missing_skills)}: {result.missing_skills}"


def test_optimize_resume_all_matched():
    from app.models.resume import ResumeProfile
    profile = ResumeProfile(title="全栈工程师", skills=["Python", "FastAPI", "Redis", "PostgreSQL", "Docker"])
    result = optimize_resume(
        profile, evaluation=None, jd_analysis=None,
        job_title="Python 后端工程师",
        jd_text="要求 Python、FastAPI、Redis、PostgreSQL。",
    )
    assert len(result.missing_skills) == 0
    assert "Python" in result.matched_skills


def test_optimize_resume_with_soft_requirements():
    from app.models.resume import ResumeProfile
    profile = ResumeProfile(title="后端工程师", skills=["Python", "MySQL"])
    result = optimize_resume(
        profile, evaluation=None, jd_analysis=None,
        job_title="高级后端工程师",
        jd_text="要求3年以上Python经验，本科及以上学历，有高并发系统设计经验。",
    )
    assert "Python" in result.matched_skills
