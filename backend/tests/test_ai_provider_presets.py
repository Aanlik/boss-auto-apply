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


def test_successful_ai_json_call_persists_a_version_record(tmp_path, monkeypatch):
    from app.services import workflow_persistence

    class FakeCompletions:
        def create(self, **_kwargs):
            return type("Response", (), {
                "choices": [type("Choice", (), {"message": type("Message", (), {"content": '{"message":"ok"}'})()})()],
            })()

    fake_client = type("Client", (), {"chat": type("Chat", (), {"completions": FakeCompletions()})()})()
    monkeypatch.setattr(workflow_persistence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(ai_client, "test_mode_enabled", lambda: False)
    monkeypatch.setattr(ai_client, "get_client", lambda: fake_client)
    monkeypatch.setattr(ai_client, "get_model", lambda: "test-model")
    monkeypatch.setattr(ai_client, "get_config", lambda: {"base_url": "https://example.test"})
    monkeypatch.setattr(ai_client, "run_with_resilience", lambda _category, operation, **_kwargs: operation())

    assert ai_client.chat_json("生成招呼语", "岗位信息") == {"message": "ok"}

    rows = workflow_persistence._read_json(tmp_path / "assistant" / "prompt_versions.json", [])
    assert rows[0]["kind"] == "ai_generation"
    assert rows[0]["promptVersion"] == "test-model"
    assert rows[0]["promptPreview"] == "生成招呼语"


def test_chat_json_plain_text_mode_returns_raw_text_without_json_request(monkeypatch):
    calls = []
    plain_text = "您好，我有用户研究和产品规划经验，希望和您进一步交流。"

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return type("Response", (), {
                "choices": [type("Choice", (), {
                    "message": type("Message", (), {"content": plain_text})(),
                })()],
            })()

    fake_client = type("Client", (), {"chat": type("Chat", (), {"completions": FakeCompletions()})()})()
    monkeypatch.setattr(ai_client, "test_mode_enabled", lambda: False)
    monkeypatch.setattr(ai_client, "get_client", lambda: fake_client)
    monkeypatch.setattr(ai_client, "get_model", lambda: "deepseek-v4-flash")
    monkeypatch.setattr(ai_client, "get_config", lambda: {"provider": "deepseek", "base_url": "https://api.deepseek.com"})
    monkeypatch.setattr(ai_client, "run_with_resilience", lambda _category, operation, **_kwargs: operation())

    result = ai_client.chat_json("生成一条打招呼语", "岗位信息", expect_json=False)

    assert result == {"raw": plain_text}
    assert "response_format" not in calls[0]



def test_deepseek_structured_request_explicitly_disables_thinking(monkeypatch):
    """DeepSeek V4 的 JSON 排序请求不能使用默认思考模式。"""
    calls = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return type("Response", (), {
                "choices": [type("Choice", (), {
                    "finish_reason": "stop",
                    "message": type("Message", (), {"content": '{"ok": true}', "reasoning_content": None})(),
                })()],
            })()

    fake_client = type("Client", (), {"chat": type("Chat", (), {"completions": FakeCompletions()})()})()
    monkeypatch.setattr(ai_client, "get_client", lambda: fake_client)
    monkeypatch.setattr(ai_client, "get_model", lambda: "deepseek-v4-flash")
    monkeypatch.setattr(ai_client, "get_config", lambda: {"provider": "deepseek", "base_url": "https://api.deepseek.com"})

    assert ai_client._chat_sync("返回 json", 0.2, 800, json_mode=True, disable_thinking=True) == '{"ok": true}'
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert calls[0]["extra_body"] == {"thinking": {"type": "disabled"}}
