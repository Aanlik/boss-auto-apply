from fastapi import APIRouter

from app.services.send_flow import build_inbox_item, confirm_send

router = APIRouter(prefix="/api/send-inbox", tags=["send-inbox"])


@router.post("/build")
def build_inbox(payload: dict) -> dict:
    jobs = payload.get("jobs", [])
    return {"items": [build_inbox_item(job).model_dump() for job in jobs]}


@router.post("/confirm")
def confirm(payload: dict) -> dict:
    return confirm_send(payload.get("job", {})).model_dump()
