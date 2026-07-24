from app.services.scoring import rank_jobs, score_job


def test_score_job_combines_match_risk_and_outlook():
    job = {"title": "Python 后端工程师", "company": "A公司"}
    resume = {"skills": ["Python"]}
    scored = score_job(job, resume, {"risk": "low", "outlook": "positive"})
    assert scored.total_score > 0
    assert scored.match_score > 0


def test_rank_jobs_sorts_highest_first():
    jobs = [
        {"title": "Java 后端工程师", "company": "A公司"},
        {"title": "Python 后端工程师", "company": "B公司"},
    ]
    resume = {"skills": ["Python"]}
    ranked = rank_jobs(jobs, resume, {"B公司": {"risk": "low", "outlook": "positive"}})
    assert ranked[0]["title"] == "Python 后端工程师"
