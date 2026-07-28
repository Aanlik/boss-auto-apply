from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

from app.services.resume_pdf_exporter import F_B, F_H


def _style(name: str, **kwargs) -> ParagraphStyle:
    defaults = {
        "fontName": F_B,
        "fontSize": 10,
        "leading": 16.8,
        "textColor": HexColor("#243041"),
        "wordWrap": "CJK",
        "spaceAfter": 7,
    }
    defaults.update(kwargs)
    return ParagraphStyle(name, **defaults)


def export_deep_report_pdf(record: dict) -> bytes:
    result = record.get("result") if isinstance(record.get("result"), dict) else {}
    strategy = result.get("strategy") if isinstance(result.get("strategy"), dict) else {}
    jd_quality = result.get("jdQuality") if isinstance(result.get("jdQuality"), dict) else {}
    risk = result.get("risk") if isinstance(result.get("risk"), dict) else {}
    ai_report = result.get("aiReport") if isinstance(result.get("aiReport"), dict) else {}
    manual = result.get("manualReport") if isinstance(result.get("manualReport"), dict) else {}
    manual_sections = manual.get("sections") if isinstance(manual.get("sections"), dict) else {}
    signals = result.get("preferenceSignals") if isinstance(result.get("preferenceSignals"), list) else []

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"{record.get('company') or ''} 求职深度报告",
    )
    company = escape(str(record.get("company") or "未命名公司"))
    title = escape(str(record.get("title") or "未命名岗位"))
    story = [
        Paragraph("求职深度报告", _style("Title", fontName=F_H, fontSize=21, leading=29, textColor=HexColor("#0f766e"), spaceAfter=4)),
        Paragraph(
            f"<font color='#0f172a'><b>{company}</b></font>　{title}",
            _style("Meta", fontSize=10.3, leading=18, textColor=HexColor("#667085"), spaceAfter=8),
        ),
        HRFlowable(width="100%", thickness=0.75, color=HexColor("#d9e1ec"), spaceAfter=8),
    ]
    sections = [
        ("结论摘要", manual_sections.get("summary") or manual.get("summary") or ai_report.get("summary") or strategy.get("reason") or "暂无总结。"),
        ("投递策略", manual_sections.get("strategy") or f"建议：{strategy.get('strategy') or '待判断'}；置信度：{strategy.get('confidence', '未知')}"),
        ("JD 质量", manual_sections.get("match") or f"质量分：{jd_quality.get('qualityScore', '未知')}；噪音等级：{jd_quality.get('noiseLevel', '未知')}"),
        ("风险提示", manual_sections.get("risk") or risk.get("plainLanguage") or f"风险等级：{risk.get('riskLevel', '未知')}"),
        ("面试准备", manual_sections.get("interview") or "暂无人工补充。"),
        ("行动建议", manual_sections.get("actions") or "暂无人工补充。"),
        ("个人偏好命中", "；".join(str(item) for item in signals) or "暂无明显偏好命中。"),
    ]
    for title, body in sections:
        story.append(Paragraph(escape(title), _style(f"{title}Heading", fontName=F_H, fontSize=12.4, leading=19, textColor=HexColor("#0f766e"), spaceBefore=9, spaceAfter=4)))
        story.append(Paragraph(escape(str(body)).replace("\n", "<br/>"), _style(f"{title}Body")))
        story.append(Spacer(1, 2.3 * mm))
    doc.build(story)
    return buf.getvalue()
