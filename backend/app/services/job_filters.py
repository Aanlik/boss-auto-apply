import re
from app.models.job import JobRecord, JobFilter


def salary_floor(salary: str) -> int:
    match = re.search(r"(\d+)", salary or "")
    return int(match.group(1)) if match else 0


def match_job_filters(job: dict, keywords: list[str], city: str, min_salary: int = 0) -> bool:
    """兼容旧版 dict-based 过滤。"""
    title = (job.get("title") or "").lower()
    job_city = job.get("city") or ""
    salary = salary_floor(job.get("salary") or "")

    if keywords and not any(keyword.lower() in title for keyword in keywords):
        return False
    if city and job_city != city:
        return False
    if min_salary and salary < min_salary:
        return False
    return True


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
