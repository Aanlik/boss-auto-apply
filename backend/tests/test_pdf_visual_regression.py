from __future__ import annotations

import warnings
from pathlib import Path

from PIL import Image

from app.models.resume import ResumeProfile
from app.services.pdf_visual_regression import _inspect_png, inspect_pdf_render
from app.services.report_pdf_exporter import export_deep_report_pdf
from app.services.resume_pdf_exporter import export_resume_pdf


def test_resume_pdf_visual_render_is_nonblank(tmp_path):
    pdf = export_resume_pdf(
        ResumeProfile(name="张三", title="产品经理", summary="负责产品规划、用户增长和跨部门协作。"),
        {"tailored_summary": "面向目标岗位突出产品规划、用户增长和业务结果。"},
        "示例科技",
        "产品经理",
    )

    result = inspect_pdf_render(pdf, tmp_path / "resume")

    assert result["status"] == "ok"
    assert result["pages"][0]["nonWhiteRatio"] > 0.01
    assert result["pages"][0]["width"] >= 500
    assert result["previewPath"].endswith(".png")


def test_deep_report_pdf_visual_render_is_nonblank(tmp_path):
    pdf = export_deep_report_pdf({
        "company": "示例科技",
        "title": "产品经理",
        "result": {
            "manualReport": {
                "sections": {
                    "summary": "人工总结",
                    "strategy": "优先投递，强调增长经验。",
                    "risk": "暂无明确高风险。",
                    "interview": "准备业务增长案例。",
                    "actions": "先打招呼，再跟进。",
                }
            }
        },
    })

    result = inspect_pdf_render(pdf, tmp_path / "report")

    assert result["status"] == "ok"
    assert result["pages"][0]["nonWhiteRatio"] > 0.01


def test_png_inspection_uses_non_deprecated_pixel_access(tmp_path):
    image_path = tmp_path / "sample.png"
    Image.new("RGB", (4, 4), "white").save(image_path)

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        result = _inspect_png(image_path)

    assert result["width"] == 4
    assert result["height"] == 4


def test_pdf_visual_render_ignores_corrupted_stale_images(tmp_path):
    output_dir = tmp_path / "resume"
    output_dir.mkdir()
    (output_dir / "page-1.png").write_text("not a real png")
    pdf = export_resume_pdf(
        ResumeProfile(name="张三", title="产品经理", summary="负责产品规划、用户增长和跨部门协作。"),
        {"tailored_summary": "面向目标岗位突出产品规划、用户增长和业务结果。"},
        "示例科技",
        "产品经理",
    )

    result = inspect_pdf_render(pdf, output_dir)

    assert result["status"] == "ok"
    assert result["pages"][0]["nonWhiteRatio"] > 0.01
    assert Path(result["previewPath"]).parent != output_dir
