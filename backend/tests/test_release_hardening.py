from __future__ import annotations

import sqlite3
from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.models.job import JobRecord


client = TestClient(app)


def test_sqlite_primary_store_can_be_enabled_for_jobs(tmp_path, monkeypatch):
    from app.routes import jobs as jobs_route
    from app.services import maintenance_service, workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(jobs_route, "JOBS_FILE", tmp_path / "jobs" / "jobs.json")
    jobs_route._job_store.clear()
    jobs_route._job_store["job-1"] = JobRecord(id="job-1", title="产品经理", company="示例科技", city="上海")

    enabled = client.post("/api/maintenance/storage/primary", json={"active_store": "sqlite"}).json()
    jobs_route._save_jobs()

    assert enabled["activeStore"] == "sqlite"
    assert (tmp_path / "boss_workbench.sqlite3").exists()
    with sqlite3.connect(tmp_path / "boss_workbench.sqlite3") as conn:
        rows = conn.execute("SELECT id, company FROM jobs").fetchall()
    assert rows == [("job-1", "示例科技")]

    status = maintenance_service.storage_status()
    assert status["activeStore"] == "sqlite"


def test_storage_status_exposes_sqlite_lifecycle_and_backup_preview(tmp_path, monkeypatch):
    from app.services import sqlite_kv_store, workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    sqlite_kv_store.put("test", "key", {"value": 1})

    status = client.get("/api/maintenance/storage").json()
    assert status["sqlite"]["schemaVersion"] == sqlite_kv_store.CURRENT_SCHEMA_VERSION
    assert status["sqlite"]["integrity"]["status"] == "ok"

    backup = client.post("/api/maintenance/storage/backup").json()
    assert backup["path"].startswith("storage/backups/")
    preview = client.post("/api/maintenance/storage/restore-preview", json={"path": backup["path"]}).json()
    assert preview["valid"] is True


def test_release_manifest_and_security_audit_are_available(tmp_path, monkeypatch):
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    (tmp_path / "provider.json").write_text('{"api_key":"plain-secret"}', encoding="utf-8")

    manifest = client.get("/api/maintenance/release/manifest").json()
    audit = client.get("/api/maintenance/security/audit").json()

    assert manifest["kind"] == "release_manifest"
    assert manifest["qualityGates"]
    assert any(item["key"] == "plain_secret_scan" for item in audit["checks"])
    assert audit["status"] in {"ok", "warn", "error"}


def test_redacted_backup_masks_secrets_and_personal_fields(tmp_path, monkeypatch):
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    (tmp_path / "provider.json").write_text('{"api_key":"sk-real-secret","owner_email":"user@example.com"}', encoding="utf-8")
    (tmp_path / "resumes").mkdir()
    (tmp_path / "resumes" / "active.json").write_text(
        '{"name":"张三","phone":"13800138000","summary":"联系邮箱 user@example.com"}',
        encoding="utf-8",
    )

    response = client.get("/api/maintenance/backup/export-redacted")

    assert response.status_code == 200
    body = response.json()
    exported = "\n".join(str(item["content"]) for item in body["files"])
    assert body["kind"] == "redacted_workspace_backup"
    assert "sk-real-secret" not in exported
    assert "13800138000" not in exported
    assert "user@example.com" not in exported
    assert "[SECRET_REDACTED]" in exported
    assert "[PRIVACY_REDACTED]" in exported or "[EMAIL_REDACTED]" in exported


def test_release_acceptance_checklist_is_available(tmp_path, monkeypatch):
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)

    response = client.get("/api/maintenance/release/acceptance")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "release_acceptance_checklist"
    assert len(body["sections"]) >= 3
    assert any(section["key"] == "greeting_flow" for section in body["sections"])


def test_onboarding_checklist_exposes_progress_and_actions(tmp_path, monkeypatch):
    from app.routes import jobs as jobs_route
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    jobs_route._job_store.clear()
    jobs_route._job_store["job-1"] = JobRecord(id="job-1", title="产品经理", company="示例科技", jd_text="")

    body = client.get("/api/dashboard/onboarding").json()

    assert "progress" in body
    assert body["progress"]["total"] >= 6
    assert any(step["action"] for step in body["steps"])
    assert body["steps"][0]["page"] in {"resumes", "settings"}


def test_runtime_mode_can_be_switched_from_settings(tmp_path, monkeypatch):
    from app.services import workflow_persistence

    monkeypatch.delenv("BOSS_WORKBENCH_MODE", raising=False)
    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)

    saved = client.post("/api/settings/runtime-mode", json={"mode": "demo"})
    status = client.get("/api/settings/runtime-mode").json()
    invalid = client.post("/api/settings/runtime-mode", json={"mode": "unknown"})

    assert saved.status_code == 200
    assert status["mode"] == "demo"
    assert status["demoAllowed"] is True
    assert status["source"] == "local"
    assert invalid.status_code == 400


def test_onboarding_wizard_marks_primary_next_step(tmp_path, monkeypatch):
    from app.routes import jobs as jobs_route
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    jobs_route._job_store.clear()

    body = client.get("/api/dashboard/onboarding/wizard").json()

    assert body["kind"] == "onboarding_wizard"
    assert body["primaryAction"]
    assert sum(1 for step in body["steps"] if step["primary"]) == 1
    assert body["steps"][0]["stateLabel"] in {"已完成", "待完成"}


def test_jobs_import_wizard_previews_and_applies_only_new_jobs(tmp_path, monkeypatch):
    from app.routes import jobs as jobs_route

    monkeypatch.setattr(jobs_route, "JOBS_FILE", tmp_path / "jobs" / "jobs.json")
    jobs_route._job_store.clear()
    existing = JobRecord(id="existing", title="产品经理", company="示例科技", city="上海")
    jobs_route._refresh_job_dedupe_key(existing)
    jobs_route._job_store["existing"] = existing
    csv_text = "title,company,city,salary\n产品经理,示例科技,上海,20-30K\n后端开发,新公司,杭州,25-35K\n,坏数据,上海,10K\n"

    preview = client.post("/api/jobs/import-wizard/preview", json={"text": csv_text}).json()
    applied = client.post("/api/jobs/import-wizard/apply", json={"text": csv_text}).json()

    assert preview["summary"] == {"total": 3, "creates": 1, "duplicates": 1, "invalid": 1}
    assert applied["imported"] == 1
    assert applied["skipped"] == 2
    assert any(job.company == "新公司" for job in jobs_route._job_store.values())


def test_release_notes_are_available(tmp_path, monkeypatch):
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)

    response = client.get("/api/maintenance/release/notes")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "release_notes"
    assert body["version"]
    assert body["highlights"]
    assert body["knownRisks"]


def test_workflow_recovery_groups_classify_failures(tmp_path, monkeypatch):
    from app.services import workflow_tasks

    monkeypatch.setattr(workflow_tasks, "TASKS_FILE", tmp_path / "workflow" / "tasks.json")
    task = workflow_tasks.start_task("greeting_send", "自动打招呼", total=1)
    workflow_tasks.fail_task(task["id"], "未找到发送按钮", error_code="send_button_not_found", action="", retryable=True)

    response = client.get("/api/workflow/center")

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["failed"] == 1
    assert body["recoveryGroups"][0]["category"] == "page_changed"
    assert body["recoveryGroups"][0]["retryable"] == 1


def test_weekly_report_summarizes_recent_flow(tmp_path, monkeypatch):
    from app.routes import jobs as jobs_route
    from app.services import workflow_persistence, workflow_tasks

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(workflow_tasks, "TASKS_FILE", tmp_path / "workflow" / "tasks.json")
    now = datetime.now().isoformat()
    jobs_route._job_store.clear()
    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        jd_text="负责产品规划",
        captured_at=now,
        fetched_at=now,
        application_status="interviewing",
        status_history=[
            {"kind": "application", "status": "greeted", "previous": "pending", "note": "", "at": now},
            {"kind": "application", "status": "interviewing", "previous": "greeted", "note": "", "at": now},
        ],
    )
    workflow_persistence.save_send_record("job-1", "sent", "已发送", message="你好", dry_run=False)
    task = workflow_tasks.start_task("boss_detail", "补全 JD", total=1)
    workflow_tasks.fail_task(task["id"], "网络失败", error_code="network_error", retryable=True)

    response = client.get("/api/dashboard/weekly-report")

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["capturedJobs"] == 1
    assert body["summary"]["jdReady"] == 1
    assert body["summary"]["greetingsSent"] == 1
    assert body["summary"]["interviewing"] == 1
    assert body["failureGroups"][0]["category"] == "network"


def test_deep_report_can_be_exported_as_markdown(tmp_path, monkeypatch):
    from app.routes import assistant as assistant_route
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(assistant_route, "_results_file", lambda: tmp_path / "assistant" / "results.json")

    client.post("/api/assistant/deep-report", json={
        "job": {"id": "job-1", "title": "产品经理", "company": "示例科技", "city": "上海", "jd_text": "负责产品规划"},
        "resume": {"skills": ["产品规划"]},
        "diligence": {"companyName": "示例科技", "companyScore": 82, "riskLevel": "low"},
        "ranking": {"matchScore": 85, "compositeScore": 84},
    })

    response = client.get("/api/assistant/deep-report/export?job_id=job-1&format=md")

    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert "示例科技" in response.text
    assert "求职深度报告" in response.text


def test_deep_report_section_edit_is_used_by_exports(tmp_path, monkeypatch):
    from app.routes import assistant as assistant_route
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(assistant_route, "_results_file", lambda: tmp_path / "assistant" / "results.json")

    client.post("/api/assistant/deep-report", json={
        "job": {"id": "job-2", "title": "增长产品", "company": "章节科技", "jd_text": "负责用户增长"},
        "resume": {"skills": ["增长"]},
        "diligence": {"companyName": "章节科技", "companyScore": 80, "riskLevel": "low"},
    })
    edited = client.post("/api/assistant/deep-report/edit", json={
        "job_id": "job-2",
        "summary": "人工总览",
        "sections": {
            "strategy": "人工策略章节",
            "risk": "人工风险章节",
            "interview": "人工面试章节",
            "actions": "人工行动章节",
        },
    })
    exported = client.get("/api/assistant/deep-report/export?job_id=job-2&format=md")

    assert edited.status_code == 200
    assert edited.json()["record"]["result"]["manualReport"]["sections"]["strategy"] == "人工策略章节"
    assert "人工策略章节" in exported.text
    assert "人工面试章节" in exported.text


def test_deep_report_pdf_export_uses_polished_manual_sections(tmp_path, monkeypatch):
    from app.routes import assistant as assistant_route
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(assistant_route, "_results_file", lambda: tmp_path / "assistant" / "results.json")

    client.post("/api/assistant/deep-report", json={
        "job": {"id": "job-pdf", "title": "商业化产品经理", "company": "报告科技", "jd_text": "负责商业化策略"},
        "resume": {"skills": ["商业化", "产品策略"]},
        "diligence": {"companyName": "报告科技", "companyScore": 78, "riskLevel": "low"},
    })
    client.post("/api/assistant/deep-report/edit", json={
        "job_id": "job-pdf",
        "summary": "人工总览",
        "sections": {
            "strategy": "人工策略章节",
            "match": "人工匹配章节",
            "risk": "人工风险章节",
            "interview": "人工面试章节",
            "actions": "人工行动章节",
        },
    })

    response = client.get("/api/assistant/deep-report/export?job_id=job-pdf&format=pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 1000


def test_ai_feedback_can_be_recorded_and_summarized(tmp_path, monkeypatch):
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)

    response = client.post("/api/feedback", json={
        "domain": "ranking",
        "targetId": "job-1",
        "useful": False,
        "note": "排序理由不够具体",
        "context": {"score": 62},
    })
    summary = client.get("/api/feedback/summary")
    listed = client.get("/api/feedback?domain=ranking")

    assert response.status_code == 200
    assert response.json()["record"]["targetId"] == "job-1"
    assert response.json()["record"]["useful"] is False
    assert summary.json()["summary"]["total"] == 1
    assert summary.json()["byDomain"]["ranking"]["notUseful"] == 1
    assert listed.json()["records"][0]["note"] == "排序理由不够具体"


def test_ai_feedback_preference_profile_summarizes_user_taste(tmp_path, monkeypatch):
    from app.services import feedback_store, workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    feedback_store.save_feedback("ranking", "job-a", False, context={"weightPreference": "company", "jobType": "产品"})
    feedback_store.save_feedback("ranking", "job-b", False, context={"weightPreference": "match", "jobType": "运营"})
    feedback_store.save_feedback("deep_report", "job-c", False, note="面试建议太泛泛")

    response = client.get("/api/feedback/preference-profile")

    assert response.status_code == 200
    body = response.json()
    assert body["weightHints"]["company"] == 1
    assert body["weightHints"]["match"] == 1
    assert body["domains"]["deep_report"]["notUseful"] == 1
    assert "面试建议太泛泛" in body["recentNeeds"][0]


def test_deep_report_includes_feedback_guidance(tmp_path, monkeypatch):
    from app.routes import assistant as assistant_route
    from app.services import feedback_store, workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(assistant_route, "_results_file", lambda: tmp_path / "assistant" / "results.json")
    feedback_store.save_feedback("deep_report", "job-1", False, note="风险解释太笼统")

    response = client.post("/api/assistant/deep-report", json={
        "job": {"id": "job-1", "title": "产品经理", "company": "反馈科技", "jd_text": "负责产品规划"},
        "resume": {"skills": ["产品规划"]},
        "diligence": {"companyName": "反馈科技", "companyScore": 85, "riskLevel": "low"},
    })

    assert response.status_code == 200
    assert response.json()["feedbackGuidance"]["summary"]["notUseful"] == 1
    assert "风险解释太笼统" in response.json()["feedbackGuidance"]["recentNotes"][0]


def test_dashboard_trends_and_data_quality_center_surface_actionable_issues(tmp_path, monkeypatch):
    from app.routes import jobs as jobs_route
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(jobs_route, "JOBS_FILE", tmp_path / "jobs" / "jobs.json")
    jobs_route._job_store.clear()
    now = datetime.now().isoformat()
    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="示例科技",
        city="上海",
        jd_text="",
        captured_at=now,
        lifecycle_status="active",
        status_history=[{"kind": "application", "status": "interviewing", "at": now}],
    )
    jobs_route._job_store["job-2"] = JobRecord(
        id="job-2",
        title="产品经理",
        company="示例科技",
        city="上海",
        jd_text="岗位描述过短",
        captured_at=now,
        lifecycle_status="suspected_expired",
    )
    workflow_persistence.save_send_record("job-1", "sent")
    client.post("/api/greetings/replies", json={"job_id": "job-1", "reply_type": "positive", "content": "约面"})

    trends = client.get("/api/dashboard/trends?days=30")
    quality = client.get("/api/dashboard/data-quality")

    assert trends.status_code == 200
    assert trends.json()["summary"]["capturedJobs"] == 2
    assert trends.json()["summary"]["greetingsSent"] == 1
    assert trends.json()["summary"]["replies"] == 1
    assert trends.json()["summary"]["positiveReplies"] == 1
    assert quality.status_code == 200
    checks = {item["key"]: item for item in quality.json()["checks"]}
    assert checks["missing_jd"]["count"] == 1
    assert checks["duplicate_jobs"]["count"] == 1
    assert checks["suspected_expired"]["count"] == 1
    assert checks["no_rankings"]["count"] == 2


def test_deep_report_records_prompt_versions_and_feedback_snapshot(tmp_path, monkeypatch):
    from app.routes import assistant as assistant_route
    from app.services import feedback_store, workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(assistant_route, "_results_file", lambda: tmp_path / "assistant" / "results.json")
    feedback_store.save_feedback("deep_report", "job-1", False, note="行动建议不够具体")

    response = client.post("/api/assistant/deep-report", json={
        "job": {"id": "job-1", "title": "产品经理", "company": "版本科技", "jd_text": "负责产品规划"},
        "resume": {"skills": ["产品规划"]},
        "diligence": {"companyName": "版本科技", "companyScore": 85, "riskLevel": "low"},
    })
    versions = client.get("/api/assistant/prompt-versions?kind=deep_report")

    assert response.status_code == 200
    assert response.json()["promptVersion"] == "deep-report-v2"
    assert versions.status_code == 200
    record = versions.json()["versions"][0]
    assert record["kind"] == "deep_report"
    assert record["promptVersion"] == "deep-report-v2"
    assert "行动建议不够具体" in record["feedbackGuidance"]["recentNotes"][0]


def test_greeting_safety_summary_blocks_high_failure_streak(tmp_path, monkeypatch):
    from app.routes import jobs as jobs_route
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(jobs_route, "JOBS_FILE", tmp_path / "jobs" / "jobs.json")
    jobs_route._job_store.clear()
    for idx in range(3):
        workflow_persistence.save_send_record(f"job-{idx}", "failed", "页面风控")

    response = client.get("/api/greetings/safety-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert body["summary"]["failedStreak"] == 3
    assert any(check["key"] == "failure_streak" and check["status"] == "error" for check in body["checks"])


def test_data_quality_repair_tags_missing_jd_and_low_quality_jobs(tmp_path, monkeypatch):
    from app.routes import jobs as jobs_route
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(jobs_route, "JOBS_FILE", tmp_path / "jobs" / "jobs.json")
    jobs_route._job_store.clear()
    jobs_route._job_store["missing"] = JobRecord(id="missing", title="产品", company="甲公司", jd_text="")
    jobs_route._job_store["low"] = JobRecord(id="low", title="运营", company="乙公司", jd_text="负责运营")

    response = client.post("/api/dashboard/data-quality/repair", json={"actions": ["tag_missing_jd", "tag_low_quality_jd"]})

    assert response.status_code == 200
    assert response.json()["updated"] == 2
    assert "缺少JD" in jobs_route._job_store["missing"].tags
    assert "JD待清理" in jobs_route._job_store["low"].tags


def test_prompt_version_compare_returns_latest_two_versions(tmp_path, monkeypatch):
    from app.routes import assistant as assistant_route
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(assistant_route, "_results_file", lambda: tmp_path / "assistant" / "results.json")
    payload = {
        "job": {"id": "job-compare", "title": "产品经理", "company": "比较科技", "jd_text": "负责产品规划"},
        "resume": {},
        "diligence": {},
    }
    client.post("/api/assistant/deep-report", json=payload)
    client.post("/api/assistant/deep-report", json=payload)

    response = client.get("/api/assistant/prompt-versions/compare?job_id=job-compare")

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["comparable"] is True
    assert len(body["versions"]) == 2
    assert body["differences"]["samePromptVersion"] is True


def test_release_guard_pdf_options_and_retention_rules_are_available(tmp_path, monkeypatch):
    from app.routes import jobs as jobs_route
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(jobs_route, "JOBS_FILE", tmp_path / "jobs" / "jobs.json")
    jobs_route._job_store.clear()
    jobs_route._job_store["old"] = JobRecord(
        id="old",
        title="产品经理",
        company="旧公司",
        fetched_at="2026-01-01T00:00:00",
        lifecycle_status="active",
    )

    pdf_options = client.get("/api/resumes/pdf-preview-options")
    guard = client.get("/api/maintenance/release/production-guard")
    rules = client.post("/api/maintenance/retention/rules/apply", json={"suspect_after_days": 30, "archive_after_days": 120})

    assert pdf_options.status_code == 200
    assert "densityOptions" in pdf_options.json()
    assert guard.status_code == 200
    assert guard.json()["mode"] in {"production", "demo", "test"}
    assert rules.status_code == 200
    assert rules.json()["markedSuspected"] == 1
    assert jobs_route._job_store["old"].lifecycle_status == "suspected_expired"


def test_final_polish_confirm_report_pdf_density_and_restore_drill(tmp_path, monkeypatch):
    from app.routes import assistant as assistant_route
    from app.routes import jobs as jobs_route
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(jobs_route, "JOBS_FILE", tmp_path / "jobs" / "jobs.json")
    monkeypatch.setattr(assistant_route, "_results_file", lambda: tmp_path / "assistant" / "results.json")
    jobs_route._job_store.clear()
    jobs_route._job_store["job-1"] = JobRecord(
        id="job-1",
        title="产品经理",
        company="精修科技",
        jd_text="负责产品规划和用户增长",
        source_url="https://www.zhipin.com/job_detail/1.html",
    )

    confirm = client.post("/api/greetings/final-confirmation", json={
        "job_ids": ["job-1"],
        "messages": {"job-1": "您好，我对贵司产品经理岗位很感兴趣，希望进一步沟通。"},
        "mode": "browser_auto",
        "daily_limit": 15,
    })
    report = client.post("/api/assistant/deep-report", json={
        "job": jobs_route._job_store["job-1"].model_dump(),
        "resume": {"summary": "产品规划经验"},
        "diligence": {"companyName": "精修科技", "companyScore": 88, "riskLevel": "low"},
    })
    quality = client.get("/api/assistant/deep-report/quality?job_id=job-1")
    pdf = client.post("/api/resumes/preview-pdf", json={
        "profile": {"name": "张三", "title": "产品经理", "summary": "负责产品规划", "skills": [], "target_titles": [], "work_experience": [], "education": [], "projects": []},
        "optimization": {},
        "company": "精修科技",
        "job_title": "产品经理",
        "template": "modern",
        "density": "comfortable",
    })
    restore = client.post("/api/maintenance/backup/restore-drill", json={"backup": {"kind": "full_backup", "files": [{"path": "jobs/jobs.json", "content": "{}"}]}})
    online = client.get("/api/maintenance/release/online-report")

    assert confirm.status_code == 200
    assert confirm.json()["summary"]["jobCount"] == 1
    assert "https://www.zhipin.com/job_detail/1.html" in confirm.json()["links"][0]
    assert report.status_code == 200
    assert report.json()["quality"]["score"] >= 60
    assert quality.status_code == 200
    assert quality.json()["score"] == report.json()["quality"]["score"]
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert restore.status_code == 200
    assert restore.json()["wouldRestore"] == 1
    assert online.status_code == 200
    assert online.json()["kind"] == "online_acceptance_report"


def test_release_pdf_visual_regression_endpoint_renders_samples(tmp_path, monkeypatch):
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)

    response = client.get("/api/maintenance/release/pdf-visual-regression")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["checks"]["resume"]["pages"][0]["nonWhiteRatio"] > 0.01
    assert response.json()["checks"]["resume"]["previewDataUrl"].startswith("data:image/png;base64,")
    assert response.json()["checks"]["deepReport"]["pages"][0]["nonWhiteRatio"] > 0.01


def test_dependency_audit_dry_run_and_migration_wizard_are_available(tmp_path, monkeypatch):
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)

    audit = client.get("/api/maintenance/security/dependency-audit?dry_run=true")
    wizard = client.get("/api/maintenance/storage/migration-wizard")

    assert audit.status_code == 200
    assert audit.json()["dryRun"] is True
    assert len(audit.json()["checks"]) >= 2
    assert wizard.status_code == 200
    assert wizard.json()["steps"][0]["key"] == "backup"
    assert wizard.json()["nextStep"]["label"]


def test_pdf_template_metadata_exposes_visual_styles():
    response = client.get("/api/resumes/pdf-templates")

    assert response.status_code == 200
    body = response.json()
    assert body["templates"]["modern"]["font"]
    assert body["templates"]["ats"]["density"] == "compact"


def test_boss_capture_page_and_detail_logs_are_recorded(tmp_path, monkeypatch):
    from app.routes import jobs as jobs_route
    from app.services import workflow_persistence

    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(jobs_route, "JOBS_FILE", tmp_path / "jobs" / "jobs.json")
    monkeypatch.setattr(jobs_route, "log_event", lambda *args, **kwargs: {})
    jobs_route._job_store.clear()

    def fake_ingest_from_boss(**kwargs):
        from app.models.job import JobRecord
        return [JobRecord(id="job-1", title="产品经理", company="示例科技", city="上海")]

    monkeypatch.setattr("app.routes.jobs.ingest_from_boss", fake_ingest_from_boss)
    response = client.post("/api/jobs/capture/boss", json={"keyword": "产品", "city": "上海", "max_pages": 2, "headless": True})

    assert response.status_code == 200
    logs = client.get("/api/maintenance/api-logs?category=boss_capture").json()["logs"]
    assert any(log["detail"].get("scope") == "page" for log in logs)
    assert any(log["detail"].get("scope") == "summary" for log in logs)
