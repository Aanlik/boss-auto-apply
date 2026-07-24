from pydantic import BaseModel, Field


class CompanyDiligenceResult(BaseModel):
    risk: str = "unknown"
    outlook: str = "unknown"
    summary: str = ""
    evidence: list[str] = Field(default_factory=list)
