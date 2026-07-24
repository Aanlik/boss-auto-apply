from app.models.scoring import ScoredJob


def job_match_score(job: dict, resume: dict) -> float:
    title = (job.get("title") or "").lower()
    skills = [skill.lower() for skill in resume.get("skills", [])]
    if not skills:
        return 0.0
    hits = sum(1 for skill in skills if skill in title)
    return min(1.0, hits / max(1, len(skills)))


def company_quality_score(diligence: dict) -> float:
    risk = diligence.get("risk", "unknown")
    if risk == "low":
        return 0.9
    if risk == "medium":
        return 0.6
    if risk == "high":
        return 0.2
    return 0.5


def outlook_score(diligence: dict) -> float:
    outlook = diligence.get("outlook", "unknown")
    if outlook == "positive":
        return 0.9
    if outlook == "neutral":
        return 0.6
    if outlook == "unknown":
        return 0.4
    return 0.5


def score_job(job: dict, resume: dict, diligence: dict | None = None) -> ScoredJob:
    diligence = diligence or {}
    match = job_match_score(job, resume)
    company = company_quality_score(diligence)
    outlook = outlook_score(diligence)
    total = match * 0.4 + company * 0.3 + outlook * 0.3
    return ScoredJob(
        match_score=match,
        company_score=company,
        outlook_score=outlook,
        total_score=total,
    )


def rank_jobs(jobs: list[dict], resume: dict, diligences: dict[str, dict] | None = None) -> list[dict]:
    diligences = diligences or {}
    scored_jobs: list[dict] = []
    for job in jobs:
        company_name = job.get("company", "")
        scored = score_job(job, resume, diligences.get(company_name, {}))
        scored_jobs.append(
            {
                **job,
                "match_score": scored.match_score,
                "company_score": scored.company_score,
                "outlook_score": scored.outlook_score,
                "total_score": scored.total_score,
            }
        )
    return sorted(scored_jobs, key=lambda item: item["total_score"], reverse=True)
