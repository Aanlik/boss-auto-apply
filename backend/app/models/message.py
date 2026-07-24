from pydantic import BaseModel


class MessageDraft(BaseModel):
    job_title: str = ""
    draft: str = ""
