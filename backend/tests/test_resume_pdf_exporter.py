from app.models.resume import Education, ResumeProfile, WorkExperience
from app.services import resume_pdf_exporter
from app.services.resume_pdf_exporter import export_resume_pdf


def test_export_resume_pdf_handles_long_optimized_resume():
    profile = ResumeProfile(
        name="张三",
        title="高级产品经理",
        phone="13800000000",
        email="zhangsan@example.com",
        location="郑州",
        summary="负责复杂业务平台从 0 到 1 建设，擅长用户增长、商业化和跨团队协作。" * 8,
        skills=[f"技能{i}" for i in range(30)],
        education=[Education(institution="郑州大学", degree="本科", major="计算机科学", graduation="2015")],
        work_experience=[
            WorkExperience(
                company="示例科技有限公司",
                title="高级产品经理",
                duration="2020-至今",
                description="负责电商、CRM、数据中台、营销自动化等多个系统建设。" * 12,
            )
        ],
    )
    long_bullets = [
        f"负责第 {i} 个复杂业务模块的产品规划、需求拆解、跨部门推进、上线复盘和指标优化，沉淀可复用方法论。"
        for i in range(45)
    ]
    optimization = {
        "tailored_summary": "面向目标岗位重写后的个人总结。" * 20,
        "skills_display": [f"技能{i}" for i in range(30)],
        "work_experience": [{
            "company": "示例科技有限公司",
            "title": "高级产品经理",
            "duration": "2020-至今",
            "bullets": long_bullets,
        }],
        "projects": [{
            "name": "业务增长平台",
            "description": "覆盖线索、转化、复购、会员和数据看板的复杂项目。" * 18,
            "technologies": ["数据分析", "CRM", "增长"],
        }],
    }

    pdf = export_resume_pdf(profile, optimization, "示例科技有限公司", "高级产品经理")

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_export_resume_pdf_renders_professional_sidebar_sections(tmp_path):
    import pdfplumber

    profile = ResumeProfile(
        name="张三",
        title="高级产品经理",
        phone="13800000000",
        email="zhangsan@example.com",
        location="郑州",
        skills=["产品规划", "数据分析", "用户增长"],
        education=[Education(institution="郑州大学", degree="本科", major="计算机科学", graduation="2015")],
        summary="具备复杂业务产品经验。",
    )

    path = tmp_path / "resume.pdf"
    path.write_bytes(export_resume_pdf(profile, {}, "示例科技有限公司", "高级产品经理"))

    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    assert "专业技能" in text
    assert "教育背景" in text
    assert "郑州大学" in text


def test_resume_pdf_template_uses_modern_sans_font():
    assert resume_pdf_exporter.F_H == "ResumeSans"
    assert resume_pdf_exporter.F_B == "ResumeSans"


def test_resume_pdf_body_copy_has_roomier_reading_rhythm():
    style = resume_pdf_exporter._body_style("ProbeBody")

    assert style.fontSize >= 9.7
    assert style.leading >= 17
    assert style.spaceAfter >= 3


def test_resume_pdf_sidebar_only_appears_on_first_page(tmp_path):
    import pdfplumber

    profile = ResumeProfile(
        name="张三",
        title="高级产品经理",
        phone="13800000000",
        email="zhangsan@example.com",
        location="郑州",
        skills=[f"技能{i}" for i in range(20)],
        education=[Education(institution="郑州大学", degree="本科", major="计算机科学", graduation="2015")],
        summary="具备复杂业务产品经验。",
        work_experience=[
            WorkExperience(
                company="示例科技有限公司",
                title="高级产品经理",
                duration="2020-至今",
                description="负责复杂业务产品建设。",
            )
        ],
    )
    optimization = {
        "tailored_summary": "具备复杂业务产品经验，能够结合目标岗位要求推动业务增长。",
        "skills_display": [f"技能{i}" for i in range(20)],
        "work_experience": [{
            "company": "示例科技有限公司",
            "title": "高级产品经理",
            "duration": "2020-至今",
            "bullets": [
                f"负责第 {i} 个业务模块的产品规划、需求拆解、跨部门推进、上线复盘和指标优化。"
                for i in range(75)
            ],
        }],
    }

    path = tmp_path / "resume.pdf"
    path.write_bytes(export_resume_pdf(profile, optimization, "示例科技有限公司", "高级产品经理"))

    with pdfplumber.open(path) as pdf:
        assert len(pdf.pages) >= 2
        first_page_text = pdf.pages[0].extract_text() or ""
        second_page_text = pdf.pages[1].extract_text() or ""

    assert "联系方式" in first_page_text
    assert "专业技能" in first_page_text
    assert "联系方式" not in second_page_text
    assert "专业技能" not in second_page_text
    assert "教育背景" not in second_page_text
