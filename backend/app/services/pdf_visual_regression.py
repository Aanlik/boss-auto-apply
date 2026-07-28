from __future__ import annotations

import shutil
import subprocess
import base64
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image


def inspect_pdf_render(pdf_bytes: bytes, output_dir: Path, max_pages: int = 1) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    renderer = shutil.which("pdftoppm")
    if not renderer:
        return {"status": "unavailable", "reason": "pdftoppm not found", "pages": [], "previewPath": ""}

    _cleanup_old_runs(output_dir)
    run_dir = output_dir / f"run-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    run_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = run_dir / "source.pdf"
    prefix = run_dir / "page"
    pdf_path.write_bytes(pdf_bytes)
    result = subprocess.run(
        [renderer, "-png", "-f", "1", "-l", str(max(1, max_pages)), "-r", "96", str(pdf_path), str(prefix)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
        check=False,
    )
    if result.returncode != 0:
        return {
            "status": "error",
            "reason": (result.stderr or result.stdout or "PDF render failed")[:500],
            "pages": [],
            "previewPath": "",
        }

    pages = []
    for image_path in sorted(run_dir.glob("page-*.png"))[:max_pages]:
        pages.append({"path": str(image_path), **_inspect_png(image_path)})
    status = "ok" if pages and all(page["nonWhiteRatio"] > 0.003 for page in pages) else "error"
    return {
        "status": status,
        "reason": "" if status == "ok" else "PDF 页面疑似空白或渲染异常",
        "pages": pages,
        "previewPath": pages[0]["path"] if pages else "",
        "previewDataUrl": _image_data_url(Path(pages[0]["path"])) if pages else "",
    }


def _inspect_png(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        raw_pixels = rgb.get_flattened_data() if hasattr(rgb, "get_flattened_data") else rgb.tobytes()
    if isinstance(raw_pixels, bytes):
        pixels = zip(raw_pixels[0::3], raw_pixels[1::3], raw_pixels[2::3])
    else:
        pixels = raw_pixels
    total = max(1, width * height)
    non_white = 0
    dark = 0
    for r, g, b in pixels:
        if min(255 - r, 255 - g, 255 - b) > 12:
            non_white += 1
        if r + g + b < 690:
            dark += 1
    return {
        "width": width,
        "height": height,
        "nonWhiteRatio": round(non_white / total, 5),
        "inkRatio": round(dark / total, 5),
    }


def _image_data_url(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _cleanup_old_runs(output_dir: Path, keep: int = 3) -> None:
    runs = sorted(
        [path for path in output_dir.glob("run-*") if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old in runs[keep:]:
        shutil.rmtree(old, ignore_errors=True)
