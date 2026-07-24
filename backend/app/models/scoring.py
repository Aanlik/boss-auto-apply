from pydantic import BaseModel


class ScoredJob(BaseModel):
    match_score: float = 0.0
    company_score: float = 0.0
    outlook_score: float = 0.0
    total_score: float = 0.0
