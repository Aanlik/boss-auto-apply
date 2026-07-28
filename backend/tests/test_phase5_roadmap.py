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
