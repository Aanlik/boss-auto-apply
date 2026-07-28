from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.services import feedback_store


router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class FeedbackPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    domain: str
    target_id: str = Field(default="", alias="targetId")
    useful: bool
    note: str = ""
    context: dict[str, Any] = Field(default_factory=dict)


@router.post("")
def record_feedback(payload: FeedbackPayload) -> dict[str, Any]:
    try:
        record = feedback_store.save_feedback(
            domain=payload.domain,
            target_id=payload.target_id,
            useful=payload.useful,
            note=payload.note,
            context=payload.context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"record": record}


@router.get("")
def get_feedback(domain: str = Query(default=""), target_id: str = Query(default="")) -> dict[str, Any]:
    return {"records": feedback_store.list_feedback(domain=domain, target_id=target_id)}


@router.get("/summary")
def get_feedback_summary() -> dict[str, Any]:
    return feedback_store.feedback_summary()


@router.get("/preference-profile")
def get_preference_profile() -> dict[str, Any]:
    return feedback_store.preference_profile()
