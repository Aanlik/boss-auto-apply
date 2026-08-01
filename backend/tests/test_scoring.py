import asyncio
import json
from app.services.scoring import _parse_json, analyze_jd_for_matching, match_resume_to_job, rank_jobs_ai


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


def test_match_resume_retries_an_invalid_ai_response_before_falling_back(monkeypatch):
    """一次格式异常不应直接把岗位标成 API 未配置。"""
    import app.services.scoring as scoring

    class FakeClient:
        def __init__(self):
            self.responses = iter([
                "这不是 JSON",
                json.dumps({
                    "match_score": 86,
                    "skill_match_rate": 0.8,
                    "experience_match": "经验匹配",
                    "education_match": "学历匹配",
                    "highlights": ["HRBP"],
                    "gaps": [],
                    "recommendation": "recommend",
                    "reason": "具备岗位核心经验",
                }),
            ])
            self.calls = 0

        async def chat(self, *_args, **_kwargs):
            self.calls += 1
            return next(self.responses)

    client = FakeClient()
    monkeypatch.setattr(scoring, "get_ai_client", lambda: client)

    result = asyncio.run(scoring.match_resume_to_job(
        {"skills": ["招聘", "绩效"]},
        {"title": "HRBP", "company": "示例公司"},
        {"core_requirements": ["HRBP 经验"]},
    ))

    assert client.calls == 2
    assert result["match_score"] == 86
    assert result.get("failureReason") is None


def test_match_resume_requests_json_mode_with_sufficient_output_budget(monkeypatch):
    """排序匹配必须请求结构化 JSON，避免仅依赖提示词约束模型输出。"""
    import app.services.scoring as scoring

    class FakeClient:
        def __init__(self):
            self.kwargs = {}

        async def chat(self, _prompt, **kwargs):
            self.kwargs = kwargs
            return json.dumps({
                "match_score": 86,
                "skill_match_rate": 0.8,
                "experience_match": "经验匹配",
                "education_match": "学历匹配",
                "highlights": ["HRBP"],
                "gaps": [],
                "recommendation": "recommend",
                "reason": "具备岗位核心经验",
            })

    client = FakeClient()
    monkeypatch.setattr(scoring, "get_ai_client", lambda: client)

    result = asyncio.run(scoring.match_resume_to_job(
        {"skills": ["招聘", "绩效"]},
        {"title": "HRBP", "company": "示例公司"},
        {"core_requirements": ["HRBP 经验"]},
    ))

    assert result["match_score"] == 86
    assert client.kwargs["json_mode"] is True
    assert client.kwargs["max_tokens"] >= 800


def test_match_resume_uses_plain_non_thinking_request_for_the_final_retry(monkeypatch):
    """结构化响应连续为空时，最后一次应以非思考普通请求兜底。"""
    import app.services.scoring as scoring

    valid_response = json.dumps({
        "match_score": 86,
        "skill_match_rate": 0.8,
        "experience_match": "经验匹配",
        "education_match": "学历匹配",
        "highlights": ["HRBP"],
        "gaps": [],
        "recommendation": "recommend",
        "reason": "具备岗位核心经验",
    })

    class FakeClient:
        def __init__(self):
            self.calls = []
            self.responses = iter(["", "", valid_response])

        async def chat(self, _prompt, **kwargs):
            self.calls.append(kwargs)
            return next(self.responses)

    client = FakeClient()
    monkeypatch.setattr(scoring, "get_ai_client", lambda: client)

    result = asyncio.run(scoring.match_resume_to_job(
        {"skills": ["招聘", "绩效"]},
        {"title": "HRBP", "company": "示例公司"},
        {"core_requirements": ["HRBP 经验"]},
    ))

    assert result["match_score"] == 86
    assert [call["json_mode"] for call in client.calls] == [True, True, False]
    assert all(call["disable_thinking"] is True for call in client.calls)


def test_parse_json_recovers_markdown_json_with_a_trailing_comma():
    """模型常见的代码块与尾逗号不应让有效匹配结果整体失败。"""
    raw = '''```json
    {"match_score": 86, "highlights": ["HRBP"], "gaps": [], "recommendation": "recommend",}
    ```'''

    assert _parse_json(raw)["match_score"] == 86


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


def test_rank_jobs_retries_a_cached_temporary_match_when_ai_is_available(tmp_path, monkeypatch):
    """临时匹配分不能阻止恢复 AI 配置后的重新分析。"""
    import app.services.scoring as scoring

    monkeypatch.setattr(scoring, "RANKING_CACHE_FILE", tmp_path / "ranking_cache.json")
    scoring._RANKING_MEMORY_CACHE.clear()
    jobs = [{"id": "retry-job", "title": "后端工程师", "company": "示例科技", "jd_text": "Python"}]
    resume = {"skills": ["Python"]}
    fallback = {"match_score": 50, "reason": "匹配度分析待AI配置后更新（请在设置中配置API Key）"}

    jd = {"core_requirements": ["Python"]}
    scoring._write_ranking_cache(scoring._ranking_cache_key("jd", job=jobs[0]), jd)
    scoring._write_ranking_cache(scoring._ranking_cache_key("match", job=jobs[0], resume=resume, jd_analysis=jd), fallback)
    calls = {"match": 0}

    async def fake_match(*_args):
        calls["match"] += 1
        return {"match_score": 88, "highlights": ["Python"], "gaps": [], "recommendation": "recommend", "reason": "技能匹配"}

    monkeypatch.setattr(scoring, "match_resume_to_job", fake_match)

    ranked = asyncio.run(rank_jobs_ai(jobs, resume, {}))

    assert calls == {"match": 1}
    assert ranked[0]["matchScore"] == 88
    assert ranked[0]["reason"] == "技能匹配"


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


def test_continue_ranking_merges_new_results_with_existing_results(monkeypatch):
    """继续排序只补齐缺失岗位，不能覆盖已经完成的排序结果。"""
    from app.routes import jobs as jobs_route
    from app.routes import scoring as scoring_route

    existing = [{"jobId": "job-1", "jobTitle": "已完成岗位", "compositeScore": 90}]
    saved: list[list[dict]] = []

    async def fake_rank_jobs(*_args, **_kwargs):
        return [{"jobId": "job-2", "jobTitle": "补齐岗位", "compositeScore": 80}]

    monkeypatch.setattr(jobs_route, "_all_jobs", lambda: [
        {"id": "job-2", "title": "补齐岗位", "company": "示例公司"},
    ])
    monkeypatch.setattr(scoring_route, "load_rankings", lambda: existing)
    monkeypatch.setattr(scoring_route, "save_rankings", lambda rankings: saved.append(rankings) or rankings)
    monkeypatch.setattr(scoring_route, "rank_jobs_ai", fake_rank_jobs)
    monkeypatch.setattr(scoring_route, "start_task", lambda *_args, **_kwargs: {"id": "ranking-task"})
    monkeypatch.setattr(scoring_route, "find_running_task", lambda *_args: None)
    monkeypatch.setattr(scoring_route, "update_task", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(scoring_route, "complete_task", lambda *_args, **_kwargs: None)

    result = asyncio.run(scoring_route.rank_jobs_endpoint({
        "job_ids": ["job-2"],
        "resume": {"skills": ["Python"]},
        "diligence_reports": {},
        "continue_existing": True,
    }))

    assert [item["jobId"] for item in result["rankings"]] == ["job-1", "job-2"]
    assert saved == [result["rankings"]]


def test_ranking_does_not_persist_temporary_ai_results(monkeypatch):
    """临时 50 分只用于本次失败说明，不能混入正式排序结果。"""
    from app.routes import jobs as jobs_route
    from app.routes import scoring as scoring_route

    saved: list[list[dict]] = []

    async def fake_rank_jobs(*_args, **_kwargs):
        return [
            {"jobId": "valid-job", "jobTitle": "有效", "compositeScore": 88, "matchStatus": "completed"},
            {"jobId": "failed-job", "jobTitle": "失败", "compositeScore": 50, "matchStatus": "failed", "failureReason": "invalid_response"},
        ]

    monkeypatch.setattr(jobs_route, "_all_jobs", lambda: [
        {"id": "valid-job", "title": "有效", "company": "示例公司"},
        {"id": "failed-job", "title": "失败", "company": "示例公司"},
    ])
    monkeypatch.setattr(scoring_route, "load_rankings", lambda: [])
    monkeypatch.setattr(scoring_route, "save_rankings", lambda rankings: saved.append(rankings) or rankings)
    monkeypatch.setattr(scoring_route, "rank_jobs_ai", fake_rank_jobs)
    monkeypatch.setattr(scoring_route, "start_task", lambda *_args, **_kwargs: {"id": "ranking-task"})
    monkeypatch.setattr(scoring_route, "find_running_task", lambda *_args: None)
    monkeypatch.setattr(scoring_route, "update_task", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(scoring_route, "complete_task", lambda *_args, **_kwargs: None)

    result = asyncio.run(scoring_route.rank_jobs_endpoint({
        "job_ids": ["valid-job", "failed-job"],
        "resume": {"skills": ["Python"]},
        "diligence_reports": {},
    }))

    assert [item["jobId"] for item in result["rankings"]] == ["valid-job"]
    assert result["failedCount"] == 1
    assert result["failedRankings"] == [{"jobId": "failed-job", "reason": "invalid_response"}]
    assert saved == [result["rankings"]]
