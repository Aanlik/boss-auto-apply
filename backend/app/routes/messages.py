from fastapi import APIRouter

from app.services.message_generator import build_message_draft, revise_greeting

router = APIRouter(prefix="/api/messages", tags=["messages"])


@router.post("/draft")
def draft_message(payload: dict) -> dict:
    return build_message_draft(
        payload.get("job_title", ""),
        payload.get("resume_summary", ""),
        payload.get("company_summary", ""),
    ).model_dump()


@router.post("/revise")
def revise_message(payload: dict) -> dict:
    return {"draft": revise_greeting(payload.get("draft", ""), payload.get("edit_hint", ""))}
