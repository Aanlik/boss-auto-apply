from app.services.company_diligence import score_company


def test_score_company_returns_risk_and_outlook():
    result = score_company({"name": "某公司", "industry": "AI 增长", "description": "业务扩张中"})
    assert result.risk in {"low", "medium", "high"}
    assert result.outlook in {"unknown", "neutral", "positive"}
    assert result.summary.startswith("某公司")
