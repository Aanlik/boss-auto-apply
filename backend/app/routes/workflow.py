from fastapi import APIRouter

from app.services import workflow_tasks


router = APIRouter(prefix="/api/workflow", tags=["workflow"])


@router.get("/tasks")
def list_workflow_tasks() -> dict:
    return {"tasks": workflow_tasks.load_tasks()}
