from fastapi import APIRouter

from app.services.company_diligence import score_company

router = APIRouter(prefix="/api/diligence", tags=["diligence"])


@router.post("/evaluate")
def evaluate_company(payload: dict) -> dict:
    result = score_company(payload)
    return result.model_dump()
