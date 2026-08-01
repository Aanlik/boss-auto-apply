from app.services import ai_client


def test_provider_presets_use_current_recommended_models():
    assert ai_client.PROVIDER_PRESETS["openai"]["models"][0] == "gpt-5.6"
    assert ai_client.PROVIDER_PRESETS["deepseek"]["models"] == ["deepseek-v4-flash", "deepseek-v4-pro"]
    assert ai_client.PROVIDER_PRESETS["zhipu"]["models"][0] == "glm-5.2"
    assert ai_client.PROVIDER_PRESETS["moonshot"]["models"][0] == "kimi-k3"


def test_stale_preset_model_falls_back_to_recommended_model(monkeypatch):
    monkeypatch.setattr(ai_client, "_cached_config", {
        "provider": "deepseek",
        "api_key": "test-key",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-legacy-model",
    })

    assert ai_client.get_model() == "deepseek-v4-flash"
