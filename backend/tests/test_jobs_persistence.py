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
