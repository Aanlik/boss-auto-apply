from app.services import workflow_persistence as persistence


def test_diligence_reports_are_saved_by_company(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)

    report = {"companyName": "示例科技有限公司", "sourceCompanyName": "示例科技", "companyScore": 82}
    saved = persistence.save_diligence_report(report)

    assert saved["companyName"] == "示例科技有限公司"
    assert saved["sourceCompanyName"] == "示例科技"
    assert saved["companyKey"]
    assert persistence.load_diligence_reports()["示例科技有限公司"]["companyScore"] == 82


def test_rankings_and_greetings_are_persisted(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)

    rankings = [{"jobId": "job-1", "compositeScore": 91}]
    greetings = {"job-1": "您好，我对这个岗位很感兴趣。"}

    persistence.save_rankings(rankings)
    persistence.save_greetings(greetings)

    assert persistence.load_rankings() == rankings
    assert persistence.load_greetings() == greetings


def test_send_record_prevents_duplicate_sent_status(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)

    first = persistence.save_send_record("job-1", "sent", "已人工确认")
    second = persistence.save_send_record("job-1", "sent", "重复确认")

    assert first["status"] == "sent"
    assert second["status"] == "sent"
    assert second["note"] == "已人工确认"
    assert len(persistence.load_send_records()) == 1


def test_send_record_can_revoke_sent_status(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)

    persistence.save_send_record("job-1", "sent", "已人工确认")
    revoked = persistence.save_send_record("job-1", "pending", "误点撤销")

    assert revoked["status"] == "pending"
    assert revoked["note"] == "误点撤销"


def test_find_diligence_report_matches_company_key_and_source_name(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)

    saved = persistence.save_diligence_report({
        "companyName": "示例科技有限公司",
        "sourceCompanyName": "示例科技",
        "companyKey": "91410100TEST",
        "companyScore": 82,
    })

    assert persistence.find_diligence_report("示例科技") == saved
    assert persistence.find_diligence_report("91410100TEST") == saved
