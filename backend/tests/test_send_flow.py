from app.services.send_flow import can_send_job, confirm_send


def test_can_send_job_requires_manual_confirmation():
    assert can_send_job({"manual_confirmed": True}) is True
    assert can_send_job({"manual_confirmed": False}) is False


def test_confirm_send_blocks_unconfirmed_jobs():
    result = confirm_send({"title": "Python 后端工程师", "company": "A 公司", "manual_confirmed": False})
    assert result.status == "blocked"
    assert "人工确认" in result.note


def test_confirm_send_allows_confirmed_jobs():
    result = confirm_send({"title": "Python 后端工程师", "company": "A 公司", "manual_confirmed": True})
    assert result.status == "sent"
