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
        # 最低薪资筛选判断岗位区间是否能达到门槛，例如 10-15K 应命中 13K。
        salary_upper = job.salary_max or job.salary_min
        if filters.min_salary and salary_upper < filters.min_salary:
            continue
        results.append(job)
    return results
