"""简历 PDF 生成器 — 支持长内容自然分页"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    Paragraph, Spacer, HRFlowable,
    BaseDocTemplate, Frame, PageTemplate,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── 跨平台中文字体自动发现 ──
import glob as _glob, platform as _platform

_FONT_CANDIDATES = {
    "ResumeSans": [
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "C:\\Windows\\Fonts\\msyh.ttc",
        "C:\\Windows\\Fonts\\simhei.ttf",
    ],
}

def _iter_font_candidates(candidates: list[str]):
    for path in candidates:
        for p in _glob.glob(path):
            if p:
                yield p
    search_dirs = []
    if _platform.system() == "Darwin":
        search_dirs = ["/System/Library/Fonts", "/Library/Fonts"]
    elif _platform.system() == "Linux":
        search_dirs = ["/usr/share/fonts", "/usr/local/share/fonts"]
    for d in search_dirs:
        for p in _glob.glob(f"{d}/**/*.ttf", recursive=True) + _glob.glob(f"{d}/**/*.ttc", recursive=True):
            yield p


def _register_first_available_font(name: str, candidates: list[str]) -> str:
    for path in _iter_font_candidates(candidates):
        try:
            pdfmetrics.registerFont(TTFont(name, path, subfontIndex=0))
            return path
        except Exception:
            continue
    raise RuntimeError("未找到可用中文字体")

_sans_path = _register_first_available_font("ResumeSans", _FONT_CANDIDATES["ResumeSans"])

F_H = "ResumeSans"
F_B = "ResumeSans"

C_PRIMARY = HexColor("#1f2937")
C_ACCENT  = HexColor("#0f766e")
C_BODY    = HexColor("#243041")
C_MUTED   = HexColor("#667085")
C_LINE    = HexColor("#d9e1ec")
C_WHITE   = HexColor("#ffffff")
C_SIDEBAR_BG = HexColor("#f3f6fb")
C_SIDEBAR_TEXT = HexColor("#263142")
C_SIDEBAR_MUTED = HexColor("#667085")
C_BG      = HexColor("#ffffff")

PDF_TEMPLATES = {
    "modern": {
        "name": "清爽续页",
        "description": "第一页双栏，第二页起单栏，留白更舒展，适合内容较多的岗位",
        "font": "ResumeSans",
        "density": "balanced",
        "bestFor": ["产品", "运营", "综合管理"],
        "layout": "first_page_sidebar",
    },
    "classic": {
        "name": "稳重双栏",
        "description": "每页保留左侧栏，层级清晰，适合一页简历或信息较少的岗位",
        "font": "ResumeSans",
        "density": "comfortable",
        "bestFor": ["管理", "市场", "HR"],
        "layout": "persistent_sidebar",
    },
    "ats": {
        "name": "ATS 单栏",
        "description": "纯单栏，减少装饰，适合系统筛选和文本读取",
        "font": "ResumeSans",
        "density": "compact",
        "bestFor": ["技术", "数据", "研发"],
        "layout": "single_column",
    },
}

DENSITY_PROFILES = {
    "comfortable": {"fontScale": 1.04, "leadingScale": 1.10, "spaceScale": 1.12, "marginScale": 1.04},
    "balanced": {"fontScale": 1.0, "leadingScale": 1.0, "spaceScale": 1.0, "marginScale": 1.0},
    "compact": {"fontScale": 0.94, "leadingScale": 0.90, "spaceScale": 0.86, "marginScale": 0.92},
}

PAGE_W, PAGE_H = A4
SIDEBAR_W = 58 * mm
MAIN_LEFT = SIDEBAR_W + 15 * mm
MAIN_RIGHT = 18 * mm
MAIN_TOP = 17 * mm
MAIN_BOTTOM = 16 * mm
MAIN_W = PAGE_W - MAIN_LEFT - MAIN_RIGHT
CONTINUATION_LEFT = 22 * mm
CONTINUATION_RIGHT = 22 * mm
CONTINUATION_W = PAGE_W - CONTINUATION_LEFT - CONTINUATION_RIGHT


def _density_options(density: str = "balanced") -> dict:
    return DENSITY_PROFILES.get(str(density or "balanced"), DENSITY_PROFILES["balanced"])


def _main_title(text, density: str = "balanced"):
    opts = _density_options(density)
    return Paragraph(text, ParagraphStyle(
        f"MTitle-{density}", fontName=F_H, fontSize=11.4 * opts["fontScale"], leading=18.5 * opts["leadingScale"],
        textColor=C_ACCENT, spaceBefore=13 * opts["spaceScale"], spaceAfter=6 * opts["spaceScale"],
        wordWrap="CJK"))


def _body_style(name, density: str = "balanced", **kwargs):
    opts = _density_options(density)
    defaults = {
        "fontName": F_B,
        "fontSize": 9.8 * opts["fontScale"],
        "leading": 18.2 * opts["leadingScale"],
        "textColor": C_BODY,
        "spaceAfter": 3 * opts["spaceScale"],
        "wordWrap": "CJK",
    }
    defaults.update(kwargs)
    return ParagraphStyle(name, **defaults)


def _build_main(profile, optimization, density: str = "balanced"):
    """构建右侧主内容（纯 flowable 列表）"""
    items = []
    opts = _density_options(density)

    # HR 栏：目标岗位
    title = profile.title or ""
    if title:
        items.append(Paragraph(
            f"<font color='#2b6cb0'>{title}</font>",
            ParagraphStyle(f"MTarget-{density}", fontName=F_H, fontSize=15.4 * opts["fontScale"], leading=22 * opts["leadingScale"],
                           textColor=C_ACCENT, spaceAfter=4 * opts["spaceScale"], wordWrap="CJK")))
        items.append(HRFlowable(width="100%", thickness=0.8, color=C_LINE, spaceAfter=11 * opts["spaceScale"]))

    # 个人总结
    summary = optimization.get("tailored_summary") or profile.summary or ""
    if summary:
        items.append(_main_title("个人总结", density))
        items.append(Paragraph(summary, ParagraphStyle(
            f"MSummary-{density}", fontName=F_B, fontSize=10 * opts["fontScale"], leading=17.8 * opts["leadingScale"],
            textColor=C_BODY, firstLineIndent=18, spaceAfter=11 * opts["spaceScale"],
            wordWrap="CJK")))

    # 工作经历
    opt_exp = optimization.get("work_experience") or []
    if opt_exp:
        items.append(_main_title("工作经历", density))
        for exp in opt_exp:
            d = exp if isinstance(exp, dict) else {
                "company": getattr(exp, "company", ""),
                "title": getattr(exp, "title", ""),
                "duration": getattr(exp, "duration", ""),
                "bullets": getattr(exp, "bullets", []),
            }
            h = f"<b>{d.get('title', '')}</b>"
            if d.get("company"):
                h += f" | {d['company']}"
            if d.get("duration"):
                h += f"  <font color='#777'>{d['duration']}</font>"
            items.append(Paragraph(h, ParagraphStyle(
                f"MExpH-{density}", fontName=F_H, fontSize=10.4 * opts["fontScale"], leading=17.8 * opts["leadingScale"],
                textColor=C_PRIMARY, spaceBefore=8 * opts["spaceScale"], spaceAfter=3 * opts["spaceScale"],
                wordWrap="CJK")))
            for b in (d.get("bullets") or []):
                if b and str(b).strip():
                    items.append(Paragraph(
                        f"- {str(b).strip()}",
                        _body_style("MBullet", density=density, leftIndent=16, spaceAfter=3 * opts["spaceScale"])))
            items.append(Spacer(1, 5 * opts["spaceScale"]))
    elif profile.work_experience:
        items.append(_main_title("工作经历", density))
        for e in profile.work_experience:
            h = f"<b>{e.title or ''}</b> | {e.company or ''}  <font color='#777'>{e.duration or ''}</font>"
            items.append(Paragraph(h, ParagraphStyle(
                f"MExpH-{density}", fontName=F_H, fontSize=10.5 * opts["fontScale"], leading=17.2 * opts["leadingScale"],
                textColor=C_PRIMARY, spaceBefore=7 * opts["spaceScale"], spaceAfter=3 * opts["spaceScale"],
                wordWrap="CJK")))
            if e.description:
                items.append(Paragraph(
                    f"- {e.description}",
                    _body_style("MBullet", density=density, leftIndent=16, spaceAfter=2 * opts["spaceScale"])))
            items.append(Spacer(1, 5 * opts["spaceScale"]))

    # 项目经历
    all_proj = (optimization.get("projects") or []) or (profile.projects or [])
    if all_proj:
        items.append(_main_title("项目经历", density))
        for proj in all_proj:
            d = proj if isinstance(proj, dict) else {
                "name": getattr(proj, "name", ""),
                "description": getattr(proj, "description", ""),
                "technologies": getattr(proj, "technologies", []),
            }
            tn = " / ".join(d.get("technologies") or [])
            h = f"<b>{d.get('name', '')}</b>"
            if tn:
                h += f"  <font color='#2b6cb0'>[{tn}]</font>"
            items.append(Paragraph(h, ParagraphStyle(
                f"MProjH-{density}", fontName=F_H, fontSize=10.5 * opts["fontScale"], leading=17.2 * opts["leadingScale"],
                textColor=C_PRIMARY, spaceBefore=7 * opts["spaceScale"], spaceAfter=3 * opts["spaceScale"],
                wordWrap="CJK")))
            if d.get("description"):
                items.append(Paragraph(
                    d["description"],
                    _body_style("MProjD", density=density, leftIndent=16, spaceAfter=5 * opts["spaceScale"])))

    return items


def _wrap_text(text, width, font_name, font_size):
    lines = []
    line = ""
    for char in str(text or "").replace("\n", " "):
        candidate = line + char
        if pdfmetrics.stringWidth(candidate, font_name, font_size) <= width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = char
    if line:
        lines.append(line)
    return lines


def _draw_wrapped(canvas, text, x, y, width, font_name, font_size, leading, color, max_lines=None):
    canvas.setFillColor(color)
    canvas.setFont(font_name, font_size)
    lines = _wrap_text(text, width, font_name, font_size)
    if max_lines:
        lines = lines[:max_lines]
    for line in lines:
        if y < 18 * mm:
            break
        canvas.drawString(x, y, line)
        y -= leading
    return y


def _draw_sidebar_title(canvas, text, x, y, width):
    canvas.setFillColor(C_ACCENT)
    canvas.setFont(F_H, 8.4)
    canvas.drawString(x, y, text)
    canvas.setStrokeColor(C_LINE)
    canvas.setLineWidth(0.35)
    canvas.line(x, y - 2.5 * mm, x + width, y - 2.5 * mm)
    return y - 6.5 * mm


def _draw_sidebar(canvas, doc, profile, optimization):
    canvas.saveState()
    canvas.setFillColor(C_BG)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(C_SIDEBAR_BG)
    canvas.rect(0, 0, SIDEBAR_W, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(C_ACCENT)
    canvas.rect(0, 0, 2.4 * mm, PAGE_H, fill=1, stroke=0)

    x = 8.5 * mm
    width = SIDEBAR_W - 15 * mm
    y = PAGE_H - 19 * mm

    y = _draw_wrapped(canvas, profile.name or "姓名", x, y, width, F_H, 19, 7 * mm, C_PRIMARY, max_lines=2)
    if profile.title:
        y -= 0.6 * mm
        y = _draw_wrapped(canvas, profile.title, x, y, width, F_B, 9.3, 4.8 * mm, C_MUTED, max_lines=2)

    y -= 7 * mm
    y = _draw_sidebar_title(canvas, "联系方式", x, y, width)
    contacts = []
    if profile.phone:
        contacts.append(f"电话 {profile.phone}")
    if profile.email:
        contacts.append(f"邮箱 {profile.email}")
    if profile.location:
        contacts.append(f"城市 {profile.location}")
    if profile.gender:
        contacts.append(f"性别 {profile.gender}")
    if profile.birth:
        contacts.append(f"出生 {profile.birth}")
    for contact in contacts or ["联系方式待补充"]:
        y = _draw_wrapped(canvas, contact, x, y, width, F_B, 7.9, 4.1 * mm, C_SIDEBAR_TEXT, max_lines=2)

    skills = optimization.get("skills_display") or profile.skills or []
    if skills:
        y -= 5 * mm
        y = _draw_sidebar_title(canvas, "专业技能", x, y, width)
        for skill in skills[:14]:
            y = _draw_wrapped(canvas, f"- {skill}", x, y, width, F_B, 8, 4.2 * mm, C_SIDEBAR_TEXT, max_lines=2)

    if profile.education:
        y -= 5 * mm
        y = _draw_sidebar_title(canvas, "教育背景", x, y, width)
        for edu in profile.education[:3]:
            school = getattr(edu, "institution", "") or ""
            degree = " ".join(
                part for part in [
                    getattr(edu, "degree", "") or "",
                    getattr(edu, "major", "") or "",
                ] if part
            )
            graduation = getattr(edu, "graduation", "") or ""
            if school:
                y = _draw_wrapped(canvas, school, x, y, width, F_H, 8.2, 4.3 * mm, C_SIDEBAR_TEXT, max_lines=2)
            if degree:
                y = _draw_wrapped(canvas, degree, x, y, width, F_B, 7.7, 4 * mm, C_SIDEBAR_MUTED, max_lines=2)
            if graduation:
                y = _draw_wrapped(canvas, graduation, x, y, width, F_B, 7.5, 3.8 * mm, C_SIDEBAR_MUTED, max_lines=1)
            y -= 2 * mm

    canvas.setFillColor(C_MUTED)
    canvas.setFont(F_B, 7.2)
    canvas.drawString(x, 10 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def _draw_continuation_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(C_BG)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setStrokeColor(C_LINE)
    canvas.setLineWidth(0.35)
    canvas.line(CONTINUATION_LEFT, PAGE_H - 13 * mm, PAGE_W - CONTINUATION_RIGHT, PAGE_H - 13 * mm)
    canvas.setFillColor(C_MUTED)
    canvas.setFont(F_B, 7.2)
    canvas.drawRightString(PAGE_W - CONTINUATION_RIGHT, 10 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def export_resume_pdf(profile, optimization: dict, company: str, job_title: str, template: str = "modern", density: str = "balanced") -> bytes:
    """生成可自然分页的专业双栏 PDF 简历。"""
    buf = io.BytesIO()
    template = template if template in PDF_TEMPLATES else "modern"
    density = density if density in DENSITY_PROFILES else PDF_TEMPLATES[template]["density"]
    density_opts = _density_options(density)

    main_items = _build_main(profile, optimization or {}, density=density)
    if not main_items:
        main_items = [Paragraph("暂无简历内容", _body_style("Empty", density=density))]

    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=0, rightMargin=0,
        topMargin=0, bottomMargin=0,
        title=f"{profile.name or ''} 简历.pdf",
    )
    first_frame = Frame(
        MAIN_LEFT, MAIN_BOTTOM * density_opts["marginScale"], MAIN_W, PAGE_H - MAIN_TOP * density_opts["marginScale"] - MAIN_BOTTOM * density_opts["marginScale"],
        id="main", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    continuation_frame = Frame(
        CONTINUATION_LEFT, MAIN_BOTTOM * density_opts["marginScale"], CONTINUATION_W, PAGE_H - MAIN_TOP * density_opts["marginScale"] - MAIN_BOTTOM * density_opts["marginScale"],
        id="continuation", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    if template == "classic":
        doc.addPageTemplates([
            PageTemplate(
                id="ResumeTemplate",
                frames=[first_frame],
                onPage=lambda canvas, current_doc: _draw_sidebar(canvas, current_doc, profile, optimization or {}),
            )
        ])
    elif template == "ats":
        doc.addPageTemplates([
            PageTemplate(
                id="ResumeTemplate",
                frames=[continuation_frame],
                onPage=_draw_continuation_page,
            )
        ])
    else:
        doc.addPageTemplates([
            PageTemplate(
                id="ResumeTemplate",
                frames=[first_frame],
                onPage=lambda canvas, current_doc: _draw_sidebar(canvas, current_doc, profile, optimization or {}),
                autoNextPageTemplate="ResumeContinuation",
            ),
            PageTemplate(
                id="ResumeContinuation",
                frames=[continuation_frame],
                onPage=_draw_continuation_page,
            ),
        ])
    doc.build(main_items)
    buf.seek(0)
    return buf.getvalue()
    opts = _density_options(density)
