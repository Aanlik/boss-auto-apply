from fastapi.testclient import TestClient

from app.main import app
from app.models.job import JobRecord


client = TestClient(app)


def test_system_health_check_reports_core_readiness():
    response = client.get("/api/workflow/health-check")

    assert response.status_code == 200
    body = response.json()
    keys = {item["key"] for item in body["checks"]}
    assert body["status"] in {"ok", "warn", "error"}
    assert {
        "runtime_mode",
        "python",
        "pnpm",
        "frontend_build",
        "data_dir",
        "ai_provider",
        "baidu_search",
        "business_api",
        "boss_login",
    }.issubset(keys)
    assert all(item["status"] in {"ok", "warn", "error"} for item in body["checks"])


def test_sample_capture_is_blocked_in_production(monkeypatch):
    monkeypatch.delenv("BOSS_WORKBENCH_MODE", raising=False)

    response = client.post("/api/jobs/capture")

    assert response.status_code == 403


def test_local_access_guard_blocks_non_local_hosts(monkeypatch):
    monkeypatch.delenv("BOSS_WORKBENCH_ALLOW_REMOTE", raising=False)

    response = client.get("/health", headers={"host": "192.168.1.9:8000"})

    assert response.status_code == 403


def test_failed_retryable_task_can_be_replayed_as_new_attempt(tmp_path, monkeypatch):
    from app.services import workflow_tasks

    monkeypatch.setattr(workflow_tasks, "TASKS_FILE", tmp_path / "tasks.json")
    task = workflow_tasks.start_task("unknown_retry", "未知任务", payload={"x": 1})
    workflow_tasks.fail_task(task["id"], "失败", "UNKNOWN", "人工处理", retryable=True)

    response = client.post(f"/api/workflow/tasks/{task['id']}/retry")

    assert response.status_code == 202
    body = response.json()
    assert body["task"]["status"] == "queued"
    assert body["task"]["payload"] == {"x": 1}
    assert body["sourceTask"]["id"] == task["id"]


def test_job_pool_export_and_batch_quality(monkeypatch):
    import app.routes.jobs as jobs_route

    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(
            id="job-1",
            title="产品经理",
            company="示例科技",
            city="上海",
            capture_batch_id="batch-1",
            capture_keyword="产品经理",
            capture_city="上海",
            capture_filters={"stage": "ipo"},
            captured_at="2026-07-27T00:00:00",
        )
    })

    quality = client.get("/api/jobs/pool/quality").json()
    exported_json = client.get("/api/jobs/export?format=json")
    exported_csv = client.get("/api/jobs/export?format=csv")

    assert quality["summary"]["batch_count"] == 1
    assert quality["batches"][0]["id"] == "batch-1"
    assert exported_json.status_code == 200
    assert exported_json.json()["jobs"][0]["capture_batch_id"] == "batch-1"
    assert exported_csv.status_code == 200
    assert "text/csv" in exported_csv.headers["content-type"]
    assert "产品经理" in exported_csv.text


def test_diligence_export_includes_evidence_summary(tmp_path, monkeypatch):
    from app.services import workflow_persistence as persistence

    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)
    persistence.save_diligence_report({
        "companyName": "示例科技",
        "companyScore": 72,
        "riskLevel": "medium",
        "businessInfo": {
            "companyName": "示例科技有限公司",
            "unifiedCreditCode": "91300000",
            "legalRepresentative": "张三",
            "registrationCapital": "100万",
            "establishedDate": "2020-01-01",
            "businessStatus": "存续",
            "industry": "软件服务",
            "abnormalInfo": [],
            "penalties": [],
        },
        "sentiment": {"evidenceLinks": ["https://example.com/news"], "positive": ["增长"], "negative": []},
        "industryOutlook": {"advantages": ["需求稳定"], "disadvantages": ["竞争激烈"], "risks": ["获客成本"]},
    })

    response = client.get("/api/diligence/export?format=json")

    assert response.status_code == 200
    report = response.json()["reports"][0]
    assert report["evidenceSummary"]["business"]
    assert report["evidenceSummary"]["searchLinks"] == ["https://example.com/news"]
    assert "需求稳定" in report["evidenceSummary"]["industryOpportunities"]


def test_ranking_templates_explanations_and_export(monkeypatch, tmp_path):
    import app.routes.jobs as jobs_route
    import app.services.scoring as scoring
    from app.services import workflow_persistence as persistence

    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(id="job-1", title="产品经理", company="示例科技", salary="20-30K", jd_text="负责产品规划")
    })

    async def fake_jd(job):
        return {"core_requirements": ["产品规划"], "hard_requirements": ["本科"], "key_responsibilities": ["规划"]}

    async def fake_match(resume, job, jd_analysis):
        return {
            "match_score": 80,
            "highlights": ["产品经验匹配"],
            "gaps": ["行业经验不足"],
            "recommendation": "recommend",
            "reason": "匹配度较高",
        }

    monkeypatch.setattr(scoring, "analyze_jd_for_matching", fake_jd)
    monkeypatch.setattr(scoring, "match_resume_to_job", fake_match)

    templates = client.get("/api/scoring/weights/templates")
    ranked = client.post("/api/scoring/rank", json={
        "job_ids": ["job-1"],
        "resume": {"skills": ["产品规划"]},
        "diligence_reports": {"示例科技": {"companyScore": 70, "riskLevel": "medium", "sentiment": {"negative": ["竞争"]}}},
        "weights": {"company_weight": 0.4, "match_weight": 0.6},
    })
    exported = client.get("/api/scoring/rankings/export?format=json")

    assert templates.status_code == 200
    assert "low_risk" in templates.json()["templates"]
    result = ranked.json()["rankings"][0]
    assert result["explanation"]["matchReasons"] == ["产品经验匹配"]
    assert result["explanation"]["resumeGaps"] == ["行业经验不足"]
    assert result["explanation"]["nextStep"]
    assert exported.status_code == 200
    assert exported.json()["rankings"][0]["jobId"] == "job-1"
