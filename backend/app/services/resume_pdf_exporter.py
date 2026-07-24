"""简历 PDF 生成器 — JadeAI 风格双栏模板，专业排版"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

pdfmetrics.registerFont(TTFont("Heiti", "/System/Library/Fonts/STHeiti Medium.ttc", subfontIndex=0))
pdfmetrics.registerFont(TTFont("Songti", "/System/Library/Fonts/Supplemental/Songti.ttc", subfontIndex=0))

F_H = "Heiti"    # 标题
F_B = "Songti"   # 正文

C_PRIMARY = HexColor("#1e3a5f")   # 深蓝主色
C_ACCENT  = HexColor("#2b6cb0")   # 亮蓝强调
C_BG      = HexColor("#f0f4f8")   # 侧栏底色
C_DARK    = HexColor("#1a1a1a")
C_BODY    = HexColor("#333333")
C_MUTED   = HexColor("#777777")
C_LINE    = HexColor("#d0d5dd")
C_WHITE   = HexColor("#ffffff")

PAGE_W, PAGE_H = A4
SIDEBAR_W = 72*mm


def export_resume_pdf(profile, optimization: dict, company: str, job_title: str) -> bytes:
    buf = io.BytesIO()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=0, rightMargin=0,
                            topMargin=0, bottomMargin=0,
                            title=f"{profile.name or ''} 简历.pdf")

    story = []

    # ═══════ 双栏布局：左侧主内容 + 右侧技能/信息栏 ═══════
    main_data = []
    sidebar_data = []

    name = profile.name or "姓名"

    # ── 侧栏 ──
    sidebar_data.append(Spacer(1, 22*mm))
    sidebar_data.append(Paragraph(name, ParagraphStyle(
        "SideName", fontName=F_H, fontSize=18, leading=24, textColor=C_WHITE, spaceAfter=6)))
    sidebar_data.append(HRFlowable(width="60%", thickness=1.5, color=C_ACCENT, spaceAfter=10))

    # 联系方式
    contacts = []
    if hasattr(profile, 'phone') and profile.phone:
        contacts.append(("📞", profile.phone))
    if hasattr(profile, 'email') and profile.email:
        contacts.append(("✉", profile.email))
    if hasattr(profile, 'location') and profile.location:
        contacts.append(("📍", profile.location))
    if hasattr(profile, 'birth') and profile.birth:
        contacts.append(("🎂", profile.birth))
    if hasattr(profile, 'gender') and profile.gender:
        contacts.append(("👤", profile.gender))

    if contacts:
        sidebar_data.append(_side_title("联系方式"))
        for icon, val in contacts:
            sidebar_data.append(Paragraph(f"{icon} <font color='#c0d0e0'>{val}</font>",
                ParagraphStyle("SContact", fontName=F_B, fontSize=8.5, leading=14, textColor=C_WHITE, spaceAfter=2)))

    # 技能
    skills = optimization.get("skills_display") or profile.skills or []
    if skills:
        sidebar_data.append(Spacer(1, 6))
        sidebar_data.append(_side_title("专业技能"))
        for s in skills[:12]:
            sidebar_data.append(Paragraph(f"▸ {s}",
                ParagraphStyle("SSkill", fontName=F_B, fontSize=9, leading=15, textColor=C_WHITE, spaceAfter=1)))

    # 教育
    if profile.education:
        sidebar_data.append(Spacer(1, 6))
        sidebar_data.append(_side_title("教育背景"))
        for edu in profile.education:
            sidebar_data.append(Paragraph(edu.institution or "",
                ParagraphStyle("SEdu1", fontName=F_H, fontSize=9, leading=14, textColor=C_WHITE, spaceAfter=1)))
            parts = [p for p in [edu.degree, edu.major, edu.graduation] if p]
            if parts:
                sidebar_data.append(Paragraph("<font color='#b0c4de'>" + " · ".join(parts) + "</font>",
                    ParagraphStyle("SEdu2", fontName=F_B, fontSize=8, leading=12, textColor=HexColor("#b0c4de"), spaceAfter=4)))

    # ── 主内容区 ──
    main_data.append(Spacer(1, 20*mm))
    main_data.append(Paragraph(name, ParagraphStyle(
        "MName", fontName=F_H, fontSize=26, leading=32, textColor=C_PRIMARY, spaceAfter=2)))
    if job_title:
        main_data.append(Paragraph(f"求职意向：{job_title}",
            ParagraphStyle("MTitle", fontName=F_H, fontSize=12, leading=18, textColor=C_ACCENT, spaceAfter=4)))
    main_data.append(HRFlowable(width="100%", thickness=1.2, color=C_PRIMARY, spaceAfter=10))

    # 个人总结
    summary = optimization.get("tailored_summary") or profile.summary or ""
    if summary:
        main_data.append(_main_title("个人总结"))
        main_data.append(Paragraph(summary, ParagraphStyle(
            "MSummary", fontName=F_B, fontSize=10.5, leading=18, textColor=C_BODY, firstLineIndent=21, spaceAfter=10)))

    # 工作经历
    opt_exp = optimization.get("work_experience") or []
    if opt_exp:
        main_data.append(_main_title("工作经历"))
        for exp in opt_exp:
            d = exp if isinstance(exp, dict) else {"company": getattr(exp,"company",""), "title": getattr(exp,"title",""), "duration": getattr(exp,"duration",""), "bullets": getattr(exp,"bullets",[])}
            h = f"<b>{d.get('title','')}</b>"
            if d.get('company'):
                h += f" ｜ {d['company']}"
            if d.get('duration'):
                h += f"  <font color='#777'>{d['duration']}</font>"
            main_data.append(Paragraph(h, ParagraphStyle("MExpH", fontName=F_H, fontSize=11, leading=18, textColor=C_PRIMARY, spaceBefore=8, spaceAfter=3)))
            for b in (d.get('bullets') or []):
                if b and str(b).strip():
                    main_data.append(Paragraph(f"• {str(b).strip()}",
                        ParagraphStyle("MBullet", fontName=F_B, fontSize=10, leading=17, textColor=C_BODY, leftIndent=16, spaceAfter=2)))
            main_data.append(Spacer(1, 4))
    elif profile.work_experience:
        main_data.append(_main_title("工作经历"))
        for e in profile.work_experience:
            h = f"<b>{e.title or ''}</b> ｜ {e.company or ''}  <font color='#777'>{e.duration or ''}</font>"
            main_data.append(Paragraph(h, ParagraphStyle("MExpH", fontName=F_H, fontSize=11, leading=18, textColor=C_PRIMARY, spaceBefore=6, spaceAfter=3)))
            if e.description:
                main_data.append(Paragraph(f"• {e.description}", ParagraphStyle("MBullet", fontName=F_B, fontSize=10, leading=17, textColor=C_BODY, leftIndent=16, spaceAfter=2)))
            main_data.append(Spacer(1, 4))

    # 项目经历
    all_proj = (optimization.get("projects") or []) or (profile.projects or [])
    if all_proj:
        main_data.append(_main_title("项目经历"))
        for proj in all_proj:
            d = proj if isinstance(proj, dict) else {"name": getattr(proj,"name",""), "description": getattr(proj,"description",""), "technologies": getattr(proj,"technologies",[])}
            tn = " · ".join(d.get('technologies') or [])
            h = f"<b>{d.get('name','')}</b>"
            if tn:
                h += f"  <font color='#2b6cb0'>[{tn}]</font>"
            main_data.append(Paragraph(h, ParagraphStyle("MProjH", fontName=F_H, fontSize=11, leading=18, textColor=C_PRIMARY, spaceBefore=6, spaceAfter=3)))
            if d.get('description'):
                main_data.append(Paragraph(d['description'], ParagraphStyle("MProjD", fontName=F_B, fontSize=10, leading=17, textColor=C_BODY, leftIndent=16, spaceAfter=4)))

    # ═══════ 构建双栏表格 ═══════
    sidebar_height = max(len(sidebar_data) * 18, 600)
    main_height = max(len(main_data) * 18, 600)

    sidebar_cell = Table([[sidebar_data]], colWidths=[SIDEBAR_W], rowHeights=[sidebar_height])
    sidebar_cell.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), C_PRIMARY),
        ("LEFTPADDING", (0,0), (-1,-1), 8*mm),
        ("RIGHTPADDING", (0,0), (-1,-1), 4*mm),
        ("TOPPADDING", (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))

    main_cell = Table([[main_data]], colWidths=[PAGE_W - SIDEBAR_W], rowHeights=[main_height])
    main_cell.setStyle(TableStyle([
        ("LEFTPADDING", (0,0), (-1,-1), 10*mm),
        ("RIGHTPADDING", (0,0), (-1,-1), 10*mm),
        ("TOPPADDING", (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))

    full_table = Table([[sidebar_cell, main_cell]], colWidths=[SIDEBAR_W, PAGE_W - SIDEBAR_W])
    full_table.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING", (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    story.append(full_table)

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def _side_title(text):
    return Paragraph(text, ParagraphStyle("STitle", fontName=F_H, fontSize=10.5, leading=16,
                                           textColor=C_WHITE, spaceBefore=8, spaceAfter=4,
                                           borderPadding=(0,0,2,0)))


def _main_title(text):
    return Paragraph(text, ParagraphStyle("MTitle", fontName=F_H, fontSize=13, leading=20,
                                           textColor=C_PRIMARY, spaceBefore=12, spaceAfter=6))
