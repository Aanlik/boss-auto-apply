from app.services import system_health


def test_health_check_does_not_include_python_version_check(monkeypatch, tmp_path):
    monkeypatch.delenv("BOSS_WORKBENCH_DESKTOP", raising=False)
    monkeypatch.setattr(system_health, "DATA_DIR", tmp_path)
    monkeypatch.setattr(system_health, "_ai_provider_check", lambda: system_health._check("ai_provider", "AI 配置", "ok", "ok"))
    monkeypatch.setattr(system_health, "_baidu_search_check", lambda: system_health._check("baidu_search", "百度搜索配置", "ok", "ok"))
    monkeypatch.setattr(system_health, "_business_api_check", lambda: system_health._check("business_api", "工商 API 配置", "ok", "ok"))
    monkeypatch.setattr(system_health, "_boss_login_check", lambda: system_health._check("boss_login", "BOSS 登录状态", "ok", "ok"))

    result = system_health.run_health_check()

    assert "python" not in [item["key"] for item in result["checks"]]


def test_desktop_health_check_does_not_include_python_version_check(monkeypatch, tmp_path):
    monkeypatch.setenv("BOSS_WORKBENCH_DESKTOP", "1")
    monkeypatch.setattr(system_health, "DATA_DIR", tmp_path)
    monkeypatch.setattr(system_health, "_ai_provider_check", lambda: system_health._check("ai_provider", "AI 配置", "ok", "ok"))
    monkeypatch.setattr(system_health, "_baidu_search_check", lambda: system_health._check("baidu_search", "百度搜索配置", "ok", "ok"))
    monkeypatch.setattr(system_health, "_business_api_check", lambda: system_health._check("business_api", "工商 API 配置", "ok", "ok"))
    monkeypatch.setattr(system_health, "_boss_login_check", lambda: system_health._check("boss_login", "BOSS 登录状态", "ok", "ok"))

    result = system_health.run_health_check()

    assert "python" not in [item["key"] for item in result["checks"]]
