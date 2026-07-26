from app.models.job import JobRecord, JobFilter


def filter_jobs_by_model(jobs: list[JobRecord], filters: JobFilter) -> list[JobRecord]:
    """基于模型的岗位过滤。"""
    results: list[JobRecord] = []
    for job in jobs:
        if filters.keywords:
            title_lower = job.title.lower()
            if not any(kw.lower() in title_lower for kw in filters.keywords):
                continue
        if filters.city and job.city != filters.city:
            continue
        if filters.min_salary and job.salary_min < filters.min_salary:
            continue
        results.append(job)
    return results
