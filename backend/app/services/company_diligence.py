from app.models.company_diligence import CompanyDiligenceResult


def score_company(company: dict) -> CompanyDiligenceResult:
    name = company.get("name", "公司")
    industry = (company.get("industry") or "").lower()
    description = (company.get("description") or "").lower()
    evidence: list[str] = []
    risk_score = 0
    outlook_score = 0

    risky_words = ["裁员", "倒闭", "欠薪", "诈骗", "纠纷", "风险"]
    positive_words = ["增长", "融资", "头部", "盈利", "扩张", "上升"]

    for word in risky_words:
        if word in description or word in industry:
            risk_score += 1
            evidence.append(f"命中风险词: {word}")

    for word in positive_words:
        if word in description or word in industry:
            outlook_score += 1
            evidence.append(f"命中积极词: {word}")

    risk = "high" if risk_score >= 2 else "medium" if risk_score == 1 else "low"
    outlook = "positive" if outlook_score >= 2 else "neutral" if outlook_score == 1 else "unknown"
    summary = f"{name} 风险={risk}，行业前景={outlook}。"
    return CompanyDiligenceResult(risk=risk, outlook=outlook, summary=summary, evidence=evidence)
