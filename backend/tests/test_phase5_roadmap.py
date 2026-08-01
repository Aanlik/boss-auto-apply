from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models.job import JobRecord


client = TestClient(app)


def test_career_assistant_generates_application_strategy(monkeypatch):
    import app.routes.jobs as jobs_route

    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(id="job-1", title="产品经理", company="稳健科技", jd_text="负责产品规划", decision_status="recommended"),
    })

    response = client.post("/api/assistant/application-strategy", json={
        "job_id": "job-1",
        "resume": {"skills": ["产品规划"]},
        "diligence": {"companyScore": 82, "riskLevel": "low"},
        "ranking": {"matchScore": 85, "compositeScore": 84},
    })

    assert response.status_code == 200
    body = response.json()
    assert body["strategy"] == "priority_apply"
    assert body["nextActions"]
    assert body["confidence"] >= 70


def test_jd_quality_detects_noise_and_missing_responsibility():
    response = client.post("/api/assistant/jd-quality", json={
        "job": {
            "title": "HRBP",
            "company": "河南云泽",
            "jd_text": "组织发展 招聘 人才发展 教育 医疗健康 电商 1100人 + 11层楼 + 成立15年 = ？在线",
        }
    })

    assert response.status_code == 200
    body = response.json()
    assert body["noiseLevel"] in {"medium", "high"}
    assert any("营销" in item or "噪音" in item for item in body["signals"])
    assert body["authenticity"] in {"weak", "medium"}


def test_resume_rewrite_advice_and_interview_prep():
    payload = {
        "job": {"title": "产品经理", "company": "示例科技", "jd_text": "负责用户增长、数据分析、跨部门协作"},
        "resume": {"skills": ["数据分析"], "projects": [{"name": "增长项目", "description": "提升转化"}]},
        "diligence": {"companyName": "示例科技", "businessInfo": {"industry": "软件服务"}, "riskLevel": "medium"},
    }

    rewrite = client.post("/api/assistant/resume-rewrite-advice", json=payload).json()
    prep = client.post("/api/assistant/interview-prep", json=payload).json()

    assert "数据分析" in rewrite["keywordEvidence"]
    assert rewrite["bulletSuggestions"]
    assert prep["questions"]
    assert prep["reverseQuestions"]


def test_followup_reminders_and_risk_explanation(monkeypatch):
    import app.routes.jobs as jobs_route
    from app.services import workflow_persistence as persistence

    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(id="job-1", title="产品经理", company="示例科技", application_status="greeted", application_updated_at="2026-07-20T00:00:00"),
        "job-2": JobRecord(id="job-2", title="运营", company="风险科技", application_status="interviewing", application_updated_at="2026-07-25T00:00:00"),
    })
    monkeypatch.setattr(persistence, "load_send_records", lambda: [{"jobId": "job-1", "status": "sent", "updatedAt": "2026-07-20T00:00:00"}])

    reminders = client.get("/api/assistant/followups").json()
    risk = client.post("/api/assistant/risk-explanation", json={
        "diligence": {
            "companyName": "风险科技",
            "riskLevel": "high",
            "businessInfo": {"abnormalInfo": ["列入经营异常"], "penalties": ["行政处罚"], "enforcedItems": ["被执行"]},
            "sentiment": {"negative": ["裁员"]},
        }
    }).json()

    assert reminders["reminders"]
    assert reminders["reminders"][0]["jobId"] == "job-1"
    assert risk["riskLevel"] == "high"
    assert risk["plainLanguage"]
    assert risk["questionsToAsk"]


def test_deep_report_includes_user_preferences(tmp_path, monkeypatch):
    from app.services import preferences

    monkeypatch.setattr(preferences, "PREFERENCES_FILE", tmp_path / "preferences.json")
    preferences.save_preferences({
        "stability": 90,
        "salary": 50,
        "growth": 80,
        "match": 85,
        "avoid_industries": ["教培"],
        "preferred_cities": ["上海"],
    })

    response = client.post("/api/assistant/deep-report", json={
        "job": {"id": "job-1", "title": "产品经理", "company": "示例科技", "city": "上海", "jd_text": "负责产品规划"},
        "resume": {"skills": ["产品规划"]},
        "diligence": {"companyName": "示例科技", "companyScore": 82, "riskLevel": "low"},
        "ranking": {"matchScore": 85, "compositeScore": 84},
    })

    assert response.status_code == 200
    body = response.json()
    assert body["preferences"]["stability"] == 90
    assert any("稳定性" in item for item in body["preferenceSignals"])


def test_onboarding_guide_counts_only_user_selected_jobs(monkeypatch):
    from app.routes import jobs as jobs_route
    from app.services import maintenance_service, workflow_persistence

    jobs_route._job_store.clear()
    jobs_route._job_store.update({
        "selected": JobRecord(id="selected", title="产品经理", company="已选公司", jd_text="完整的岗位职责", jd_detail_fetched_at="2026-08-01T00:00:00"),
        "unselected": JobRecord(id="unselected", title="运营", company="未选公司", jd_text=""),
    })
    monkeypatch.setattr(workflow_persistence, "load_selection", lambda: ["selected"])
    monkeypatch.setattr(workflow_persistence, "load_diligence_reports", lambda: {})
    monkeypatch.setattr(workflow_persistence, "load_rankings", lambda: [])
    guide = maintenance_service.onboarding_guide()
    statuses = {step["key"]: step["status"] for step in guide["steps"]}

    assert guide["scope"]["selectedJobs"] == 1
    assert statuses["capture_jobs"] == "done"
    assert statuses["complete_jd"] == "done"


def test_onboarding_does_not_treat_existing_jobs_as_completed_configuration(monkeypatch):
    from app.routes import jobs as jobs_route
    from app.services import maintenance_service, workflow_persistence

    jobs_route._job_store.clear()
    jobs_route._job_store["selected"] = JobRecord(id="selected", title="产品经理", company="已选公司", jd_text="完整 JD")
    monkeypatch.setattr(workflow_persistence, "load_selection", lambda: ["selected"])
    monkeypatch.setattr(workflow_persistence, "load_diligence_reports", lambda: {})
    monkeypatch.setattr(workflow_persistence, "load_rankings", lambda: [])
    monkeypatch.setattr(maintenance_service, "_configuration_ready", lambda: False)

    guide = maintenance_service.onboarding_guide()

    assert {step["key"]: step["status"] for step in guide["steps"]}["configure"] == "todo"


def test_dashboard_summary_uses_selected_jobs_for_readiness(monkeypatch):
    from app.routes import jobs as jobs_route
    from app.services import workflow_persistence

    jobs_route._job_store.clear()
    jobs_route._job_store.update({
        "selected": JobRecord(id="selected", title="产品经理", company="已选公司", jd_text="完整的岗位职责", jd_detail_fetched_at="2026-08-01T00:00:00"),
        "unselected": JobRecord(id="unselected", title="运营", company="未选公司", jd_text=""),
    })
    monkeypatch.setattr(workflow_persistence, "load_diligence_reports", lambda: {"已选公司": {"companyName": "已选公司"}})
    monkeypatch.setattr(workflow_persistence, "load_rankings", lambda: [{"jobId": "selected", "recommendation": "strong"}])

    body = client.get("/api/dashboard/summary?selected_job_ids=selected").json()

    assert body["jobs"]["total"] == 1
    assert body["jobs"]["missingJd"] == 0
    assert body["diligence"]["pendingCompanies"] == 0
    assert body["readiness"]["stage"] == "decision"


def test_dashboard_summary_excludes_blacklisted_companies_from_flow_guidance(monkeypatch):
    from app.routes import jobs as jobs_route
    from app.services import workflow_persistence

    jobs_route._job_store.clear()
    jobs_route._job_store.update({
        "available": JobRecord(id="available", title="产品经理", company="可用公司", jd_text="完整职责", jd_detail_fetched_at="2026-08-01T00:00:00"),
        "blacklisted": JobRecord(id="blacklisted", title="运营", company="黑名单公司", jd_text="", lifecycle_status="blacklisted"),
    })
    monkeypatch.setattr(workflow_persistence, "load_diligence_reports", lambda: {
        "可用公司": {"companyName": "可用公司"},
        "黑名单公司": {"companyName": "黑名单公司"},
    })
    monkeypatch.setattr(workflow_persistence, "load_rankings", lambda: [
        {"jobId": "available", "recommendation": "strong"},
        {"jobId": "blacklisted", "recommendation": "strong"},
    ])

    body = client.get("/api/dashboard/summary?selected_job_ids=available,blacklisted").json()

    assert body["jobs"]["total"] == 1
    assert body["jobs"]["missingJd"] == 0
    assert body["diligence"]["pendingCompanies"] == 0
    assert body["ranking"]["total"] == 1
    assert body["decisions"]["recommended"] == 0


def test_dashboard_summary_matches_diligence_report_source_company_name(monkeypatch):
    from app.routes import jobs as jobs_route
    from app.services import workflow_persistence

    jobs_route._job_store.clear()
    jobs_route._job_store["job-alias"] = JobRecord(
        id="job-alias",
        title="HRBP",
        company="金华市封哥塑料制品有限公司",
        jd_text="完整职责",
    )
    monkeypatch.setattr(workflow_persistence, "load_diligence_reports", lambda: {
        "宿迁封哥电子商务有限公司": {
            "companyName": "宿迁封哥电子商务有限公司",
            "sourceCompanyName": "金华市封哥塑料制品有限公司",
            "companyKey": "91331126322972590F",
        },
    })
    monkeypatch.setattr(workflow_persistence, "load_rankings", lambda: [])

    body = client.get("/api/dashboard/summary?selected_job_ids=job-alias").json()

    assert body["diligence"]["completedCompanies"] == 1
    assert body["diligence"]["pendingCompanies"] == 0


def test_dashboard_summary_with_no_selected_jobs_requests_selection(monkeypatch):
    from app.routes import jobs as jobs_route

    jobs_route._job_store.clear()
    jobs_route._job_store["available"] = JobRecord(id="available", title="产品经理", company="示例科技", jd_text="完整的岗位职责")

    body = client.get("/api/dashboard/summary?selected_job_ids=").json()

    assert body["jobs"]["total"] == 0
    assert body["readiness"]["stage"] == "select_jobs"


def test_prompt_versions_can_delete_one_record(tmp_path, monkeypatch):
    import app.routes.assistant as assistant_route
    from app.services.workflow_persistence import write_json_atomic

    versions_file = tmp_path / "prompt_versions.json"
    monkeypatch.setattr(assistant_route, "_prompt_versions_file", lambda: versions_file)
    write_json_atomic(versions_file, [
        {"id": "v-1", "kind": "deep_report", "jobId": "job-1"},
        {"id": "v-2", "kind": "deep_report", "jobId": "job-2"},
    ])

    response = client.delete("/api/assistant/prompt-versions/v-1")

    assert response.status_code == 200
    assert response.json()["deleted"] is True
    remaining = client.get("/api/assistant/prompt-versions").json()["versions"]
    assert [item["id"] for item in remaining] == ["v-2"]


def test_prompt_versions_can_clear_by_kind(tmp_path, monkeypatch):
    import app.routes.assistant as assistant_route
    from app.services.workflow_persistence import write_json_atomic

    versions_file = tmp_path / "prompt_versions.json"
    monkeypatch.setattr(assistant_route, "_prompt_versions_file", lambda: versions_file)
    write_json_atomic(versions_file, [
        {"id": "v-1", "kind": "deep_report", "jobId": "job-1"},
        {"id": "v-2", "kind": "resume", "jobId": "job-2"},
    ])

    response = client.delete("/api/assistant/prompt-versions?kind=deep_report")

    assert response.status_code == 200
    assert response.json()["deleted"] == 1
    remaining = client.get("/api/assistant/prompt-versions").json()["versions"]
    assert [item["id"] for item in remaining] == ["v-2"]


def test_prompt_versions_backfill_historical_ai_calls_when_no_records_exist(tmp_path, monkeypatch):
    import json

    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    log_path = tmp_path / "logs" / "api_calls.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps({
        "time": "2026-08-01T06:48:08+00:00",
        "category": "ai",
        "detail": {"model": "deepseek-v4-flash", "outcome": "success"},
    }) + "\n", encoding="utf-8")

    body = client.get("/api/assistant/prompt-versions").json()

    assert body["summary"]["total"] == 1
    assert body["versions"][0]["kind"] == "ai_historical"
    assert body["versions"][0]["promptVersion"] == "deepseek-v4-flash"


def test_clearing_prompt_versions_does_not_restore_historical_records(tmp_path, monkeypatch):
    import json

    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    log_path = tmp_path / "logs" / "api_calls.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps({
        "time": "2026-08-01T06:48:08+00:00",
        "category": "ai",
        "detail": {"model": "deepseek-v4-flash", "outcome": "success"},
    }) + "\n", encoding="utf-8")

    assert client.get("/api/assistant/prompt-versions").json()["summary"]["total"] == 1
    response = client.delete("/api/assistant/prompt-versions")

    assert response.status_code == 200
    assert response.json()["deleted"] == 1
    assert client.get("/api/assistant/prompt-versions").json()["summary"]["total"] == 0
