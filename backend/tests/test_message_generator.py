from app.services.message_generator import build_message_draft, generate_greeting, revise_greeting


def test_generate_greeting_uses_job_and_resume():
    greeting = generate_greeting(
        job_title="Python 后端工程师",
        resume_summary="3 年 Python 后端经验",
        company_summary="成长型公司",
    )
    assert "Python 后端工程师" not in greeting
    assert "3 年 Python 后端经验" in greeting


def test_generate_greeting_changes_by_job_type():
    backend = generate_greeting("后端工程师", "3 年 Python 后端经验", "成长型公司")
    product = generate_greeting("产品经理", "2 年产品经验", "成长型公司")
    assert backend != product


def test_build_and_revise_message_draft():
    draft = build_message_draft("后端工程师", "3 年 Python 后端经验", "成长型公司")
    revised = revise_greeting(draft.draft, "更简洁一点")
    assert draft.job_title == "后端工程师"
    assert "更简洁一点" in revised
