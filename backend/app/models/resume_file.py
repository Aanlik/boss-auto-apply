from pydantic import BaseModel


class ResumeFile(BaseModel):
    filename: str
    content_type: str | None = None
    raw_text: str = ""
