from fastapi import APIRouter, HTTPException

from app.services.workflow_persistence import (
    load_greetings,
    load_send_records,
    save_greetings,
    save_send_record,
)


router = APIRouter(prefix="/api/greetings", tags=["greetings"])


@router.get("/drafts")
def get_greeting_drafts() -> dict:
    return {"greetings": load_greetings()}


@router.post("/drafts")
def save_greeting_drafts(payload: dict) -> dict:
    greetings = payload.get("greetings", {})
    if not isinstance(greetings, dict):
        raise HTTPException(status_code=400, detail="greetings 必须是对象")
    return {"greetings": save_greetings({str(k): str(v) for k, v in greetings.items()})}


@router.get("/send-records")
def get_send_records() -> dict:
    return {"records": load_send_records()}


@router.post("/send-records")
def confirm_send_record(payload: dict) -> dict:
    job_id = str(payload.get("job_id", "")).strip()
    status = str(payload.get("status", "sent")).strip() or "sent"
    note = str(payload.get("note", "")).strip()
    if not job_id:
        raise HTTPException(status_code=400, detail="缺少 job_id")
    return {"record": save_send_record(job_id, status, note)}
