import json
import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.models.job import JobRecord


def test_stop_chrome_preserves_login_marker_by_default(monkeypatch, tmp_path):
    import app.services.boss_scraper as scraper

    session_file = tmp_path / ".boss_logged_in"
    session_file.write_text("2026-07-29T00:00:00+00:00")
    monkeypatch.setattr(scraper, "CDP_PROFILE", str(tmp_path))
    monkeypatch.setattr(scraper.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout=""))
    monkeypatch.setattr(scraper._time, "sleep", lambda seconds: None)

    scraper._stop_chrome()

    assert session_file.exists()
    scraper._stop_chrome(clear_session=True)
    assert not session_file.exists()


def test_stop_chrome_never_kills_an_unowned_process_on_the_cdp_port(monkeypatch, tmp_path):
    import app.services.boss_scraper as scraper

    pid_file = tmp_path / ".cdp_chrome.pid"
    pid_file.write_text("888")
    killed = []

    def fake_run(command, **kwargs):
        if command[0] == "lsof":
            return SimpleNamespace(stdout="777\n888\n")
        return SimpleNamespace(stdout=f"Google Chrome --remote-debugging-port={scraper.CDP_PORT} --user-data-dir={tmp_path}\n")

    monkeypatch.setattr(scraper, "CDP_PROFILE", str(tmp_path))
    monkeypatch.setattr(scraper.subprocess, "run", fake_run)
    monkeypatch.setattr(scraper.os, "kill", lambda pid, signal: killed.append(pid))
    monkeypatch.setattr(scraper._time, "sleep", lambda seconds: None)

    scraper._stop_chrome()

    assert killed == [888]


def test_launch_chrome_bypasses_a_broken_system_proxy(monkeypatch, tmp_path):
    import app.services.boss_scraper as scraper

    commands = []

    class FakeProcess:
        pid = 12345

    monkeypatch.setattr(scraper, "CDP_PROFILE", str(tmp_path / "profile"))
    monkeypatch.setattr(scraper, "_find_chrome", lambda: "/Applications/Chrome")
    monkeypatch.setattr(scraper, "_stop_chrome", lambda: None)
    monkeypatch.setattr(scraper, "_chrome_running", lambda: True)
    monkeypatch.setattr(scraper._time, "sleep", lambda seconds: None)
    monkeypatch.setattr(scraper.subprocess, "Popen", lambda command, **kwargs: commands.append(command) or FakeProcess())

    assert scraper._launch_chrome()
    assert "--no-proxy-server" in commands[0]


def test_boss_login_closes_browser_and_preserves_session_marker(monkeypatch, tmp_path):
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
            return json.dumps({
                "httpStatus": 200,
                "body": json.dumps({"code": 0, "zpData": {"jobList": [{"salaryDesc": "20-30K"}]}}),
            })

        def send(self, method, params=None, sid=None, timeout=30):
            return {}

        def close(self):
            pass

    async def fast_sleep(seconds):
        return None

    monkeypatch.setattr(scraper, "CDP_PROFILE", str(tmp_path))
    monkeypatch.setattr(scraper, "_chrome_running", lambda: False)
    monkeypatch.setattr(scraper, "_launch_chrome", lambda: True)
    monkeypatch.setattr(scraper, "_stop_chrome", lambda clear_session=False: closed.append(clear_session))
    monkeypatch.setattr(scraper, "CDPSession", FakeCDP)
    monkeypatch.setattr(asyncio, "sleep", fast_sleep)

    result = asyncio.run(scraper.boss_login_and_save_session())

    assert result["status"] == "ok"
    assert closed == [False]
    assert (tmp_path / ".boss_logged_in").exists()


def test_boss_login_status_route_only_probes_when_requested(monkeypatch):
    import app.services.boss_scraper as scraper

    called = {}

    def fake_check_login_status(*, probe=True):
      called["probe"] = probe
      return {"logged_in": False, "reason": "ok", "message": "未登录", "action": "请重新登录"}

    monkeypatch.setattr(scraper, "check_login_status", fake_check_login_status)

    client = TestClient(app)
    response = client.get("/api/jobs/capture/boss/status")

    assert response.status_code == 200
    assert called["probe"] is False
    assert response.json()["logged_in"] is False

    response = client.get("/api/jobs/capture/boss/status?probe=true")

    assert response.status_code == 200
    assert called["probe"] is True


def test_login_status_does_not_trust_stale_marker_when_chrome_is_closed(monkeypatch, tmp_path):
    import app.services.boss_scraper as scraper

    session_file = tmp_path / ".boss_logged_in"
    session_file.write_text("2026-07-29T00:00:00+00:00")
    stopped = []

    class FakeCDP:
        def __init__(self, port):
            pass

        def create_page(self):
            return "target-1", "session-1"

        def navigate(self, url, sid):
            pass

        def eval_js(self, js, sid):
            return json.dumps({
                "httpStatus": 200,
                "body": json.dumps({"code": 0, "zpData": {"jobList": []}}),
            })

        def send(self, method, params=None, sid=None, timeout=30):
            return {}

        def close(self):
            pass

    monkeypatch.setattr(scraper, "CDP_PROFILE", str(tmp_path))
    monkeypatch.setattr(scraper, "_chrome_running", lambda: False)
    monkeypatch.setattr(scraper, "_launch_chrome", lambda: True)
    monkeypatch.setattr(scraper, "_stop_chrome", lambda: stopped.append(True))
    monkeypatch.setattr(scraper, "CDPSession", FakeCDP)

    result = scraper.check_login_status()

    assert result["logged_in"] is False
    assert result["reason"] == "cookie_expired"
    assert not session_file.exists()
    assert stopped == [True]


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
    assert job.capture_company_name == "示例科技"
    assert job.tags == []


def test_enrich_detail_closes_browser_after_task(monkeypatch):
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
            if js.startswith("window.scrollBy"):
                return None
            return json.dumps({
                "jd": (
                    "岗位职责：负责产品规划、需求分析、跨团队协作和项目推进。"
                    "要求具备数据分析能力、业务理解能力和良好的沟通协作能力。"
                ),
                "jd_tags": ["产品规划"],
                "company_name": "",
            })

        def send(self, method, params=None, sid=None, timeout=30):
            return {}

        def close(self):
            pass

    monkeypatch.setattr(scraper, "_chrome_running", lambda: True)
    monkeypatch.setattr(scraper, "CDPSession", FakeCDP)
    monkeypatch.setattr(scraper._time, "sleep", lambda seconds: None)
    monkeypatch.setattr(scraper, "_stop_chrome", lambda: closed.append(True))

    job = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        source_url="https://www.zhipin.com/job_detail/demo.html",
    )

    assert scraper.enrich_jobs_with_details([job], max_jobs=1) == 1
    assert closed == [True]


def test_enrich_detail_keeps_browser_open_when_every_job_fails(monkeypatch):
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
            if js.startswith("window.scrollBy"):
                return None
            return json.dumps({"jd": "", "jd_tags": [], "company_name": ""})

        def send(self, method, params=None, sid=None, timeout=30):
            return {}

        def close(self):
            pass

    monkeypatch.setattr(scraper, "_chrome_running", lambda: True)
    monkeypatch.setattr(scraper, "CDPSession", FakeCDP)
    monkeypatch.setattr(scraper, "_stop_chrome", lambda: closed.append(True))
    monkeypatch.setattr(scraper._time, "sleep", lambda seconds: None)

    result = scraper.enrich_jobs_with_details(
        [JobRecord(id="job-1", title="产品经理", company="示例科技", source_url="https://www.zhipin.com/job_detail/demo.html")],
        max_jobs=1,
        preserve_browser_on_all_failures=True,
    )

    assert result == 0
    assert closed == []


def test_enrich_detail_recovers_once_after_cdp_connection_loss(monkeypatch):
    import app.services.boss_scraper as scraper

    launches = []
    progress = []
    attempts = []

    class FakeCDP:
        def __init__(self, port):
            pass

        def create_page(self):
            return "target-1", "session-1"

        def send(self, method, params=None, sid=None, timeout=30):
            return {}

        def close(self):
            pass

    def fake_detail(cdp, sid, source_url):
        attempts.append(source_url)
        if len(attempts) == 1:
            raise ConnectionError("CDP connection closed")
        return {
            "jd": "岗位职责：负责产品规划、需求分析和跨团队协作。" * 3,
            "jd_tags": [],
            "company_name": "",
        }

    monkeypatch.setattr(scraper, "_chrome_running", lambda: True)
    monkeypatch.setattr(scraper, "_launch_chrome", lambda: launches.append(True) or True)
    monkeypatch.setattr(scraper, "_stop_chrome", lambda clear_session=False: None)
    monkeypatch.setattr(scraper, "CDPSession", FakeCDP)
    monkeypatch.setattr(scraper, "scrape_job_detail", fake_detail)
    monkeypatch.setattr(scraper._time, "sleep", lambda seconds: None)

    job = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        source_url="https://www.zhipin.com/job_detail/demo.html",
    )

    result = scraper.enrich_jobs_with_details(
        [job],
        max_jobs=1,
        on_progress=lambda item, done, total, success, reason="": progress.append((item.id, done, total, success, reason)),
    )

    assert result == 1
    assert launches == [True]
    assert len(attempts) == 2
    assert progress == [("job-1", 1, 1, True, "")]


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


def test_enrich_jd_filters_existing_detail_jd_by_default(monkeypatch):
    import app.routes.jobs as jobs_route
    import app.services.boss_scraper as scraper

    seen_ids = []

    def fake_enrich(jobs, max_jobs=20, on_progress=None, preserve_browser_on_all_failures=False):
        seen_ids.extend(job.id for job in jobs)
        for job in jobs:
            job.jd_text = "新抓取的岗位职责内容" * 4
        return len(jobs)

    monkeypatch.setattr(scraper, "enrich_jobs_with_details", fake_enrich)
    monkeypatch.setattr(jobs_route, "_save_jobs", lambda: None)
    monkeypatch.setattr(jobs_route, "_dedupe_store", lambda: 0)
    monkeypatch.setattr(jobs_route, "_apply_blacklist_to_store", lambda: 0)
    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-with-jd": JobRecord(
            id="job-with-jd",
            title="产品经理",
            company="已有 JD",
            city="郑州",
            source_url="https://www.zhipin.com/job_detail/with.html",
            jd_text="已经存在的 JD",
            jd_detail_fetched_at="2026-07-29T00:00:00+00:00",
        ),
        "job-missing-jd": JobRecord(
            id="job-missing-jd",
            title="运营",
            company="缺少 JD",
            city="郑州",
            source_url="https://www.zhipin.com/job_detail/missing.html",
            jd_text="",
        ),
    })

    client = TestClient(app)
    response = client.post("/api/jobs/enrich-jd", json={
        "job_ids": ["job-with-jd", "job-missing-jd"],
        "max_jobs": 10,
    })

    assert response.status_code == 200
    assert seen_ids == ["job-missing-jd"]
    assert response.json()["skipped_existing_jd"] == 1


def test_enrich_jd_does_not_fallback_to_all_jobs_for_stale_selection(monkeypatch):
    import app.routes.jobs as jobs_route
    import app.services.boss_scraper as scraper

    def fail_if_called(*args, **kwargs):
        raise AssertionError("失效的岗位选择不应回退为全量抓取")

    monkeypatch.setattr(scraper, "enrich_jobs_with_details", fail_if_called)
    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(
            id="job-1",
            title="产品经理",
            company="正常公司",
            city="郑州",
            source_url="https://www.zhipin.com/job_detail/job-1.html",
        ),
    })

    client = TestClient(app)
    response = client.post("/api/jobs/enrich-jd", json={"job_ids": ["deleted-job"]})

    assert response.status_code == 400
    assert "选中的岗位已不存在" in response.json()["detail"]


def test_job_quality_excludes_blacklisted_jobs_from_jd_counts(monkeypatch):
    import app.routes.jobs as jobs_route

    monkeypatch.setattr(jobs_route, "is_company_blacklisted", lambda company: company == "黑名单公司")
    monkeypatch.setattr(jobs_route, "_job_store", {
        "blacklisted-missing": JobRecord(
            id="blacklisted-missing",
            title="黑名单岗位",
            company="黑名单公司",
            capture_batch_id="batch-a",
        ),
        "active-missing": JobRecord(
            id="active-missing",
            title="待补 JD 岗位",
            company="正常公司",
            capture_batch_id="batch-a",
        ),
        "active-with-jd": JobRecord(
            id="active-with-jd",
            title="已补 JD 岗位",
            company="正常公司",
            capture_batch_id="batch-b",
            jd_text="完整的岗位职责内容",
            jd_detail_fetched_at="2026-07-31T00:00:00+00:00",
        ),
    })

    quality = jobs_route._job_quality_report()

    assert quality["summary"]["total"] == 3
    assert quality["summary"]["blacklisted"] == 1
    assert quality["summary"]["with_jd"] == 1
    assert quality["summary"]["missing_jd"] == 1
    batch_a = next(batch for batch in quality["batches"] if batch["id"] == "batch-a")
    assert batch_a["missing_jd"] == 1


def test_job_quality_exposes_diligence_risk_and_revision_feedback_job_ids(monkeypatch):
    import app.routes.jobs as jobs_route
    from app.services import feedback_store, workflow_persistence

    monkeypatch.setattr(jobs_route, "is_company_blacklisted", lambda company: company == "黑名单公司")
    monkeypatch.setattr(jobs_route, "_job_store", {
        "risk-job": JobRecord(id="risk-job", title="风险岗位", company="展示公司"),
        "jd-quality-job": JobRecord(id="jd-quality-job", title="JD 待修改岗位", company="JD 公司"),
        "normal-job": JobRecord(id="normal-job", title="正常岗位", company="正常公司"),
        "blacklisted-risk-job": JobRecord(id="blacklisted-risk-job", title="隐藏风险岗位", company="黑名单公司"),
    })
    monkeypatch.setattr(workflow_persistence, "load_diligence_reports", lambda: {
        "分析公司": {
            "companyName": "分析公司",
            "sourceCompanyName": "展示公司",
            "companyKey": "company-key",
            "riskLevel": "high",
        },
        "黑名单公司": {
            "companyName": "黑名单公司",
            "riskLevel": "high",
        },
    })
    monkeypatch.setattr(feedback_store, "list_feedback", lambda domain="", target_id="": [
        {"domain": "diligence", "targetId": "company-key", "useful": False},
        {"domain": "jd_quality", "targetId": "jd-quality-job", "useful": False},
        {"domain": "ranking", "targetId": "deleted-job", "useful": False},
    ])

    quality = jobs_route._job_quality_report()

    assert quality["summary"]["risk_jobs"] == 1
    assert quality["summary"]["ai_feedback_needs_revision"] == 2
    assert quality["diligence"]["riskJobIds"] == ["risk-job"]
    assert quality["diligence"]["aiFeedbackNeedsRevisionJobIds"] == ["risk-job", "jd-quality-job"]


def test_delete_capture_batch_removes_only_its_jobs_and_workflow_references(monkeypatch):
    import app.routes.jobs as jobs_route
    from app.services import workflow_persistence

    jobs_route._job_store = {
        "batch-a-1": JobRecord(id="batch-a-1", title="A1", company="公司 A", capture_batch_id="capture-a"),
        "batch-a-2": JobRecord(id="batch-a-2", title="A2", company="公司 A", capture_batch_id="capture-a"),
        "batch-b-1": JobRecord(id="batch-b-1", title="B1", company="公司 B", capture_batch_id="capture-b"),
    }
    archived: list[str] = []
    saved = {"jobs": 0, "selection": None, "greeting": None, "rankings": None, "drafts": None}
    monkeypatch.setattr(jobs_route, "_archive_jobs", lambda ids: archived.extend(ids))
    monkeypatch.setattr(jobs_route, "_save_jobs", lambda: saved.__setitem__("jobs", saved["jobs"] + 1))
    monkeypatch.setattr(jobs_route, "log_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(workflow_persistence, "load_selection", lambda: ["batch-a-1", "batch-b-1"])
    monkeypatch.setattr(workflow_persistence, "save_selection", lambda ids: saved.__setitem__("selection", ids) or ids)
    monkeypatch.setattr(workflow_persistence, "load_greeting_selection", lambda: ["batch-a-2", "batch-b-1"])
    monkeypatch.setattr(workflow_persistence, "save_greeting_selection", lambda ids: saved.__setitem__("greeting", ids) or ids)
    monkeypatch.setattr(workflow_persistence, "load_rankings", lambda: [{"jobId": "batch-a-1"}, {"jobId": "batch-b-1"}])
    monkeypatch.setattr(workflow_persistence, "save_rankings", lambda rows: saved.__setitem__("rankings", rows) or rows)
    monkeypatch.setattr(workflow_persistence, "load_greetings", lambda: {"batch-a-1": "A", "batch-b-1": "B"})
    monkeypatch.setattr(workflow_persistence, "save_greetings", lambda rows: saved.__setitem__("drafts", rows) or rows)

    response = TestClient(app).delete("/api/jobs/capture-batches/capture-a")

    assert response.status_code == 200
    assert response.json() == {"batchId": "capture-a", "deleted": 2, "deletedJobIds": ["batch-a-1", "batch-a-2"], "total": 1}
    assert set(jobs_route._job_store) == {"batch-b-1"}
    assert archived == ["batch-a-1", "batch-a-2"]
    assert saved == {
        "jobs": 1,
        "selection": ["batch-b-1"],
        "greeting": ["batch-b-1"],
        "rankings": [{"jobId": "batch-b-1"}],
        "drafts": {"batch-b-1": "B"},
    }


def test_data_quality_uses_selected_non_blacklisted_jobs(monkeypatch):
    import app.routes.jobs as jobs_route
    from app.services import maintenance_service

    monkeypatch.setattr(jobs_route, "_job_store", {
        "selected": JobRecord(id="selected", title="已选", company="正常公司", jd_text="完整 JD", jd_detail_fetched_at="2026-08-01T00:00:00"),
        "unselected": JobRecord(id="unselected", title="未选", company="正常公司"),
        "blacklisted": JobRecord(id="blacklisted", title="黑名单", company="黑名单公司", lifecycle_status="blacklisted"),
    })
    monkeypatch.setattr(maintenance_service.workflow_persistence, "load_rankings", lambda: [{"jobId": "selected"}])

    quality = maintenance_service.data_quality_center(["selected", "blacklisted"])

    assert quality["summary"]["totalJobs"] == 1
    assert next(check for check in quality["checks"] if check["key"] == "missing_jd")["count"] == 0


def test_enrich_jd_processes_all_explicitly_selected_jobs(monkeypatch, tmp_path):
    import app.routes.jobs as jobs_route
    import app.services.boss_scraper as scraper
    from app.services import workflow_persistence, workflow_tasks

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(workflow_tasks, "TASKS_FILE", tmp_path / "workflow" / "tasks.json")
    selected = {
        f"job-{index}": JobRecord(
            id=f"job-{index}",
            title="岗位",
            company="公司",
            source_url=f"https://www.zhipin.com/job_detail/{index}.html",
        )
        for index in range(41)
    }
    seen = {}

    def fake_enrich(jobs, max_jobs=20, on_progress=None, preserve_browser_on_all_failures=False):
        seen["max_jobs"] = max_jobs
        for index, job in enumerate(jobs, start=1):
            job.jd_text = "详情页岗位职责内容" * 8
            job.jd_detail_fetched_at = "2026-07-31T00:00:00+00:00"
            if on_progress:
                on_progress(job, index, len(jobs), True)
        return len(jobs)

    monkeypatch.setattr(scraper, "enrich_jobs_with_details", fake_enrich)
    monkeypatch.setattr(jobs_route, "_save_jobs", lambda: None)
    monkeypatch.setattr(jobs_route, "_dedupe_store", lambda: 0)
    monkeypatch.setattr(jobs_route, "_apply_blacklist_to_store", lambda: 0)
    monkeypatch.setattr(jobs_route, "_job_store", selected)

    response = TestClient(app).post("/api/jobs/enrich-jd", json={
        "job_ids": list(selected),
    })

    assert response.status_code == 200
    assert seen["max_jobs"] == 41
    assert response.json()["enriched"] == 41


def test_enrich_jd_does_not_treat_capture_summary_as_detail_jd(monkeypatch):
    import app.routes.jobs as jobs_route
    import app.services.boss_scraper as scraper

    seen_ids = []

    def fake_enrich(jobs, max_jobs=20, on_progress=None, preserve_browser_on_all_failures=False):
        seen_ids.extend(job.id for job in jobs)
        for job in jobs:
            job.jd_text = "详情页重新抓取后的岗位职责内容" * 4
            job.jd_detail_fetched_at = "2026-07-29T00:00:00+00:00"
        return len(jobs)

    monkeypatch.setattr(scraper, "enrich_jobs_with_details", fake_enrich)
    monkeypatch.setattr(jobs_route, "_save_jobs", lambda: None)
    monkeypatch.setattr(jobs_route, "_dedupe_store", lambda: 0)
    monkeypatch.setattr(jobs_route, "_apply_blacklist_to_store", lambda: 0)
    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-summary-only": JobRecord(
            id="job-summary-only",
            title="产品经理",
            company="短摘要 JD",
            city="郑州",
            source_url="https://www.zhipin.com/job_detail/summary.html",
            jd_text="标签 | 技能 | 福利",
        ),
    })

    client = TestClient(app)
    response = client.post("/api/jobs/enrich-jd", json={
        "job_ids": ["job-summary-only"],
        "max_jobs": 10,
    })

    assert response.status_code == 200
    assert seen_ids == ["job-summary-only"]
    assert response.json()["skipped_existing_jd"] == 0


def test_enrich_jd_persists_and_updates_task_after_each_success(monkeypatch):
    import app.routes.jobs as jobs_route
    import app.services.boss_scraper as scraper

    saves = []
    updates = []

    def fake_enrich(jobs, max_jobs=20, on_progress=None, preserve_browser_on_all_failures=False):
        job = jobs[0]
        job.jd_text = "详情页岗位职责内容" * 8
        job.jd_detail_fetched_at = "2026-07-31T00:00:00+00:00"
        if on_progress:
            on_progress(job, 1, 1, True)
        return 1

    monkeypatch.setattr(scraper, "enrich_jobs_with_details", fake_enrich)
    monkeypatch.setattr(jobs_route, "_save_jobs", lambda: saves.append(True))
    monkeypatch.setattr(jobs_route, "_dedupe_store", lambda: 0)
    monkeypatch.setattr(jobs_route, "_apply_blacklist_to_store", lambda: 0)
    monkeypatch.setattr(jobs_route, "start_task", lambda *args, **kwargs: {"id": "task-1"})
    monkeypatch.setattr(jobs_route, "update_task", lambda task_id, **updates_: updates.append((task_id, updates_)))
    monkeypatch.setattr(jobs_route, "complete_task", lambda *args, **kwargs: None)
    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(
            id="job-1",
            title="产品经理",
            company="示例科技",
            city="郑州",
            source_url="https://www.zhipin.com/job_detail/demo.html",
        ),
    })

    client = TestClient(app)
    response = client.post("/api/jobs/enrich-jd", json={"job_ids": ["job-1"], "max_jobs": 1})

    assert response.status_code == 200
    assert saves
    assert updates == [("task-1", {
        "done": 1,
        "message": "正在获取 JD：示例科技 · 产品经理（1/1）",
        "payload": {"job_ids": ["job-1"], "max_jobs": 1, "force": False, "failed_job_ids": [], "failed_jobs": []},
    })]


def test_enrich_jd_marks_task_failed_when_every_detail_extraction_fails(monkeypatch):
    import app.routes.jobs as jobs_route
    import app.services.boss_scraper as scraper

    failed = []
    partial = []

    def fake_enrich(jobs, max_jobs=20, on_progress=None, preserve_browser_on_all_failures=False):
        if on_progress:
            on_progress(jobs[0], 1, 1, False, "BOSS 页面显示登录二维码")
        return 0

    monkeypatch.setattr(scraper, "enrich_jobs_with_details", fake_enrich)
    monkeypatch.setattr(jobs_route, "_save_jobs", lambda: None)
    monkeypatch.setattr(jobs_route, "_dedupe_store", lambda: 0)
    monkeypatch.setattr(jobs_route, "_apply_blacklist_to_store", lambda: 0)
    monkeypatch.setattr(jobs_route, "start_task", lambda *args, **kwargs: {"id": "task-1"})
    monkeypatch.setattr(jobs_route, "update_task", lambda *args, **kwargs: None)
    monkeypatch.setattr(jobs_route, "fail_task", lambda *args, **kwargs: failed.append((args, kwargs)))
    monkeypatch.setattr(jobs_route, "partial_fail_task", lambda *args, **kwargs: partial.append((args, kwargs)))
    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(
            id="job-1",
            title="产品经理",
            company="示例科技",
            city="郑州",
            source_url="https://www.zhipin.com/job_detail/demo.html",
        ),
    })

    client = TestClient(app)
    response = client.post("/api/jobs/enrich-jd", json={"job_ids": ["job-1"], "max_jobs": 1})

    assert response.status_code == 200
    assert partial == []
    assert failed == [(("task-1", "JD 详情抓取失败，0/1 成功；BOSS 页面显示登录二维码", "JD_ALL_FAILED", "检查保留的 BOSS 页面，完成登录或风控处理后重试"), {})]


def test_enrich_jd_force_refresh_includes_existing_jd(monkeypatch):
    import app.routes.jobs as jobs_route
    import app.services.boss_scraper as scraper

    seen_ids = []

    def fake_enrich(jobs, max_jobs=20, on_progress=None, preserve_browser_on_all_failures=False):
        seen_ids.extend(job.id for job in jobs)
        for job in jobs:
            job.jd_text = "重新抓取后的岗位职责内容" * 4
        return len(jobs)

    monkeypatch.setattr(scraper, "enrich_jobs_with_details", fake_enrich)
    monkeypatch.setattr(jobs_route, "_save_jobs", lambda: None)
    monkeypatch.setattr(jobs_route, "_dedupe_store", lambda: 0)
    monkeypatch.setattr(jobs_route, "_apply_blacklist_to_store", lambda: 0)
    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-with-jd": JobRecord(
            id="job-with-jd",
            title="产品经理",
            company="已有 JD",
            city="郑州",
            source_url="https://www.zhipin.com/job_detail/with.html",
            jd_text="已经存在的 JD",
            jd_detail_fetched_at="2026-07-29T00:00:00+00:00",
        ),
        "job-missing-jd": JobRecord(
            id="job-missing-jd",
            title="运营",
            company="缺少 JD",
            city="郑州",
            source_url="https://www.zhipin.com/job_detail/missing.html",
            jd_text="",
        ),
    })

    client = TestClient(app)
    response = client.post("/api/jobs/enrich-jd", json={
        "job_ids": ["job-with-jd", "job-missing-jd"],
        "max_jobs": 10,
        "force": True,
    })

    assert response.status_code == 200
    assert seen_ids == ["job-with-jd", "job-missing-jd"]
    assert response.json()["skipped_existing_jd"] == 0


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
