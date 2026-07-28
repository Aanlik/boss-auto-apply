import asyncio
import json
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.models.job import JobRecord


client = TestClient(app)


def test_old_jobs_are_marked_suspected_expired_instead_of_deleted(tmp_path, monkeypatch):
    import app.routes.jobs as jobs_route

    old_date = (datetime.now() - timedelta(days=120)).isoformat()
    monkeypatch.setattr(jobs_route, "JOBS_FILE", tmp_path / "jobs.json")
    monkeypatch.setattr(jobs_route, "_job_store", {})
    jobs_route.JOBS_FILE.write_text(json.dumps({
        "job-old": JobRecord(id="job-old", title="产品经理", company="旧公司", fetched_at=old_date).model_dump()
    }, ensure_ascii=False))

    jobs_route._load_jobs()

    assert "job-old" in jobs_route._job_store
    job = jobs_route._job_store["job-old"]
    assert job.lifecycle_status == "suspected_expired"
    assert job.stale_reason == "抓取时间超过 90 天"


def test_company_blacklist_export_import_roundtrip(tmp_path, monkeypatch):
    from app.services import workflow_persistence as persistence
    import app.routes.jobs as jobs_route

    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(jobs_route, "_job_store", {})
    client.post("/api/jobs/company-blacklist", json={"company_name": "示例科技有限公司"})

    exported = client.get("/api/jobs/company-blacklist/export").json()
    assert exported["kind"] == "company_blacklist"
    assert exported["companies"][0]["name"] == "示例科技有限公司"

    client.request("DELETE", "/api/jobs/company-blacklist", json={"company_name": "示例科技有限公司"})
    imported = client.post("/api/jobs/company-blacklist/import", json=exported)

    assert imported.status_code == 200
    assert imported.json()["total"] == 1


def test_company_blacklist_hides_jobs_without_deleting_and_restores_on_remove(tmp_path, monkeypatch):
    from app.services import workflow_persistence as persistence
    import app.routes.jobs as jobs_route

    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(id="job-1", title="产品经理", company="示例科技有限公司")
    })

    added = client.post("/api/jobs/company-blacklist", json={"company_name": "示例科技有限公司"})
    hidden_pool = client.get("/api/jobs/pool").json()

    assert added.status_code == 200
    assert added.json()["removed"] == 1
    assert "job-1" in jobs_route._job_store
    assert jobs_route._job_store["job-1"].lifecycle_status == "blacklisted"
    assert hidden_pool["total"] == 0

    removed = client.request("DELETE", "/api/jobs/company-blacklist", json={"company_name": "示例科技有限公司"})
    restored_pool = client.get("/api/jobs/pool").json()

    assert removed.status_code == 200
    assert removed.json()["restored"] == 1
    assert jobs_route._job_store["job-1"].lifecycle_status == "active"
    assert restored_pool["total"] == 1


def test_job_pool_can_include_hidden_blacklisted_jobs_for_quality_drilldown(tmp_path, monkeypatch):
    from app.services import workflow_persistence as persistence
    import app.routes.jobs as jobs_route

    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(id="job-1", title="产品经理", company="示例科技有限公司")
    })
    client.post("/api/jobs/company-blacklist", json={"company_name": "示例科技有限公司"})

    visible_pool = client.get("/api/jobs/pool").json()
    full_pool = client.get("/api/jobs/pool?include_hidden=true").json()

    assert visible_pool["total"] == 0
    assert full_pool["total"] == 1
    assert full_pool["hidden"] == 1
    assert full_pool["jobs"][0]["lifecycle_status"] == "blacklisted"


def test_settings_export_is_masked_by_default_and_can_import(tmp_path, monkeypatch):
    import app.routes.settings as settings_route
    from app.services import ai_client, business_info

    monkeypatch.setattr(ai_client, "CONFIG_FILE", tmp_path / "provider.json")
    monkeypatch.setattr(settings_route, "BAIDU_CONFIG_FILE", tmp_path / "baidu_config.json")
    monkeypatch.setattr(business_info, "CONFIG_FILE", tmp_path / "business_info_config.json")
    ai_client.set_config("deepseek", "sk-secret-value", "https://api.deepseek.com", "deepseek-chat")
    settings_route._write_baidu_config({"api_key": "baidu-secret"})
    business_info.set_config("sid-secret", "skey-secret")

    exported = client.get("/api/settings/export").json()

    assert exported["kind"] == "settings_backup"
    assert exported["provider"]["api_key"] == ""
    assert exported["provider"]["masked"]
    assert exported["baidu"]["api_key"] == ""
    assert exported["business"]["secret_key"] == ""

    blocked = client.get("/api/settings/export?include_secret=true")
    assert blocked.status_code == 403

    token_response = client.post("/api/settings/export/authorize")
    assert token_response.status_code == 200
    token = token_response.json()["token"]

    full = client.get(
        "/api/settings/export?include_secret=true",
        headers={"X-Settings-Export-Token": token},
    ).json()
    assert full["provider"]["api_key"] == "sk-secret-value"
    response = client.post("/api/settings/import", json=full)
    assert response.status_code == 200
    assert response.json()["imported"] == ["provider", "baidu", "business"]

    reused = client.get(
        "/api/settings/export?include_secret=true",
        headers={"X-Settings-Export-Token": token},
    )
    assert reused.status_code == 403


def test_diligence_refresh_business_updates_existing_report(monkeypatch, tmp_path):
    from app.services import workflow_persistence as persistence
    import app.routes.diligence as diligence_route

    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)
    persistence.save_diligence_report({
        "companyName": "示例科技",
        "companyKey": "old-key",
        "companyScore": 60,
        "riskLevel": "medium",
        "businessInfo": {"companyName": "示例科技", "companyKey": "old-key"},
    })

    async def fake_query(name):
        return {"companyName": "示例科技有限公司", "companyKey": "new-key", "registeredIndustry": "电商"}

    monkeypatch.setattr(diligence_route, "query_business_info", fake_query)

    response = client.post("/api/diligence/refresh", json={"company_name": "示例科技", "mode": "business"})

    assert response.status_code == 200
    body = response.json()
    assert body["businessInfo"]["companyKey"] == "new-key"
    assert body["companyName"] == "示例科技有限公司"
    assert body["refreshMode"] == "business"


def test_scoring_weights_are_persisted_and_applied(tmp_path, monkeypatch):
    import app.routes.scoring as scoring_route
    import app.services.scoring as scoring

    monkeypatch.setattr(scoring_route, "RANKING_SETTINGS_FILE", tmp_path / "ranking_settings.json")
    monkeypatch.setattr(scoring, "RANKING_SETTINGS_FILE", tmp_path / "ranking_settings.json")

    response = client.post("/api/scoring/weights", json={"company_weight": 0.2, "match_weight": 0.8})
    assert response.status_code == 200
    assert response.json()["weights"] == {"company_weight": 0.2, "match_weight": 0.8}

    async def fake_jd(job):
        return {"core_requirements": ["Python"]}

    async def fake_match(resume, job, jd_analysis):
        return {"match_score": 90, "highlights": [], "gaps": [], "recommendation": "recommend", "reason": "匹配"}

    monkeypatch.setattr(scoring, "analyze_jd_for_matching", fake_jd)
    monkeypatch.setattr(scoring, "match_resume_to_job", fake_match)

    ranked = asyncio.run(scoring.rank_jobs_ai(
        [{"id": "job-1", "title": "后端", "company": "A", "salary": "20K"}],
        {"skills": ["Python"]},
        {"A": {"companyScore": 50}},
    ))

    assert ranked[0]["compositeScore"] == 82
    assert ranked[0]["weights"] == {"company_weight": 0.2, "match_weight": 0.8}


def test_pdf_template_options_and_ats_template_supported():
    from app.services.resume_pdf_exporter import PDF_TEMPLATES, export_resume_pdf
    from app.models.resume import ResumeProfile

    assert set(PDF_TEMPLATES) >= {"modern", "classic", "ats"}
    pdf = export_resume_pdf(ResumeProfile(name="张三", title="产品经理"), {}, "示例公司", "产品经理", template="ats")
    assert pdf.startswith(b"%PDF")


def test_job_pool_quality_summary_exposes_duplicates_and_lifecycle(monkeypatch):
    import app.routes.jobs as jobs_route

    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(
            id="job-1",
            title="产品经理",
            company="示例科技",
            city="郑州",
            jd_text="负责用户增长",
            dedupe_key="示例科技|产品经理|郑州",
        ),
        "job-2": JobRecord(
            id="job-2",
            title="产品经理",
            company="示例科技",
            city="郑州",
            dedupe_key="示例科技|产品经理|郑州",
        ),
        "job-3": JobRecord(
            id="job-3",
            title="运营",
            company="旧公司",
            city="上海",
            lifecycle_status="suspected_expired",
            application_status="interviewing",
        ),
    })

    response = client.get("/api/jobs/pool/quality")

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["total"] == 3
    assert body["summary"]["with_jd"] == 1
    assert body["summary"]["missing_jd"] == 2
    assert body["summary"]["suspected_expired"] == 1
    assert body["summary"]["duplicate_groups"] == 1
    assert body["summary"]["duplicate_jobs"] == 2
    assert body["summary"]["application_statuses"]["pending"] == 2
    assert body["summary"]["application_statuses"]["interviewing"] == 1
    assert body["duplicateGroups"][0]["key"] == "示例科技|产品经理|郑州"
    assert body["duplicateGroups"][0]["jobIds"] == ["job-1", "job-2"]


def test_job_status_change_keeps_history_and_audit_event(tmp_path, monkeypatch):
    import app.routes.jobs as jobs_route
    from app.services import workflow_persistence as persistence

    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(id="job-1", title="产品经理", company="示例科技"),
    })

    response = client.post("/api/jobs/status", json={"job_id": "job-1", "status": "interviewing", "note": "约周五面试"})
    history = client.get("/api/jobs/job-1/history")
    logs = client.get("/api/maintenance/logs?limit=10")

    assert response.status_code == 200
    assert history.json()["history"][-1]["status"] == "interviewing"
    assert history.json()["history"][-1]["note"] == "约周五面试"
    assert any(event["category"] == "job_status" for event in logs.json()["events"])


def test_batch_quality_includes_rates_and_job_compare(monkeypatch):
    import app.routes.jobs as jobs_route

    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(
            id="job-1", title="产品经理", company="示例科技", city="上海",
            jd_text="负责产品规划", capture_batch_id="batch-1",
        ),
        "job-2": JobRecord(
            id="job-2", title="运营", company="风险科技", city="上海",
            jd_text="", capture_batch_id="batch-1", lifecycle_status="suspected_expired",
        ),
    })

    quality = client.get("/api/jobs/pool/quality").json()
    compare = client.post("/api/jobs/compare", json={"job_ids": ["job-1", "job-2"]})

    batch = quality["batches"][0]
    assert batch["jd_completion_rate"] == 50
    assert batch["stale_rate"] == 50
    assert compare.status_code == 200
    assert compare.json()["jobs"][0]["id"] == "job-1"
    assert "jd_quality" in compare.json()["comparison"]


def test_application_funnel_reports_conversion_and_batch_performance(monkeypatch):
    import app.routes.jobs as jobs_route

    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(id="job-1", title="产品", company="A", capture_batch_id="b1", application_status="greeted", decision_status="recommended"),
        "job-2": JobRecord(id="job-2", title="运营", company="B", capture_batch_id="b1", application_status="interviewing", decision_status="recommended"),
        "job-3": JobRecord(id="job-3", title="销售", company="C", capture_batch_id="b2", application_status="rejected", decision_status="risky"),
        "job-4": JobRecord(id="job-4", title="客服", company="D", capture_batch_id="b2", application_status="pending"),
    })

    response = client.get("/api/jobs/funnel")

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["total"] == 4
    assert body["summary"]["contacted"] == 3
    assert body["summary"]["interviewRate"] == 25
    assert body["batches"][0]["id"] in {"b1", "b2"}
    assert body["recommendations"]


def test_user_preferences_can_be_saved_for_personalized_ranking(tmp_path, monkeypatch):
    from app.services import preferences

    monkeypatch.setattr(preferences, "PREFERENCES_FILE", tmp_path / "preferences.json")

    saved = client.post("/api/settings/preferences", json={
        "stability": 80,
        "salary": 60,
        "growth": 70,
        "match": 90,
        "avoid_industries": ["教培"],
        "preferred_cities": ["上海"],
    })
    loaded = client.get("/api/settings/preferences")

    assert saved.status_code == 200
    assert loaded.json()["preferences"]["stability"] == 80
    assert "教培" in loaded.json()["preferences"]["avoid_industries"]


def test_ranking_explanation_includes_user_preferences(tmp_path, monkeypatch):
    import app.services.scoring as scoring
    from app.services import preferences

    monkeypatch.setattr(preferences, "PREFERENCES_FILE", tmp_path / "preferences.json")
    preferences.save_preferences({
        "stability": 90,
        "salary": 40,
        "growth": 70,
        "match": 85,
        "avoid_industries": ["教培"],
        "preferred_cities": ["上海"],
    })

    async def fake_jd(job):
        return {"core_requirements": ["产品规划"], "hard_requirements": []}

    async def fake_match(resume, job, jd_analysis):
        return {"match_score": 80, "highlights": ["产品经验匹配"], "gaps": [], "recommendation": "recommend", "reason": "匹配"}

    monkeypatch.setattr(scoring, "analyze_jd_for_matching", fake_jd)
    monkeypatch.setattr(scoring, "match_resume_to_job", fake_match)

    ranked = asyncio.run(scoring.rank_jobs_ai(
        [{"id": "job-1", "title": "产品经理", "company": "示例科技", "city": "上海", "salary": "20-30K", "jd_text": "负责产品规划"}],
        {"skills": ["产品规划"]},
        {"示例科技": {"companyScore": 80, "riskLevel": "low"}},
    ))

    assert ranked[0]["explanation"]["preferenceSignals"]
    assert any("稳定性" in item for item in ranked[0]["explanation"]["preferenceSignals"])


def test_deleted_jobs_can_be_restored_from_archive(tmp_path, monkeypatch):
    import app.routes.jobs as jobs_route

    monkeypatch.setattr(jobs_route, "JOBS_FILE", tmp_path / "jobs.json")
    monkeypatch.setattr(jobs_route, "DELETED_JOBS_FILE", tmp_path / "deleted_jobs.json")
    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(id="job-1", title="产品经理", company="示例科技"),
    })

    deleted = client.delete("/api/jobs/job-1")
    restored = client.post("/api/jobs/restore", json={"job_ids": ["job-1"]})

    assert deleted.status_code == 200
    assert restored.status_code == 200
    assert restored.json()["restored"] == 1
    assert "job-1" in jobs_route._job_store


def test_standard_api_error_preserves_code_message_and_action():
    from app.services.api_errors import api_error

    err = api_error("BOSS_NOT_LOGIN", "需要先登录 BOSS", "打开登录")

    assert err == {
        "code": "BOSS_NOT_LOGIN",
        "message": "需要先登录 BOSS",
        "action": "打开登录",
    }


def test_job_pipeline_status_can_be_updated(monkeypatch):
    import app.routes.jobs as jobs_route

    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(id="job-1", title="产品经理", company="示例科技")
    })

    response = client.post("/api/jobs/status", json={"job_id": "job-1", "status": "interviewing", "note": "约了周三"})

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == "job-1"
    assert body["application_status"] == "interviewing"
    assert body["application_note"] == "约了周三"


def test_job_decision_status_can_be_updated(monkeypatch):
    import app.routes.jobs as jobs_route

    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(id="job-1", title="产品经理", company="示例科技")
    })

    response = client.post("/api/jobs/decision", json={"job_id": "job-1", "status": "recommended"})

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == "job-1"
    assert body["decision_status"] == "recommended"
    assert jobs_route._job_store["job-1"].decision_status == "recommended"


def test_workflow_task_failure_keeps_recovery_action(tmp_path, monkeypatch):
    from app.services import workflow_tasks

    monkeypatch.setattr(workflow_tasks, "TASKS_FILE", tmp_path / "tasks.json")

    task = workflow_tasks.start_task("jd_enrich", "获取 JD 详情", total=3)
    workflow_tasks.fail_task(
        task["id"],
        "BOSS 登录已失效",
        error_code="BOSS_NOT_LOGIN",
        action="重新登录 BOSS 后重试",
        retryable=True,
    )

    response = client.get("/api/workflow/tasks")

    assert response.status_code == 200
    failed = response.json()["tasks"][0]
    assert failed["status"] == "failed"
    assert failed["message"] == "BOSS 登录已失效"
    assert failed["action"] == "重新登录 BOSS 后重试"
    assert failed["retryable"] is True


def test_duplicate_job_merge_keeps_best_jd_tags_and_greeted(monkeypatch):
    import app.routes.jobs as jobs_route

    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(id="job-1", title="产品经理", company="A", city="郑州", jd_text="", tags=["重点"]),
        "job-2": JobRecord(id="job-2", title="产品经理", company="A", city="郑州", jd_text="完整 JD", greeted=True, tags=["已沟通"]),
    })

    response = client.post("/api/jobs/duplicates/merge", json={"job_ids": ["job-1", "job-2"]})

    assert response.status_code == 200
    body = response.json()
    assert body["kept"] == "job-2"
    assert body["removed"] == ["job-1"]
    assert list(jobs_route._job_store) == ["job-2"]
    assert jobs_route._job_store["job-2"].tags == ["已沟通", "重点"]
    assert jobs_route._job_store["job-2"].greeted is True


def test_workflow_task_lifecycle_is_persisted(tmp_path, monkeypatch):
    import app.services.workflow_tasks as workflow_tasks
    import app.routes.workflow as workflow_route

    monkeypatch.setattr(workflow_tasks, "TASKS_FILE", tmp_path / "tasks.json")
    monkeypatch.setattr(workflow_route, "workflow_tasks", workflow_tasks)

    task = workflow_tasks.start_task("jd_enrich", "获取 JD 详情", total=3)
    done = workflow_tasks.complete_task(task["id"], done=3, message="完成")

    response = client.get("/api/workflow/tasks")

    assert done["status"] == "completed"
    assert response.status_code == 200
    body = response.json()
    assert body["tasks"][0]["type"] == "jd_enrich"
    assert body["tasks"][0]["done"] == 3
    assert body["tasks"][0]["message"] == "完成"


def test_secret_store_encrypts_and_round_trips_without_plaintext(tmp_path, monkeypatch):
    from app.services import secret_store

    monkeypatch.setattr(secret_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(secret_store, "KEY_FILE", tmp_path / ".secret_key")

    encrypted = secret_store.encrypt_secret("sk-sensitive")

    assert encrypted != "sk-sensitive"
    assert secret_store.decrypt_secret(encrypted) == "sk-sensitive"
    assert secret_store.is_encrypted(encrypted) is True


def test_provider_config_is_stored_encrypted(tmp_path, monkeypatch):
    from app.services import ai_client, secret_store

    monkeypatch.setattr(ai_client, "CONFIG_FILE", tmp_path / "provider.json")
    monkeypatch.setattr(secret_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(secret_store, "KEY_FILE", tmp_path / ".secret_key")
    monkeypatch.setattr(ai_client, "_cached_config", None)

    assert ai_client.set_config("openai", "sk-sensitive", "", "gpt-4.1-mini")

    raw = (tmp_path / "provider.json").read_text(encoding="utf-8")
    assert "sk-sensitive" not in raw
    assert ai_client.get_config()["api_key"] == "sk-sensitive"
