from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_reference_repositories_are_not_runtime_imports():
    runtime_files = list((ROOT / "backend" / "app").rglob("*.py")) + list((ROOT / "frontend" / "src").rglob("*.*"))
    forbidden_tokens = ["boss-scraper-ref", "JobPilot", "JadeAI", "Align-Resume"]

    offenders = []
    for path in runtime_files:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for token in forbidden_tokens:
            for line in lines:
                stripped = line.strip()
                is_runtime_load = (
                    stripped.startswith(("import ", "from "))
                    or "require(" in stripped
                    or "import(" in stripped
                )
                if is_runtime_load and token in stripped:
                    offenders.append(f"{path.relative_to(ROOT)} imports {token}")

    assert offenders == []


def test_boss_scraper_declares_reference_boundary():
    text = (ROOT / "backend" / "app" / "services" / "boss_scraper.py").read_text(encoding="utf-8")

    assert "无运行时依赖" in text
    assert "独立实现" in text


def test_spa_fallback_is_registered_even_when_frontend_dist_is_missing_at_startup():
    text = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")

    assert "if STATIC_DIR.exists():" not in text
    assert "@app.get(\"/{full_path:path}\")" in text
