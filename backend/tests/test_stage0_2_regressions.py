import importlib

from fastapi.testclient import TestClient

from app.models.job import JobSource
from app.routes.resumes import router as resumes_router
from app.main import app
from app.services.job_capture import jobs_from_source
from app.services.job_recognition import recognize_job
from app.services.resume_parser import _extract_text_from_bytes


def test_resume_profile_route_is_registered_once():
    matches = [
        route for route in resumes_router.routes
        if getattr(route, "path", "") == "/api/resumes/profile"
        and "PUT" in getattr(route, "methods", set())
    ]

    assert len(matches) == 1


def test_parse_resume_without_ai_persists_completed_status(tmp_path, monkeypatch):
    routes = importlib.import_module("app.routes.resumes")
    monkeypatch.setattr(routes, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(routes, "STORE_DIR", tmp_path / "resumes")
    routes.UPLOAD_DIR.mkdir()
    routes.STORE_DIR.mkdir()
    monkeypatch.setattr(routes, "_uploaded_files", [])
    monkeypatch.setattr(routes, "_active_file_id", "")

    import app.services.ai_client as ai_client
    monkeypatch.setattr(ai_client, "get_client", lambda: (_ for _ in ()).throw(RuntimeError("no key")))

    client = TestClient(app)
    response = client.post(
        "/api/resumes/parse",
        files={"file": ("resume.txt", "张三\nPython 后端工程师\n技能: Python, FastAPI".encode("utf-8"), "text/plain")},
    )

    assert response.status_code == 200
    assert response.json()["parse_status"] == "completed"
    assert client.get("/api/resumes/active").json()["parse_status"] == "completed"


def test_active_resume_ignores_legacy_entry_without_profile(tmp_path, monkeypatch):
    routes = importlib.import_module("app.routes.resumes")
    monkeypatch.setattr(routes, "STORE_DIR", tmp_path / "resumes")
    routes.STORE_DIR.mkdir()
    monkeypatch.setattr(routes, "_active_file_id", "legacy")
    (routes.STORE_DIR / "legacy.json").write_text('{"raw_text":"legacy text","parse_status":"completed"}')

    client = TestClient(app)
    response = client.get("/api/resumes/active")

    assert response.status_code == 200
    assert response.json()["profile"] is None
    assert response.json()["file_id"] == ""


def test_image_resume_uses_ocr_instead_of_utf8_garbage(monkeypatch):
    import app.services.ai_client as ai_client
    monkeypatch.setattr(ai_client, "ocr_image", lambda data, filename: "李四\n前端工程师\n技能: React")

    text = _extract_text_from_bytes(b"\x89PNG\r\n\x1a\nfake", "resume.png")

    assert "李四" in text
    assert "React" in text


def test_jobs_from_source_preserves_captured_tags_as_keywords():
    source = JobSource(
        source_type="captured",
        source_id="boss-1",
        raw_payload={
            "id": "boss-1",
            "title": "产品经理",
            "company": "示例科技",
            "city": "深圳",
            "salary": "20-30K",
            "jd_text": "负责 B 端产品规划",
            "tags": ["3-5年", "本科", "100-499人", "B轮"],
        },
        fetched_at="2026-07-26T00:00:00+00:00",
        dedupe_key="dedupe",
    )

    job = recognize_job(jobs_from_source(source))

    assert {"3-5年", "本科", "100-499人", "B轮"}.issubset(set(job.keywords))


def test_analyze_jd_persists_result_on_job_record(monkeypatch):
    import app.routes.jobs as jobs_route
    import app.routes.resumes as resumes_route
    from app.models.job import JobRecord
    from app.models.resume import JDAnalysis

    jobs_route._job_store.clear()
    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        jd_text="负责产品规划和跨部门项目推进",
    )
    monkeypatch.setattr(jobs_route, "_save_jobs", lambda: None)
    monkeypatch.setattr(
        resumes_route,
        "analyze_jd",
        lambda *args, **kwargs: JDAnalysis(
            must_have_skills=["产品规划"],
            summary_text="负责产品规划和项目推进",
        ),
    )

    client = TestClient(app)
    response = client.post("/api/resumes/analyze-jd", json={
        "job_id": "job-1",
        "title": "产品经理",
        "company": "示例科技",
        "jd_text": "负责产品规划和跨部门项目推进",
    })

    assert response.status_code == 200
    listed = client.get("/api/jobs/pool").json()["jobs"]
    saved = next(job for job in listed if job["id"] == "job-1")
    assert saved["jd_analysis"]["must_have_skills"] == ["产品规划"]
    assert saved["jd_analysis"]["summary_text"] == "负责产品规划和项目推进"


def test_optimize_resume_persists_result_by_job_id(tmp_path, monkeypatch):
    import app.routes.resumes as resumes_route
    from app.models.resume import ResumeOptimizationResult

    monkeypatch.setattr(resumes_route, "DATA_DIR", tmp_path)
    monkeypatch.setattr(resumes_route, "STORE_DIR", tmp_path / "resumes")
    resumes_route.STORE_DIR.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        resumes_route,
        "ai_optimize",
        lambda *args, **kwargs: ResumeOptimizationResult(
            summary="优化完成",
            tailored_summary="面向产品经理优化",
            optimized_bullets=["推动产品增长"],
            matched_skills=["产品规划"],
        ),
    )

    client = TestClient(app)
    response = client.post("/api/resumes/optimize", json={
        "profile": {"name": "张三", "skills": ["产品规划"]},
        "target_job": {
            "id": "job-1",
            "title": "产品经理",
            "company": "示例科技",
            "jd_text": "负责产品规划",
        },
    })

    assert response.status_code == 200
    saved = client.get("/api/resumes/optimizations").json()["optimizations"]
    assert saved["job-1"]["tailored_summary"] == "面向产品经理优化"
    assert saved["job-1"]["optimized_bullets"] == ["推动产品增长"]


def test_jobs_city_options_use_reference_city_catalog():
    client = TestClient(app)

    response = client.get("/api/jobs/cities")

    assert response.status_code == 200
    data = response.json()
    city_names = [city["name"] for city in data["cities"]]
    assert data["total"] >= 300
    assert city_names[:5] == ["全国", "北京", "上海", "广州", "深圳"]
    assert "郑州" in city_names
    assert "澳门" in city_names
    assert "阿克苏地区" in city_names


def test_city_code_resolver_supports_full_catalog_and_city_suffix():
    from app.services.city_codes import resolve_city_code

    assert resolve_city_code("") == "100010000"
    assert resolve_city_code("深圳市") == "101280600"
    assert resolve_city_code("阿克苏地区") == "101131000"


def test_jobs_filter_options_expose_boss_capture_filters():
    client = TestClient(app)

    response = client.get("/api/jobs/capture/boss/filter-options")

    assert response.status_code == 200
    data = response.json()
    assert {"label": "1000-9999人", "value": "305"} in data["scale"]
    assert {"label": "已上市", "value": "807"} in data["stage"]
    assert {"label": "20-50K", "value": "406"} in data["salary"]
    assert {"label": "3-5年", "value": "105"} in data["experience"]
    assert {"label": "本科", "value": "203"} in data["degree"]
    assert {"label": "互联网", "value": "1001"} in data["industry"]


def test_boss_capture_endpoint_passes_multi_dimension_filters(monkeypatch):
    import app.routes.jobs as jobs_route

    captured = {}

    def fake_ingest_from_boss(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(jobs_route, "ingest_from_boss", fake_ingest_from_boss)

    client = TestClient(app)
    response = client.post("/api/jobs/capture/boss", json={
        "keyword": "产品经理",
        "city": "郑州",
        "max_pages": 1,
        "filters": {
            "scale": "305",
            "stage": "807",
            "salary": "406",
            "experience": "105",
            "degree": "203",
            "industry": "1001",
        },
    })

    assert response.status_code == 200
    assert captured["filters"] == {
        "scale": "305",
        "stage": "807",
        "salary": "406",
        "experience": "105",
        "degree": "203",
        "industry": "1001",
    }


def test_boss_scraper_adds_filters_to_api_url(monkeypatch):
    import json
    import app.services.boss_scraper as scraper

    api_scripts = []
    closed = []

    class FakeCDP:
        def __init__(self, port):
            self.navigated = []

        def create_page(self):
            return "target-1", "session-1"

        def navigate(self, url, sid):
            self.navigated.append(url)

        def eval_js(self, js, sid):
            if "__PROBE_URL__" not in js and "pageSize=10" not in js:
                api_scripts.append(js)
                return json.dumps([])
            return json.dumps({
                "httpStatus": 200,
                "body": json.dumps({
                    "code": 0,
                    "zpData": {"jobList": [{"salaryDesc": "20-30K"}]},
                }),
            })

        def send(self, method, params=None, sid=None, timeout=30):
            return {}

        def close(self):
            pass

    monkeypatch.setattr(scraper, "_chrome_running", lambda: True)
    monkeypatch.setattr(scraper, "CDPSession", FakeCDP)
    monkeypatch.setattr(scraper, "_stop_chrome", lambda clear_session=False: closed.append(clear_session))

    scraper.scrape_jobs_sync(
        keyword="产品经理",
        city="郑州",
        max_pages=1,
        filters={
            "scale": "305",
            "stage": "807",
            "salary": "406",
            "experience": "105",
            "degree": "203",
            "industry": "1001",
        },
    )

    script = api_scripts[0]
    assert "scale=305" in script
    assert "stage=807" in script
    assert "salary=406" in script
    assert "experience=105" in script
    assert "degree=203" in script
    assert "industry=1001" in script
    assert closed == [False]


def test_boss_selector_health_closes_browser_after_check(monkeypatch):
    import json
    import app.services.boss_scraper as scraper

    closed = []

    class FakeCDP:
        def __init__(self, port):
            pass

        def create_page(self):
            return "target-1", "session-1"

        def navigate(self, url, sid):
            pass

        def eval_js(self, js, sid):
            if "pageSize=10" in js:
                return json.dumps({
                    "httpStatus": 200,
                    "body": json.dumps({"code": 0, "zpData": {"jobList": [{"salaryDesc": "20-30K"}]}}),
                })
            return json.dumps({"status": "ok", "checks": []})

        def send(self, method, params=None, sid=None, timeout=30):
            return {}

        def close(self):
            pass

    monkeypatch.setattr(scraper, "_chrome_running", lambda: True)
    monkeypatch.setattr(scraper, "CDPSession", FakeCDP)
    monkeypatch.setattr(scraper, "_stop_chrome", lambda clear_session=False: closed.append(clear_session))

    result = scraper.check_boss_greeting_selectors_sync("https://www.zhipin.com/job_detail/demo.html")

    assert result["status"] == "ok"
    assert closed == [False]


def test_company_blacklist_api_adds_and_removes_existing_jobs(tmp_path, monkeypatch):
    import app.routes.jobs as jobs_route
    from app.models.job import JobRecord
    from app.services import workflow_persistence as persistence

    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(id="job-1", title="HRBP", company="示例科技有限公司", city="郑州"),
        "job-2": JobRecord(id="job-2", title="产品经理", company="正常科技有限公司", city="郑州"),
    })

    client = TestClient(app)
    added = client.post("/api/jobs/company-blacklist", json={"company_name": "示例科技有限公司"})

    assert added.status_code == 200
    assert added.json()["removed"] == 1
    assert "job-1" in jobs_route._job_store
    assert jobs_route._job_store["job-1"].lifecycle_status == "blacklisted"
    assert "job-2" in jobs_route._job_store
    assert client.get("/api/jobs/pool").json()["total"] == 1

    listed = client.get("/api/jobs/company-blacklist")
    assert listed.json()["companies"][0]["name"] == "示例科技有限公司"

    deleted = client.request("DELETE", "/api/jobs/company-blacklist", json={"company_name": "示例科技有限公司"})
    assert deleted.status_code == 200
    assert deleted.json()["companies"] == []
    assert deleted.json()["restored"] == 1
    assert jobs_route._job_store["job-1"].lifecycle_status == "active"
    assert client.get("/api/jobs/pool").json()["total"] == 2


def test_boss_capture_dedupes_within_new_batch(monkeypatch):
    import app.routes.jobs as jobs_route
    from app.models.job import JobRecord

    monkeypatch.setattr(jobs_route, "_job_store", {})

    def fake_ingest_from_boss(**kwargs):
        return [
            JobRecord(id="job-1", title="产品经理", company="示例科技", city="郑州", dedupe_key="same-key"),
            JobRecord(id="job-2", title="产品经理", company="示例科技", city="郑州", dedupe_key="same-key"),
        ]

    monkeypatch.setattr(jobs_route, "ingest_from_boss", fake_ingest_from_boss)

    client = TestClient(app)
    response = client.post("/api/jobs/capture/boss", json={"keyword": "产品经理", "city": "郑州"})

    assert response.status_code == 200
    assert response.json()["captured"] == 1
    assert response.json()["removed_duplicates"] == 1
    assert list(jobs_route._job_store) == ["job-1"]
