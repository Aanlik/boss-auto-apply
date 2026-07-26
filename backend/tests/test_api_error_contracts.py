from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_diligence_evaluate_requires_company_name():
    response = client.post("/api/diligence/evaluate", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "缺少公司名称"


def test_scoring_rank_requires_job_ids():
    response = client.post("/api/scoring/rank", json={"resume": {"skills": ["Python"]}})

    assert response.status_code == 400
    assert response.json()["detail"] == "没有岗位 ID"


def test_greeting_send_record_requires_job_id():
    response = client.post("/api/greetings/send-records", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "缺少 job_id"


def test_diligence_note_accepts_source_company_name(tmp_path, monkeypatch):
    from app.services import workflow_persistence as persistence

    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)
    persistence.save_diligence_report({
        "companyName": "示例科技有限公司",
        "sourceCompanyName": "示例科技",
        "companyKey": "91410100TEST",
        "companyScore": 82,
    })

    response = client.post("/api/diligence/note", json={"company_name": "示例科技", "note": "重点关注"})

    assert response.status_code == 200
    assert response.json()["userNotes"] == "重点关注"


def test_greeting_send_record_can_mark_pending(tmp_path, monkeypatch):
    from app.services import workflow_persistence as persistence

    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)
    client.post("/api/greetings/send-records", json={"job_id": "job-1", "status": "sent", "note": "已发送"})

    response = client.post("/api/greetings/send-records", json={"job_id": "job-1", "status": "pending", "note": "撤销"})

    assert response.status_code == 200
    assert response.json()["record"]["status"] == "pending"
