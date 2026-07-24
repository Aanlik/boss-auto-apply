from fastapi import APIRouter

from app.services.scoring import rank_jobs, score_job

router = APIRouter(prefix="/api/scoring", tags=["scoring"])


@router.post("/score")
def score_job_endpoint(payload: dict) -> dict:
    job = payload.get("job", {})
    resume = payload.get("resume", {})
    diligence = payload.get("diligence", {})
    scored = score_job(job, resume, diligence)
    return scored.model_dump()


@router.post("/rank")
def rank_jobs_endpoint(payload: dict) -> dict:
    jobs = payload.get("jobs", [])
    resume = payload.get("resume", {})
    diligences = payload.get("diligences", {})
    return {"jobs": rank_jobs(jobs, resume, diligences)}
