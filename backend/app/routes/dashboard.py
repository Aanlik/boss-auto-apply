from __future__ import annotations

from fastapi import APIRouter

from app.services.maintenance_service import data_quality_center, dashboard_summary, onboarding_guide, onboarding_wizard, repair_data_quality, review_center, trend_report, weekly_report


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_dashboard_summary(selected_job_ids: str | None = None) -> dict:
    job_ids = None if selected_job_ids is None else [job_id for job_id in selected_job_ids.split(",") if job_id]
    return dashboard_summary(job_ids)


@router.get("/onboarding")
def get_onboarding_guide(selected_job_ids: str | None = None) -> dict:
    job_ids = None if selected_job_ids is None else [job_id for job_id in selected_job_ids.split(",") if job_id]
    return onboarding_guide(job_ids)


@router.get("/onboarding/wizard")
def get_onboarding_wizard() -> dict:
    return onboarding_wizard()


@router.get("/review-center")
def get_review_center() -> dict:
    return review_center()


@router.get("/weekly-report")
def get_weekly_report(days: int = 7) -> dict:
    return weekly_report(days=days)


@router.get("/trends")
def get_trends(days: int = 30) -> dict:
    return trend_report(days=days)


@router.get("/data-quality")
def get_data_quality_center(selected_job_ids: str | None = None) -> dict:
    job_ids = None if selected_job_ids is None else [job_id for job_id in selected_job_ids.split(",") if job_id]
    return data_quality_center(job_ids)


@router.post("/data-quality/repair")
def repair_data_quality_center(payload: dict) -> dict:
    actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
    return repair_data_quality([str(item) for item in actions])
