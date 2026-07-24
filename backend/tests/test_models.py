from app.models.resume import ResumeProfile


def test_resume_profile_defaults():
    profile = ResumeProfile()
    assert profile.skills == []
    assert profile.target_titles == []
