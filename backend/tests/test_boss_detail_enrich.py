import json

from fastapi.testclient import TestClient

from app.main import app
from app.models.job import JobRecord


def test_enrich_detail_replaces_company_name_instead_of_tagging(monkeypatch):
    import app.services.boss_scraper as scraper

    class FakeCDP:
        def __init__(self, port):
            self.closed_targets = []

        def create_page(self):
            return "target-1", "session-1"

        def navigate(self, url, sid):
            pass

        def eval_js(self, js, sid):
            return json.dumps({
                "jd": (
                    "岗位职责：负责组织发展体系建设，推动人才盘点和干部培养。"
                    "负责搭建组织诊断机制，协同业务负责人完成关键岗位梯队建设。"
                ),
                "jd_tags": [],
                "company_name": "示例科技有限公司",
            })

        def send(self, method, params=None, sid=None, timeout=30):
            if method == "Target.closeTarget":
                self.closed_targets.append(params["targetId"])
            return {}

        def close(self):
            pass

    monkeypatch.setattr(scraper, "_chrome_running", lambda: True)
    monkeypatch.setattr(scraper, "CDPSession", FakeCDP)
    monkeypatch.setattr(scraper._time, "sleep", lambda seconds: None)

    job = JobRecord(
        id="job-1",
        title="组织发展",
        company="示例科技",
        city="郑州",
        salary="10-15K",
        source_url="https://www.zhipin.com/job_detail/demo.html",
        jd_text="",
        keywords=[],
        tags=[],
    )

    assert scraper.enrich_jobs_with_details([job], max_jobs=1) == 1
    assert job.company == "示例科技有限公司"
    assert job.tags == []


def test_login_status_does_not_open_boss_page_during_detail_enrich(monkeypatch, tmp_path):
    import app.services.boss_scraper as scraper

    session_file = tmp_path / ".boss_logged_in"
    session_file.write_text("2026-07-26T00:00:00+00:00")

    class ForbiddenCDP:
        def __init__(self, port):
            raise AssertionError("CDP should not be opened while JD detail enrichment is running")

    monkeypatch.setattr(scraper, "CDP_PROFILE", str(tmp_path))
    monkeypatch.setattr(scraper, "_chrome_running", lambda: True)
    monkeypatch.setattr(scraper, "_detail_enrich_running", True)
    monkeypatch.setattr(scraper, "CDPSession", ForbiddenCDP)

    result = scraper.check_login_status()

    assert result["logged_in"] is True


def test_enrich_jd_hides_job_after_registered_company_hits_blacklist(monkeypatch, tmp_path):
    import app.routes.jobs as jobs_route
    import app.services.boss_scraper as scraper
    from app.models.job import JobRecord
    from app.services import workflow_persistence as persistence
    from app.services.company_blacklist import add_company_to_blacklist

    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)
    add_company_to_blacklist("示例科技有限公司")

    class FakeCDP:
        def __init__(self, port):
            pass

        def create_page(self):
            return "target-1", "session-1"

        def navigate(self, url, sid):
            pass

        def eval_js(self, js, sid):
            return json.dumps({
                "jd": "岗位职责：负责组织发展体系建设，推动人才盘点和干部培养。" * 3,
                "jd_tags": [],
                "company_name": "示例科技有限公司",
            })

        def send(self, method, params=None, sid=None, timeout=30):
            return {}

        def close(self):
            pass

    monkeypatch.setattr(scraper, "_chrome_running", lambda: True)
    monkeypatch.setattr(scraper, "CDPSession", FakeCDP)
    monkeypatch.setattr(scraper._time, "sleep", lambda seconds: None)
    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(
            id="job-1",
            title="组织发展",
            company="示例科技",
            city="郑州",
            source_url="https://www.zhipin.com/job_detail/demo.html",
        )
    })

    client = TestClient(app)
    response = client.post("/api/jobs/enrich-jd", json={"job_ids": ["job-1"], "max_jobs": 1})

    assert response.status_code == 200
    assert response.json()["removed_by_blacklist"] == 1
    assert "job-1" in jobs_route._job_store
    assert jobs_route._job_store["job-1"].company == "示例科技有限公司"
    assert jobs_route._job_store["job-1"].lifecycle_status == "blacklisted"
    assert client.get("/api/jobs/pool").json()["total"] == 0


def test_enrich_jd_recomputes_dedupe_key_and_removes_duplicates(monkeypatch, tmp_path):
    import app.routes.jobs as jobs_route
    import app.services.boss_scraper as scraper
    from app.models.job import JobRecord
    from app.services import workflow_persistence as persistence
    from app.services.job_capture import _make_dedupe_key

    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)

    class FakeCDP:
        def __init__(self, port):
            pass

        def create_page(self):
            return "target-1", "session-1"

        def navigate(self, url, sid):
            pass

        def eval_js(self, js, sid):
            return json.dumps({
                "jd": "岗位职责：负责产品规划、需求拆解和项目推进。" * 3,
                "jd_tags": [],
                "company_name": "示例科技有限公司",
            })

        def send(self, method, params=None, sid=None, timeout=30):
            return {}

        def close(self):
            pass

    existing_key = _make_dedupe_key("示例科技有限公司", "产品经理", "郑州")
    monkeypatch.setattr(scraper, "_chrome_running", lambda: True)
    monkeypatch.setattr(scraper, "CDPSession", FakeCDP)
    monkeypatch.setattr(scraper._time, "sleep", lambda seconds: None)
    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-existing": JobRecord(
            id="job-existing",
            title="产品经理",
            company="示例科技有限公司",
            city="郑州",
            dedupe_key=existing_key,
        ),
        "job-new": JobRecord(
            id="job-new",
            title="产品经理",
            company="示例科技",
            city="郑州",
            source_url="https://www.zhipin.com/job_detail/demo.html",
        ),
    })

    client = TestClient(app)
    response = client.post("/api/jobs/enrich-jd", json={"job_ids": ["job-new"], "max_jobs": 1})

    assert response.status_code == 200
    assert response.json()["removed_duplicates"] == 1
    assert list(jobs_route._job_store) == ["job-existing"]
