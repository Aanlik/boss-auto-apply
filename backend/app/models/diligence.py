from pydantic import BaseModel


class CompanyDiligence(BaseModel):
    risk: str = "unknown"
    outlook: str = "unknown"
    summary: str = ""
