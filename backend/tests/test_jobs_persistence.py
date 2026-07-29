def test_jobs_save_uses_atomic_writer(monkeypatch, tmp_path):
    import app.routes.jobs as jobs_route
    from app.models.job import JobRecord

    calls = []
    monkeypatch.setattr(jobs_route, "JOBS_FILE", tmp_path / "jobs.json")
    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(id="job-1", title="产品经理", company="示例科技")
    })

    def fake_write(path, payload):
        calls.append((path, payload))

    monkeypatch.setattr(jobs_route, "write_json_atomic", fake_write)

    jobs_route._save_jobs()

    assert calls
    assert calls[0][0] == tmp_path / "jobs.json"
    assert calls[0][1]["job-1"]["company"] == "示例科技"


def test_jobs_save_keeps_previous_file_backup(monkeypatch, tmp_path):
    import json
    import app.routes.jobs as jobs_route
    from app.models.job import JobRecord

    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps({"old-job": {"company": "旧公司"}}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(jobs_route, "JOBS_FILE", jobs_file)
    monkeypatch.setattr(jobs_route, "_job_store", {
        "job-1": JobRecord(id="job-1", title="产品经理", company="示例科技")
    })

    jobs_route._save_jobs()

    backup = jobs_file.with_suffix(".json.bak")
    assert backup.exists()
    assert json.loads(backup.read_text(encoding="utf-8"))["old-job"]["company"] == "旧公司"
