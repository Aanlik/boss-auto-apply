import asyncio
import json
from app.services.scoring import analyze_jd_for_matching, match_resume_to_job, rank_jobs_ai


def test_analyze_jd_fallback():
    """Verifies JD analysis fallback when AI is unavailable."""
    job = {"title": "Python 后端工程师", "company": "A公司", "jd_text": "需要Python和FastAPI"}
    result = asyncio.run(analyze_jd_for_matching(job))
    assert isinstance(result, dict)
    assert "core_requirements" in result


def test_match_resume_to_job_fallback():
    """Verifies resume matching fallback when AI is unavailable."""
    resume = {"skills": ["Python"], "name": "张三"}
    job = {"title": "Python 后端工程师", "company": "A公司"}
    jd_analysis = {"core_requirements": ["Python"]}
    result = asyncio.run(match_resume_to_job(resume, job, jd_analysis))
    assert isinstance(result, dict)
    assert "match_score" in result


def test_rank_jobs_uses_company_key_before_company_name(monkeypatch):
    import app.services.scoring as scoring

    async def fake_jd(job):
        return {"core_requirements": ["Python"]}

    async def fake_match(resume, job, jd_analysis):
        return {
            "match_score": 80,
            "highlights": ["Python"],
            "gaps": [],
            "recommendation": "recommend",
            "reason": "匹配",
        }

    monkeypatch.setattr(scoring, "analyze_jd_for_matching", fake_jd)
    monkeypatch.setattr(scoring, "match_resume_to_job", fake_match)

    jobs = [{
        "id": "job-1",
        "title": "后端工程师",
        "company": "示例科技",
        "company_key": "91410100TEST",
        "salary": "15-25K",
    }]
    diligence = {
        "示例科技有限公司": {
            "companyName": "示例科技有限公司",
            "sourceCompanyName": "示例科技",
            "companyKey": "91410100TEST",
            "companyScore": 90,
        }
    }

    ranked = asyncio.run(rank_jobs_ai(jobs, {"skills": ["Python"]}, diligence))

    assert ranked[0]["companyScore"] == 90
    assert ranked[0]["companyKey"] == "91410100TEST"


def test_ranking_feedback_adjusts_weights_toward_company_risk(tmp_path, monkeypatch):
    import app.services.scoring as scoring
    from app.services import feedback_store, workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(scoring, "RANKING_SETTINGS_FILE", tmp_path / "rankings" / "settings.json")
    feedback_store.save_feedback(
        "ranking",
        "job-risky",
        False,
        context={"weightPreference": "company", "reason": "公司风险应该更重要"},
    )

    weights = scoring.load_feedback_adjusted_weights({"company_weight": 0.4, "match_weight": 0.6})

    assert weights["feedbackAdjusted"] is True
    assert weights["company_weight"] > 0.4
    assert weights["match_weight"] < 0.6
    assert any("公司风险" in item for item in weights["feedbackSignals"])


def test_rank_jobs_reuses_jd_and_match_cache(tmp_path, monkeypatch):
    import app.services.scoring as scoring

    monkeypatch.setattr(scoring, "RANKING_CACHE_FILE", tmp_path / "ranking_cache.json")
    scoring._RANKING_MEMORY_CACHE.clear()
    calls = {"jd": 0, "match": 0}

    async def fake_jd(job):
        calls["jd"] += 1
        return {"core_requirements": [job["title"]]}

    async def fake_match(resume, job, jd_analysis):
        calls["match"] += 1
        return {"match_score": 80, "highlights": [], "gaps": [], "recommendation": "recommend", "reason": "匹配"}

    monkeypatch.setattr(scoring, "analyze_jd_for_matching", fake_jd)
    monkeypatch.setattr(scoring, "match_resume_to_job", fake_match)
    jobs = [{"id": "cache-job", "title": "后端工程师", "company": "示例科技", "jd_text": "Python", "salary": "15-25K"}]
    resume = {"skills": ["Python"]}

    asyncio.run(rank_jobs_ai(jobs, resume, {}))
    asyncio.run(rank_jobs_ai(jobs, resume, {}))

    assert calls == {"jd": 1, "match": 1}
    assert json.loads((tmp_path / "ranking_cache.json").read_text())


def test_rank_jobs_limits_ai_concurrency(tmp_path, monkeypatch):
    import app.services.scoring as scoring

    monkeypatch.setattr(scoring, "RANKING_CACHE_FILE", tmp_path / "ranking_cache.json")
    scoring._RANKING_MEMORY_CACHE.clear()
    active = 0
    peak = 0

    async def fake_jd(job):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {"core_requirements": [job["title"]]}

    async def fake_match(resume, job, jd_analysis):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {"match_score": 80, "highlights": [], "gaps": [], "recommendation": "recommend", "reason": "匹配"}

    monkeypatch.setattr(scoring, "analyze_jd_for_matching", fake_jd)
    monkeypatch.setattr(scoring, "match_resume_to_job", fake_match)
    jobs = [
        {"id": f"concurrent-{i}", "title": f"岗位{i}", "company": "示例科技", "jd_text": str(i)}
        for i in range(8)
    ]

    asyncio.run(rank_jobs_ai(jobs, {"skills": ["Python"]}, {}))

    assert peak <= scoring.RANKING_MAX_CONCURRENCY
