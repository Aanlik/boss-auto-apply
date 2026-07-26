from app.models.job import JobFilter
from app.services.job_filters import filter_jobs_by_model


def test_filter_jobs_by_model():
    from app.models.job import JobRecord
    jobs = [
        JobRecord(id="1", title="Python 后端工程师", company="A", city="深圳", salary="20-30K", salary_min=20, salary_max=30, keywords=["Python"]),
        JobRecord(id="2", title="前端工程师", company="B", city="北京", salary="15-25K", salary_min=15, salary_max=25, keywords=["React"]),
        JobRecord(id="3", title="Python 全栈", company="C", city="深圳", salary="30-40K", salary_min=30, salary_max=40, keywords=["Python"]),
    ]
    result = filter_jobs_by_model(jobs, JobFilter(keywords=["Python"], city="深圳", min_salary=20))
    assert len(result) == 2
    assert result[0].id == "1"
