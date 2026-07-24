from pydantic import BaseModel


class SendRecord(BaseModel):
    job_title: str
    company: str
    manual_confirmed: bool = False
    status: str = "pending"
    note: str = ""


class SendInboxItem(BaseModel):
    job_title: str
    company: str
    draft: str = ""
    manual_confirmed: bool = False
    status: str = "pending"
    note: str = ""
