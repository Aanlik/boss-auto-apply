from app.services.company_diligence import run_full_diligence, _compute_company_score


def test_compute_company_score_returns_valid_range():
    """Verifies company score computation returns valid range and risk level."""
    info = {"scale": "500人", "funding": "B轮", "business": "互联网", "tech_stack": []}
    sentiment = {"positive_signals": [], "negative_signals": [], "employee_feedback": "", "legal_risks": []}
    industry = {"trend": "上升期", "policy": "政策支持", "market_space": "百亿", "risks": []}
    recruitment = {"requiredSkillsCount": 5}
    
    score, risk = _compute_company_score(info, sentiment, industry, recruitment)
    assert 0 <= score <= 100
    assert risk in ("low", "medium", "high")


def test_run_full_diligence_includes_business_info(monkeypatch):
    import app.services.company_diligence as diligence

    async def fake_company_info(company_name):
        return {
            "scale": "500人",
            "funding": "B轮",
            "founded": "2015",
            "business": "护肤电商",
            "tech_stack": [],
            "evidence_links": [],
        }

    async def fake_sentiment(company_name):
        return {
            "positive_signals": ["增长稳定"],
            "negative_signals": [],
            "employee_feedback": "",
            "legal_risks": [],
            "evidence_links": [],
        }

    observed = {}

    async def fake_industry(company_name, business):
        observed["business"] = business
        return {
            "industry": business,
            "trend": "上升期",
            "policy": "政策支持",
            "market_space": "百亿",
            "risks": [],
            "evidence_links": [],
        }

    async def fake_business_info(company_name):
        return {
            "companyName": "示例科技有限公司",
            "legalRepresentative": "张三",
            "registrationCapital": "1000万人民币",
            "businessStatus": "存续",
            "industry": "批发和零售业",
            "subIndustry": "互联网零售",
            "registeredIndustry": "批发和零售业",
            "registeredSubIndustry": "互联网零售",
            "abnormalInfo": [],
            "penalties": [],
        }

    monkeypatch.setattr(diligence, "search_company_info", fake_company_info)
    monkeypatch.setattr(diligence, "search_company_sentiment", fake_sentiment)
    monkeypatch.setattr(diligence, "search_industry_outlook", fake_industry)
    monkeypatch.setattr(diligence, "query_business_info", fake_business_info)
    monkeypatch.setattr(diligence, "get_ai_client", lambda: None)

    import asyncio
    report = asyncio.run(run_full_diligence("示例科技有限公司", jd_text="岗位职责：负责HRBP。"))

    assert report["companyName"] == "示例科技有限公司"
    assert report["businessInfo"]["businessStatus"] == "存续"
    assert observed["business"] == "批发和零售业 / 互联网零售"
    assert report["industryOutlook"]["industry"] == "批发和零售业 / 互联网零售"
    assert report["companyScore"] >= 50


def test_company_score_penalizes_enterprise_risk_signals():
    info = {"scale": "500人", "funding": "B轮", "business": "互联网", "tech_stack": []}
    sentiment = {"positive_signals": [], "negative_signals": [], "employee_feedback": "", "legal_risks": []}
    industry = {"trend": "上升期", "policy": "政策支持", "market_space": "百亿", "risks": []}
    recruitment = {"requiredSkillsCount": 5}

    clean_score, _ = _compute_company_score(info, sentiment, industry, recruitment, {
        "businessStatus": "存续",
        "abnormalInfo": [],
        "penalties": [],
        "dishonestCount": 0,
        "enforcedCount": 0,
    })
    risky_score, risk = _compute_company_score(info, sentiment, industry, recruitment, {
        "businessStatus": "存续",
        "abnormalInfo": ["未按规定公示年度报告"],
        "penalties": ["罚款"],
        "dishonestCount": 1,
        "enforcedCount": 1,
    })

    assert risky_score < clean_score
    assert risk in ("medium", "high")


def test_evaluate_company_returns_saved_report_before_running_new_diligence(monkeypatch):
    import asyncio
    import app.routes.diligence as diligence_route

    cached = {
        "companyName": "示例科技有限公司",
        "sourceCompanyName": "示例科技",
        "companyKey": "credit-1",
        "companyScore": 82,
        "riskLevel": "low",
    }
    monkeypatch.setattr(diligence_route, "find_diligence_report", lambda _: cached)

    async def should_not_run(**kwargs):
        raise AssertionError("已有报告时不应重新执行全量尽调")

    monkeypatch.setattr(diligence_route, "run_full_diligence", should_not_run)

    result = asyncio.run(diligence_route.evaluate_company({"company_name": "示例科技"}))

    assert result["companyScore"] == 82
    assert result["cacheHit"] is True
