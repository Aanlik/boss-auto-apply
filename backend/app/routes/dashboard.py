from fastapi import APIRouter

from app.services.maintenance_service import data_quality_center, dashboard_summary, onboarding_guide, onboarding_wizard, repair_data_quality, review_center, trend_report, weekly_report


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_dashboard_summary() -> dict:
    return dashboard_summary()


@router.get("/onboarding")
def get_onboarding_guide() -> dict:
    return onboarding_guide()


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
def get_data_quality_center() -> dict:
    return data_quality_center()


@router.post("/data-quality/repair")
def repair_data_quality_center(payload: dict) -> dict:
    actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
    return repair_data_quality([str(item) for item in actions])
