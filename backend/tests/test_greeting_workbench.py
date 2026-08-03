from __future__ import annotations

import pytest

from fastapi.testclient import TestClient

from app.main import app
from app.models.job import JobRecord


client = TestClient(app)


@pytest.fixture(autouse=True)
def _allow_boss_login_for_greeting_route_tests(monkeypatch):
    """Greeting route tests exercise send logic, not live BOSS authentication."""
    from app.routes import greetings as greeting_route

    monkeypatch.setattr(greeting_route, "check_boss_login_status", lambda **_: {
        "logged_in": True, "message": "已登录", "action": "",
    })


def _prepare_greeting_test_state(tmp_path, monkeypatch):
    from app.routes import jobs as jobs_route
    from app.services import company_blacklist, workflow_persistence, workflow_tasks

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(company_blacklist, "BLACKLIST_FILE", tmp_path / "jobs" / "company_blacklist.json")
    monkeypatch.setattr(jobs_route, "JOBS_FILE", tmp_path / "jobs" / "jobs.json")
    monkeypatch.setattr(workflow_tasks, "TASKS_FILE", tmp_path / "workflow" / "tasks.json")
    jobs_route._job_store.clear()
    return jobs_route


def _enable_auto_send():
    client.post("/api/greetings/auto-send-settings", json={"auto_send_enabled": True, "gray_mode_enabled": False})


def test_greeting_candidates_filter_blacklist_duplicates_and_missing_jd(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.services.company_blacklist import add_company_to_blacklist
    from app.services.workflow_persistence import save_send_record

    add_company_to_blacklist("风险科技")
    save_send_record("already", "sent", "之前已沟通")
    jobs_route._job_store.update({
        "ok": JobRecord(id="ok", title="产品经理", company="示例科技", city="上海", jd_text="负责产品规划和用户研究", source_url="https://example.com/job/ok"),
        "black": JobRecord(id="black", title="产品经理", company="风险科技", city="上海", jd_text="负责产品规划", source_url="https://example.com/job/black"),
        "already": JobRecord(id="already", title="后端开发", company="老公司", city="上海", jd_text="负责后端开发", source_url="https://example.com/job/already"),
        "missing": JobRecord(id="missing", title="运营", company="空 JD", city="上海", jd_text="", source_url="https://example.com/job/missing"),
    })

    body = client.post("/api/greetings/candidates", json={"job_ids": ["ok", "black", "already", "missing"]}).json()

    assert [item["jobId"] for item in body["candidates"]] == ["ok"]
    skipped = {item["jobId"]: item["reason"] for item in body["skipped"]}
    assert skipped["black"] == "blacklisted_company"
    assert skipped["already"] == "already_contacted"
    assert skipped["missing"] == "missing_jd"


def test_greeting_safety_summary_blocks_automatic_sending_when_boss_is_not_logged_in(tmp_path, monkeypatch):
    _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.routes import greetings as greeting_route

    monkeypatch.setattr(greeting_route, "check_boss_login_status", lambda **_: {
        "logged_in": False,
        "message": "未登录",
        "action": "验证 BOSS 登录",
    })

    summary = greeting_route.greeting_safety_summary()

    assert summary["status"] == "blocked"
    assert next(item for item in summary["checks"] if item["key"] == "boss_login") == {
        "key": "boss_login",
        "status": "error",
        "message": "未登录",
        "action": "验证 BOSS 登录",
    }


def test_greeting_safety_summary_reads_login_status_without_active_browser_probe(tmp_path, monkeypatch):
    """Opening any module must not launch BOSS merely to render safety status."""
    _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.routes import greetings as greeting_route

    probes: list[bool] = []

    def passive_login_status(*, probe: bool) -> dict:
        probes.append(probe)
        return {"logged_in": True, "message": "已登录", "action": ""}

    monkeypatch.setattr(greeting_route, "check_boss_login_status", passive_login_status)

    summary = greeting_route.greeting_safety_summary()

    assert probes == [False]
    assert next(item for item in summary["checks"] if item["key"] == "boss_login")["status"] == "ok"


def test_greeting_safety_summary_uses_the_saved_frequency_profile_limit(tmp_path, monkeypatch):
    _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.routes import greetings as greeting_route
    from app.services.workflow_persistence import save_send_record

    greeting_route._save_settings({"auto_send_enabled": True, "profile": "conservative"})
    for index in range(10):
        save_send_record(f"job-{index}", "sent", "已发送", dry_run=False)

    summary = greeting_route.greeting_safety_summary()

    assert summary["status"] == "blocked"
    assert summary["summary"]["dailyLimit"] == 10
    assert summary["summary"]["remaining"] == 0
    assert next(item for item in summary["checks"] if item["key"] == "daily_limit")["status"] == "error"


def test_final_confirmation_reports_the_actual_login_block_reason(tmp_path, monkeypatch):
    _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.routes import greetings as greeting_route

    monkeypatch.setattr(greeting_route, "check_boss_login_status", lambda **_: {
        "logged_in": False,
        "message": "登录已过期",
        "action": "重新登录 BOSS 直聘",
    })

    response = client.post("/api/greetings/final-confirmation", json={
        "job_ids": [],
        "messages": {},
        "mode": "browser_auto",
        "daily_limit": 15,
    })

    assert response.status_code == 200
    assert response.json()["riskItems"] == ["BOSS 登录校验未通过：登录已过期。重新登录 BOSS 直聘"]


def test_final_confirmation_keeps_the_daily_quota_block_reason(tmp_path, monkeypatch):
    _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.routes import greetings as greeting_route
    from app.services.workflow_persistence import save_send_record

    greeting_route._save_settings({"auto_send_enabled": True, "profile": "conservative"})
    for index in range(10):
        save_send_record(f"job-{index}", "sent", "已发送", dry_run=False)

    response = client.post("/api/greetings/final-confirmation", json={
        "job_ids": [],
        "messages": {},
        "mode": "browser_auto",
        "daily_limit": 10,
    })

    assert response.status_code == 200
    assert response.json()["riskItems"] == ["今日发送额度已用完（10/10），请明日再发送或调整发送上限"]


def test_partial_auto_send_setting_update_preserves_existing_safety_settings(tmp_path, monkeypatch):
    _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.routes import greetings as greeting_route

    greeting_route._save_settings({
        "auto_send_enabled": True,
        "profile": "conservative",
        "gray_mode_enabled": True,
    })

    response = client.post("/api/greetings/auto-send-settings", json={"daily_limit": 12})

    assert response.status_code == 200
    assert response.json()["settings"] == {
        "auto_send_enabled": True,
        "profile": "conservative",
        "gray_mode_enabled": True,
        "gray_first_success_required": True,
        "daily_limit": 12,
        "send_interval_seconds": 20,
        "updatedAt": response.json()["settings"]["updatedAt"],
    }


def test_browser_auto_send_cannot_override_the_saved_daily_limit(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.routes import greetings as greeting_route
    from app.services.workflow_persistence import save_send_record

    greeting_route._save_settings({
        "auto_send_enabled": True,
        "profile": "conservative",
        "gray_mode_enabled": False,
    })
    for index in range(10):
        save_send_record(f"sent-{index}", "sent", "已发送", dry_run=False)
    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        city="上海",
        jd_text="负责产品规划",
        source_url="https://example.com/job/1",
    )
    monkeypatch.setattr(greeting_route, "execute_browser_greeting", lambda job, message: {"ok": True, "status": "sent", "message": "不应发送"})

    response = client.post("/api/greetings/send", json={
        "job_ids": ["job-1"],
        "messages": {"job-1": "您好，我对贵司的产品经理岗位很感兴趣，过往有需求分析经验，希望有机会进一步沟通。"},
        "confirm": True,
        "mode": "browser_auto",
        "daily_limit": 100,
        "send_interval_seconds": 3,
    })

    assert response.status_code == 200
    assert response.json()["summary"]["dailyLimit"] == 10
    assert response.json()["summary"]["sent"] == 0
    assert response.json()["skipped"][0]["reason"] == "rate_limited"


def test_greeting_validation_blocks_ai_error_and_template_variables():
    body = client.post("/api/greetings/validate", json={
        "items": [
            {"job_id": "bad-ai", "message": "As an AI，我不能完成这个请求"},
            {"job_id": "template", "message": "您好，我对贵司的 {{job}} 岗位非常感兴趣，希望沟通。"},
            {"job_id": "ok", "message": "您好，我对贵司的产品经理岗位很感兴趣，过往有用户研究和需求梳理经验，希望有机会进一步沟通。"},
        ]
    }).json()

    results = {item["jobId"]: item for item in body["results"]}
    assert results["bad-ai"]["ok"] is False
    assert "blacklist:As an AI" in results["bad-ai"]["reasons"]
    assert results["template"]["ok"] is False
    assert "unresolved_template_variable" in results["template"]["reasons"]
    assert results["ok"]["ok"] is True


def test_greeting_generation_uses_job_jd_and_resume_context(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.services import greeting_workbench

    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        city="上海",
        jd_text="负责用户研究、需求分析和产品规划",
        source_url="https://example.com/job/1",
    )
    captured = {}

    def fake_chat_json(system, user, **kwargs):
        captured["system"] = system
        captured["user"] = user
        return {"message": "您好，我有用户研究和产品规划经验，希望和您进一步交流。"}

    monkeypatch.setattr(greeting_workbench, "chat_json", fake_chat_json)
    response = client.post("/api/greetings/generate", json={
        "job_id": "job-1",
        "resume": {"name": "张三", "skills": ["用户研究", "需求分析"], "work_experience": [{"company": "甲公司", "description": "负责产品规划"}]},
        "jd_analysis": {"must_have_skills": ["用户研究", "需求分析"]},
        "style": "稳妥自然",
    })

    assert response.status_code == 200
    assert response.json()["message"].startswith("您好")
    assert "负责用户研究、需求分析和产品规划" in captured["user"]
    assert "需求分析" in captured["user"]
    assert "甲公司" in captured["user"]


def test_greeting_generation_uses_plain_text_ai_mode(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.services import greeting_workbench

    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        city="上海",
        jd_text="负责用户研究、需求分析和产品规划",
        source_url="https://example.com/job/1",
    )
    captured = {}

    def fake_chat_json(system, user, **kwargs):
        captured.update(kwargs)
        return {"raw": "您好，我有用户研究和产品规划经验，希望和您进一步交流。"}

    monkeypatch.setattr(greeting_workbench, "chat_json", fake_chat_json)
    response = client.post("/api/greetings/generate", json={"job_id": "job-1", "resume": {"summary": "用户研究"}})

    assert response.status_code == 200
    assert response.json()["source"] == "ai"
    assert captured["expect_json"] is False


def test_greeting_generation_falls_back_when_ai_response_has_no_message(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.services import greeting_workbench

    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        city="上海",
        jd_text="负责用户研究、需求分析和产品规划",
        source_url="https://example.com/job/1",
    )
    monkeypatch.setattr(greeting_workbench, "chat_json", lambda *args, **kwargs: {"error": "AI 返回格式异常"})

    response = client.post("/api/greetings/generate", json={
        "job_id": "job-1",
        "resume": {"summary": "用户研究和产品规划"},
    })

    assert response.status_code == 200
    assert response.json()["source"] == "fallback"
    assert len(response.json()["message"]) >= 20


def test_greeting_send_requires_confirmation_and_blocks_invalid_message(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        city="上海",
        jd_text="负责产品规划",
        source_url="https://example.com/job/1",
    )

    no_confirm = client.post("/api/greetings/send", json={
        "job_ids": ["job-1"],
        "messages": {"job-1": "您好，我对贵司的产品经理岗位很感兴趣，希望进一步沟通。"},
        "confirm": False,
    })
    invalid = client.post("/api/greetings/send", json={
        "job_ids": ["job-1"],
        "messages": {"job-1": "As an AI，我不能发送"},
        "confirm": True,
    }).json()

    assert no_confirm.status_code == 400
    assert invalid["summary"]["sent"] == 0
    assert invalid["records"][0]["status"] == "failed"
    assert jobs_route._job_store["job-1"].application_status == "pending"


def test_greeting_send_marks_jobs_and_application_timeline(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.services import workflow_tasks

    monkeypatch.setattr(workflow_tasks, "TASKS_FILE", tmp_path / "workflow" / "tasks.json")
    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        city="上海",
        jd_text="负责产品规划",
        source_url="https://example.com/job/1",
    )

    body = client.post("/api/greetings/send", json={
        "job_ids": ["job-1"],
        "messages": {"job-1": "您好，我对贵司的产品经理岗位很感兴趣，过往有需求分析经验，希望有机会进一步沟通。"},
        "confirm": True,
        "mode": "manual_confirm",
    }).json()

    assert body["summary"]["sent"] == 1
    assert body["records"][0]["status"] == "sent"
    assert jobs_route._job_store["job-1"].greeted is True
    assert jobs_route._job_store["job-1"].application_status == "greeted"
    assert jobs_route._job_store["job-1"].status_history[-1]["kind"] == "application"

    timeline = client.get("/api/jobs/application-timeline").json()
    assert timeline["events"][0]["jobId"] == "job-1"
    assert timeline["events"][0]["status"] == "greeted"
    tasks = workflow_tasks.load_tasks(limit=5)
    assert tasks[0]["type"] == "greeting_send"
    assert tasks[0]["status"] == "completed"


def test_greeting_acceptance_records_are_persisted(tmp_path, monkeypatch):
    _prepare_greeting_test_state(tmp_path, monkeypatch)

    response = client.post("/api/greetings/acceptance-records", json={
        "job_id": "job-1",
        "result": "passed",
        "operator": "测试人员",
        "note": "真实页面已人工确认",
        "checks": [
            {"key": "open_job", "status": "passed", "note": "页面打开"},
            {"key": "confirm_send", "status": "passed", "note": "已点击发送"},
        ],
    })
    listed = client.get("/api/greetings/acceptance-records").json()

    assert response.status_code == 200
    assert response.json()["record"]["result"] == "passed"
    assert listed["summary"]["total"] == 1
    assert listed["records"][0]["operator"] == "测试人员"


def test_greeting_reply_records_drive_followup_summary(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        city="上海",
        jd_text="负责产品规划",
        source_url="https://example.com/job/1",
    )

    response = client.post("/api/greetings/replies", json={
        "job_id": "job-1",
        "reply_type": "positive",
        "content": "HR 邀请进一步沟通",
        "next_action": "准备面试时间",
    })
    listed = client.get("/api/greetings/replies").json()
    stats = client.get("/api/greetings/stats").json()

    assert response.status_code == 200
    assert response.json()["record"]["replyType"] == "positive"
    assert listed["summary"]["total"] == 1
    assert listed["summary"]["positive"] == 1
    assert stats["summary"]["replies"] == 1


def test_greeting_template_effectiveness_groups_replies(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.services.workflow_persistence import save_send_record

    jobs_route._job_store["job-1"] = JobRecord(id="job-1", title="产品经理", company="示例科技", jd_text="负责产品规划", source_url="https://example.com/1")
    jobs_route._job_store["job-2"] = JobRecord(id="job-2", title="运营经理", company="运营科技", jd_text="负责用户运营", source_url="https://example.com/2")
    save_send_record("job-1", "sent", "已发送", message="您好，我有产品规划经验，希望沟通。", dry_run=False)
    save_send_record("job-2", "sent", "已发送", message="您好，我有用户运营经验，希望沟通。", dry_run=False)
    client.post("/api/greetings/replies", json={"job_id": "job-1", "reply_type": "positive", "content": "可以聊聊", "next_action": "约时间"})

    body = client.get("/api/greetings/template-effectiveness").json()

    assert body["summary"]["sent"] == 2
    assert body["summary"]["replyRate"] == 50
    assert body["byJobType"][0]["jobType"] in {"产品", "运营"}
    assert any(item["positiveReplies"] == 1 for item in body["byJobType"])


def test_greeting_send_respects_daily_limit(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    for index in range(3):
        job_id = f"job-{index}"
        jobs_route._job_store[job_id] = JobRecord(
            id=job_id,
            title="产品经理",
            company=f"示例科技{index}",
            city="上海",
            jd_text="负责产品规划",
            source_url=f"https://example.com/job/{index}",
        )

    body = client.post("/api/greetings/send", json={
        "job_ids": ["job-0", "job-1", "job-2"],
        "messages": {
            "job-0": "您好，我对贵司的产品经理岗位很感兴趣，过往有需求分析经验，希望有机会进一步沟通。",
            "job-1": "您好，我对贵司的产品经理岗位很感兴趣，过往有项目推进经验，希望有机会进一步沟通。",
            "job-2": "您好，我对贵司的产品经理岗位很感兴趣，过往有用户研究经验，希望有机会进一步沟通。",
        },
        "confirm": True,
        "daily_limit": 2,
    }).json()

    assert body["summary"]["sent"] == 2
    assert body["summary"]["skipped"] == 1
    skipped = {item["jobId"]: item["reason"] for item in body["skipped"]}
    assert skipped["job-2"] == "rate_limited"


def test_greeting_send_with_only_skips_completes_workflow_task(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.services import workflow_tasks
    from app.services.workflow_persistence import save_send_record

    jobs_route._job_store["already"] = JobRecord(
        id="already",
        title="产品经理",
        company="已沟通科技",
        city="上海",
        jd_text="负责产品规划",
        source_url="https://example.com/job/already",
    )
    save_send_record("already", "sent", "之前已沟通")

    body = client.post("/api/greetings/send", json={
        "job_ids": ["already"],
        "messages": {"already": "您好，我对贵司的产品经理岗位很感兴趣，过往有需求分析经验，希望有机会进一步沟通。"},
        "confirm": True,
    }).json()

    assert body["summary"]["total"] == 1
    assert body["summary"]["sent"] == 0
    assert body["summary"]["failed"] == 0
    assert body["summary"]["skipped"] == 1
    task = workflow_tasks.load_tasks(limit=1)[0]
    assert task["status"] == "completed"
    assert task["payload"]["skipped"][0]["reason"] == "already_contacted"


def test_greeting_browser_auto_mode_invokes_sender_and_marks_sent(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.routes import greetings as greeting_route
    _enable_auto_send()

    sent_calls = []

    def fake_sender(job, message):
        sent_calls.append((job.id, message))
        return {"ok": True, "status": "sent", "message": "已自动发送"}

    monkeypatch.setattr(greeting_route, "execute_browser_greeting", fake_sender)
    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        city="上海",
        jd_text="负责产品规划",
        source_url="https://example.com/job/1",
    )

    body = client.post("/api/greetings/send", json={
        "job_ids": ["job-1"],
        "messages": {"job-1": "您好，我对贵司的产品经理岗位很感兴趣，过往有需求分析经验，希望有机会进一步沟通。"},
        "confirm": True,
        "mode": "browser_auto",
    }).json()

    assert body["summary"]["sent"] == 1
    assert body["records"][0]["status"] == "sent"
    assert sent_calls[0][0] == "job-1"
    assert jobs_route._job_store["job-1"].application_status == "greeted"


def test_greeting_browser_auto_closes_browser_after_task(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.routes import greetings as greeting_route
    _enable_auto_send()

    closed = []
    monkeypatch.setattr(greeting_route, "execute_browser_greeting", lambda job, message: {"ok": True, "status": "sent", "message": "已自动发送"})
    monkeypatch.setattr(greeting_route, "close_browser_after_greeting_task", lambda: closed.append(True))
    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        city="上海",
        jd_text="负责产品规划",
        source_url="https://example.com/job/1",
    )

    body = client.post("/api/greetings/send", json={
        "job_ids": ["job-1"],
        "messages": {"job-1": "您好，我对贵司的产品经理岗位很感兴趣，过往有需求分析经验，希望有机会进一步沟通。"},
        "confirm": True,
        "mode": "browser_auto",
    }).json()

    assert body["summary"]["sent"] == 1
    assert closed == [True]


def test_greeting_browser_auto_schedules_browser_close_after_response_boundary(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.routes import greetings as greeting_route
    _enable_auto_send()

    class FakeBackgroundTasks:
        def __init__(self):
            self.tasks = []

        def add_task(self, fn, *args, **kwargs):
            self.tasks.append((fn, args, kwargs))

    closed = []
    monkeypatch.setattr(greeting_route, "execute_browser_greeting", lambda job, message: {"ok": True, "status": "sent", "message": "已自动发送"})
    monkeypatch.setattr(greeting_route, "close_browser_after_greeting_task", lambda: closed.append(True))
    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        city="上海",
        jd_text="负责产品规划",
        source_url="https://example.com/job/1",
    )

    background_tasks = FakeBackgroundTasks()
    body = greeting_route.send_greetings(greeting_route.GreetingSendRequest(
        job_ids=["job-1"],
        messages={"job-1": "您好，我对贵司的产品经理岗位很感兴趣，过往有需求分析经验，希望有机会进一步沟通。"},
        confirm=True,
        mode="browser_auto",
    ), background_tasks=background_tasks)

    assert body["summary"]["sent"] == 1
    assert closed == []
    assert len(background_tasks.tasks) == 1

    fn, args, kwargs = background_tasks.tasks[0]
    fn(*args, **kwargs)
    assert closed == [True]


def test_greeting_manual_confirm_does_not_close_browser(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.routes import greetings as greeting_route

    closed = []
    monkeypatch.setattr(greeting_route, "close_browser_after_greeting_task", lambda: closed.append(True))
    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        city="上海",
        jd_text="负责产品规划",
        source_url="https://example.com/job/1",
    )

    body = client.post("/api/greetings/send", json={
        "job_ids": ["job-1"],
        "messages": {"job-1": "您好，我对贵司的产品经理岗位很感兴趣，过往有需求分析经验，希望有机会进一步沟通。"},
        "confirm": True,
        "mode": "manual_confirm",
    }).json()

    assert body["summary"]["sent"] == 1
    assert closed == []


def test_boss_greeting_script_clicks_nearest_actionable_chat_button():
    from app.services.boss_scraper import GREETING_SEND_JS_TEMPLATE

    assert "function nearestActionable" in GREETING_SEND_JS_TEMPLATE
    assert "function actionableByText" in GREETING_SEND_JS_TEMPLATE
    assert "function chatInput" in GREETING_SEND_JS_TEMPLATE
    assert ".startchat-dialog textarea" in GREETING_SEND_JS_TEMPLATE
    assert "ipt-search" in GREETING_SEND_JS_TEMPLATE
    assert "candidates.sort" in GREETING_SEND_JS_TEMPLATE
    assert "clickElement(chatButton)" in GREETING_SEND_JS_TEMPLATE
    assert ".closest('button,a" in GREETING_SEND_JS_TEMPLATE


def test_cdp_eval_js_waits_for_async_greeting_script():
    from app.services.boss_scraper import CDPSession

    captured = {}
    cdp = CDPSession.__new__(CDPSession)

    def fake_send(method, params=None, sid=None, timeout=30):
        captured["method"] = method
        captured["params"] = params
        return {"result": {"result": {"value": "ok"}}}

    cdp.send = fake_send

    assert cdp.eval_js("(async function(){ return 'ok'; })()", "sid-1") == "ok"
    assert captured["method"] == "Runtime.evaluate"
    assert captured["params"]["awaitPromise"] is True


def test_greeting_browser_auto_mode_blocks_when_sender_reports_risk(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.routes import greetings as greeting_route
    _enable_auto_send()

    def fake_sender(job, message):
        return {"ok": False, "status": "blocked", "failureCode": "risk_control", "message": "检测到验证码或页面风控"}

    monkeypatch.setattr(greeting_route, "execute_browser_greeting", fake_sender)
    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        city="上海",
        jd_text="负责产品规划",
        source_url="https://example.com/job/1",
    )

    body = client.post("/api/greetings/send", json={
        "job_ids": ["job-1"],
        "messages": {"job-1": "您好，我对贵司的产品经理岗位很感兴趣，过往有需求分析经验，希望有机会进一步沟通。"},
        "confirm": True,
        "mode": "browser_auto",
    }).json()

    assert body["summary"]["sent"] == 0
    assert body["summary"]["failed"] == 1
    assert body["records"][0]["status"] == "blocked"
    assert body["records"][0]["failureCode"] == "risk_control"
    assert jobs_route._job_store["job-1"].application_status == "pending"


def test_greeting_browser_auto_waits_between_successful_sends(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.routes import greetings as greeting_route
    client.post("/api/greetings/auto-send-settings", json={
        "auto_send_enabled": True,
        "gray_mode_enabled": False,
        "send_interval_seconds": 7,
    })

    calls = []
    waits = []

    def fake_sender(job, message):
        calls.append(job.id)
        return {"ok": True, "status": "sent", "message": "已自动发送"}

    monkeypatch.setattr(greeting_route, "execute_browser_greeting", fake_sender)
    monkeypatch.setattr(greeting_route, "sleep_between_greetings", lambda seconds: waits.append(seconds))
    for index in range(2):
        jobs_route._job_store[f"job-{index}"] = JobRecord(
            id=f"job-{index}",
            title="产品经理",
            company=f"示例科技{index}",
            city="上海",
            jd_text="负责产品规划",
            source_url=f"https://example.com/job/{index}",
        )

    body = client.post("/api/greetings/send", json={
        "job_ids": ["job-0", "job-1"],
        "messages": {
            "job-0": "您好，我对贵司的产品经理岗位很感兴趣，过往有需求分析经验，希望有机会进一步沟通。",
            "job-1": "您好，我对贵司的产品经理岗位很感兴趣，过往有项目推进经验，希望有机会进一步沟通。",
        },
        "confirm": True,
        "mode": "browser_auto",
        "send_interval_seconds": 7,
    }).json()

    assert body["summary"]["sent"] == 2
    assert calls == ["job-0", "job-1"]
    assert waits == [7]


def test_greeting_browser_auto_pauses_remaining_after_blocked_result(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.routes import greetings as greeting_route
    _enable_auto_send()

    calls = []

    def fake_sender(job, message):
        calls.append(job.id)
        return {"ok": False, "status": "blocked", "failureCode": "risk_control", "message": "检测到验证码或页面风控"}

    monkeypatch.setattr(greeting_route, "execute_browser_greeting", fake_sender)
    for index in range(3):
        jobs_route._job_store[f"job-{index}"] = JobRecord(
            id=f"job-{index}",
            title="产品经理",
            company=f"示例科技{index}",
            city="上海",
            jd_text="负责产品规划",
            source_url=f"https://example.com/job/{index}",
        )

    body = client.post("/api/greetings/send", json={
        "job_ids": ["job-0", "job-1", "job-2"],
        "messages": {
            "job-0": "您好，我对贵司的产品经理岗位很感兴趣，过往有需求分析经验，希望有机会进一步沟通。",
            "job-1": "您好，我对贵司的产品经理岗位很感兴趣，过往有项目推进经验，希望有机会进一步沟通。",
            "job-2": "您好，我对贵司的产品经理岗位很感兴趣，过往有用户研究经验，希望有机会进一步沟通。",
        },
        "confirm": True,
        "mode": "browser_auto",
    }).json()

    assert calls == ["job-0"]
    assert body["summary"]["failed"] == 1
    skipped = {item["jobId"]: item["reason"] for item in body["skipped"]}
    assert skipped["job-1"] == "paused_after_blocked"
    assert skipped["job-2"] == "paused_after_blocked"


def test_greeting_retry_failed_replays_failed_job_ids(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.routes import greetings as greeting_route
    _enable_auto_send()

    outcomes = [
        {"ok": False, "status": "blocked", "failureCode": "risk_control", "message": "检测到验证码或页面风控"},
        {"ok": True, "status": "sent", "message": "已自动发送"},
    ]

    def fake_sender(job, message):
        return outcomes.pop(0)

    monkeypatch.setattr(greeting_route, "execute_browser_greeting", fake_sender)
    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        city="上海",
        jd_text="负责产品规划",
        source_url="https://example.com/job/1",
    )
    message = "您好，我对贵司的产品经理岗位很感兴趣，过往有需求分析经验，希望有机会进一步沟通。"
    first = client.post("/api/greetings/send", json={
        "job_ids": ["job-1"],
        "messages": {"job-1": message},
        "confirm": True,
        "mode": "browser_auto",
    }).json()

    retried = client.post(f"/api/greetings/retry-failed/{first['taskId']}").json()

    assert retried["summary"]["sent"] == 1
    assert jobs_route._job_store["job-1"].application_status == "greeted"


def test_workflow_retry_executes_failed_greeting_task(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.routes import greetings as greeting_route
    _enable_auto_send()

    outcomes = [
        {"ok": False, "status": "failed", "failureCode": "input_not_found", "message": "未找到聊天输入框"},
        {"ok": True, "status": "sent", "message": "已自动发送"},
    ]

    monkeypatch.setattr(greeting_route, "execute_browser_greeting", lambda job, message: outcomes.pop(0))
    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        city="上海",
        jd_text="负责产品规划",
        source_url="https://example.com/job/1",
    )
    message = "您好，我对贵司的产品经理岗位很感兴趣，过往有需求分析经验，希望有机会进一步沟通。"
    first = client.post("/api/greetings/send", json={
        "job_ids": ["job-1"],
        "messages": {"job-1": message},
        "confirm": True,
        "mode": "browser_auto",
    }).json()

    retried = client.post(f"/api/workflow/tasks/{first['taskId']}/retry").json()

    assert retried["task"]["status"] == "completed"
    assert retried["task"]["id"] == first["taskId"]
    assert "sourceTaskId" not in retried["task"]
    assert retried["result"]["summary"]["sent"] == 1
    assert jobs_route._job_store["job-1"].application_status == "greeted"


def test_greeting_auto_send_requires_global_switch(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        city="上海",
        jd_text="负责产品规划",
        source_url="https://example.com/job/1",
    )

    response = client.post("/api/greetings/send", json={
        "job_ids": ["job-1"],
        "messages": {"job-1": "您好，我对贵司的产品经理岗位很感兴趣，过往有需求分析经验，希望有机会进一步沟通。"},
        "confirm": True,
        "mode": "browser_auto",
    })

    assert response.status_code == 403
    assert "自动发送" in response.json()["detail"]


def test_greeting_gray_mode_requires_first_success_before_batch(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.routes import greetings as greeting_route

    jobs_route._job_store.update({
        "job-1": JobRecord(id="job-1", title="产品经理", company="示例科技", city="上海", jd_text="负责产品规划", source_url="https://example.com/1"),
        "job-2": JobRecord(id="job-2", title="后端开发", company="新公司", city="杭州", jd_text="负责后端开发", source_url="https://example.com/2"),
    })
    client.post("/api/greetings/auto-send-settings", json={
        "auto_send_enabled": True,
        "gray_mode_enabled": True,
        "gray_first_success_required": True,
    })
    monkeypatch.setattr(greeting_route, "execute_browser_greeting", lambda job, message: {"ok": True, "status": "sent", "message": "ok"})

    blocked = client.post("/api/greetings/send", json={
        "job_ids": ["job-1", "job-2"],
        "messages": {
            "job-1": "您好，我对贵司的产品经理岗位很感兴趣，过往有需求分析经验，希望有机会进一步沟通。",
            "job-2": "您好，我对贵司的后端开发岗位很感兴趣，过往有接口开发经验，希望有机会进一步沟通。",
        },
        "confirm": True,
        "mode": "browser_auto",
    })
    first = client.post("/api/greetings/send", json={
        "job_ids": ["job-1"],
        "messages": {"job-1": "您好，我对贵司的产品经理岗位很感兴趣，过往有需求分析经验，希望有机会进一步沟通。"},
        "confirm": True,
        "mode": "browser_auto",
    }).json()
    safety = client.get("/api/greetings/safety-summary").json()

    assert blocked.status_code == 403
    assert first["summary"]["sent"] == 1
    assert safety["summary"]["grayMode"]["batchAllowed"] is True


def test_greeting_preflight_reports_switch_login_candidates_and_validation(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.routes import greetings as greeting_route

    monkeypatch.setattr(greeting_route, "check_boss_login_status", lambda **_: {"logged_in": True, "reason": "ok", "message": "已登录", "action": ""})
    _enable_auto_send()
    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        city="上海",
        jd_text="负责产品规划",
        source_url="https://example.com/job/1",
    )

    body = client.post("/api/greetings/preflight", json={
        "job_ids": ["job-1"],
        "messages": {"job-1": "您好，我对贵司的产品经理岗位很感兴趣，过往有需求分析经验，希望有机会进一步沟通。"},
        "mode": "browser_auto",
    }).json()

    assert body["status"] == "ok"
    assert body["summary"]["ok"] >= 4
    assert any(check["key"] == "boss_login" and check["status"] == "ok" for check in body["checks"])


def test_auto_greeting_requires_a_verified_boss_login(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.routes import greetings as greeting_route

    _enable_auto_send()
    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1", title="产品经理", company="示例科技", city="上海",
        jd_text="负责产品规划", source_url="https://example.com/job/1",
    )
    monkeypatch.setattr(greeting_route, "check_boss_login_status", lambda **_: {
        "logged_in": False, "message": "登录已过期", "action": "请重新扫码登录 BOSS 直聘",
    })
    monkeypatch.setattr(greeting_route, "execute_browser_greeting", lambda *args: (_ for _ in ()).throw(AssertionError("发送不应启动")))

    response = client.post("/api/greetings/send", json={
        "job_ids": ["job-1"],
        "messages": {"job-1": "您好，我对贵司的产品经理岗位很感兴趣，过往有需求分析经验，希望有机会进一步沟通。"},
        "confirm": True,
        "mode": "browser_auto",
    })

    assert response.status_code == 401
    assert "登录已过期" in response.json()["detail"]


def test_greeting_control_can_pause_and_resume(tmp_path, monkeypatch):
    _prepare_greeting_test_state(tmp_path, monkeypatch)

    paused = client.post("/api/greetings/control", json={"action": "pause"}).json()
    progress = client.get("/api/greetings/progress").json()
    resumed = client.post("/api/greetings/control", json={"action": "resume"}).json()

    assert paused["control"]["state"] == "paused"
    assert progress["control"]["state"] == "paused"
    assert resumed["control"]["state"] == "running"


def test_greeting_frequency_profiles_and_stats(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.services.workflow_persistence import save_send_record

    jobs_route._job_store["job-1"] = JobRecord(id="job-1", title="产品经理", company="示例科技", application_status="greeted")
    save_send_record("job-1", "sent", "已发送", message="您好，我对产品经理岗位感兴趣", dry_run=False)

    profiles = client.get("/api/greetings/frequency-profiles").json()
    stats = client.get("/api/greetings/stats").json()

    assert {item["key"] for item in profiles["profiles"]} >= {"conservative", "standard", "fast"}
    assert stats["summary"]["sent"] == 1
    assert stats["summary"]["replyTrackingReady"] is True


def test_greeting_selector_health_and_acceptance_plan(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.routes import greetings as greeting_route

    monkeypatch.setattr(greeting_route, "check_boss_selector_health", lambda job_url: {
        "status": "ok",
        "checks": [
            {"key": "chat_button", "status": "ok", "message": "找到立即沟通按钮"},
            {"key": "chat_input", "status": "ok", "message": "找到输入框"},
            {"key": "send_button", "status": "ok", "message": "找到发送按钮"},
        ],
    })
    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        city="上海",
        jd_text="负责产品规划",
        source_url="https://example.com/job/1",
    )

    health = client.post("/api/greetings/selector-health", json={"job_id": "job-1"}).json()
    plan = client.post("/api/greetings/acceptance-plan", json={"job_id": "job-1"}).json()

    assert health["status"] == "ok"
    assert [check["key"] for check in health["checks"]] == ["chat_button", "chat_input", "send_button"]
    assert plan["jobId"] == "job-1"
    assert plan["steps"][0]["key"] == "open_job"
    assert any(step["key"] == "confirm_send" for step in plan["steps"])


def test_greeting_followups_marks_sent_jobs_after_window(tmp_path, monkeypatch):
    jobs_route = _prepare_greeting_test_state(tmp_path, monkeypatch)
    from app.services.workflow_persistence import save_send_record

    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        application_status="greeted",
    )
    record = save_send_record("job-1", "sent", "已发送", message="您好，我对产品经理岗位感兴趣", dry_run=False)
    record["updatedAt"] = "2026-07-20T10:00:00+00:00"
    from app.services import workflow_persistence
    workflow_persistence.write_json_atomic(tmp_path / "greetings" / "send_records.json", [record])

    body = client.get("/api/greetings/followups?now=2026-07-23T11:00:00+00:00").json()

    assert body["summary"]["pendingFollowups"] == 1
    assert body["items"][0]["jobId"] == "job-1"
    assert body["items"][0]["windowHours"] >= 72


def test_greeting_recovery_panel_endpoint_is_removed():
    response = client.get("/api/greetings/recovery-panel")

    assert response.status_code == 404
