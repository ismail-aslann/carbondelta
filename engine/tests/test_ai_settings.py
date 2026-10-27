"""Delti ayarları: şifreli saklama, öncelik sırası, hata mesajları."""
import json

import pytest

from desktop import ai_client, ai_settings


@pytest.fixture
def settings_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CARBONDELTA_SETTINGS_DIR", str(tmp_path))
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setattr(ai_client, "env_path", lambda: tmp_path / "yok.env")
    return tmp_path


def test_round_trip_and_key_not_plain(settings_dir):
    ai_settings.save("claude", "  sk-gizli-123  ", "")
    raw = (settings_dir / ai_settings.FILE_NAME).read_text(encoding="utf-8")
    assert "sk-gizli-123" not in raw
    assert json.loads(raw)["api_key"].startswith(("dpapi:", "plain:"))
    assert ai_settings.load() == {"provider": "claude", "model": "", "api_key": "sk-gizli-123"}


def test_missing_or_broken_file_is_empty(settings_dir):
    assert ai_settings.load() == {}
    (settings_dir / ai_settings.FILE_NAME).write_text("{bozuk", encoding="utf-8")
    assert ai_settings.load() == {}
    (settings_dir / ai_settings.FILE_NAME).write_text('{"provider":"gemini","api_key":"dpapi:AAAA"}',
                                                     encoding="utf-8")
    assert ai_settings.load()["api_key"] == ""      # çözülemeyen anahtar boş sayılır


def test_clear(settings_dir):
    ai_settings.save("gemini", "k")
    ai_settings.clear()
    ai_settings.clear()                              # ikinci kez de hata vermez
    assert ai_settings.load() == {}


def test_precedence(settings_dir, monkeypatch):
    env = settings_dir / "a.env"
    env.write_text("LLM_PROVIDER=gemini\nLLM_API_KEY=dosya\n", encoding="utf-8")
    monkeypatch.setattr(ai_client, "env_path", lambda: env)
    cfg = ai_client.load_config()
    assert (cfg.api_key, cfg.source, cfg.model) == ("dosya", ".env", "gemini-flash-lite-latest")

    ai_settings.save("claude", "uygulama-anahtari")
    cfg = ai_client.load_config()
    assert (cfg.provider, cfg.api_key, cfg.source, cfg.model) == \
        ("claude", "uygulama-anahtari", "uygulama", "claude-opus-5-5")

    monkeypatch.setenv("LLM_API_KEY", "ortam")
    assert ai_client.load_config().source == "ortam"


def test_no_key_is_offline(settings_dir):
    cfg = ai_client.load_config()
    assert not cfg.enabled and cfg.source == ""
    assert ai_client.check_connection(cfg)[0] is False


@pytest.mark.parametrize("err, word", [
    ('HTTP 400: {"reason": "API_KEY_INVALID"}', "geçersiz"),
    ("HTTP 401: unauthorized", "geçersiz"),
    ("HTTP 404: not found", "Model"),
    ("HTTP 429: quota", "sınırı"),
    ("HTTP 503: overloaded", "biraz sonra"),
    ("Bağlantı hatası: <urlopen error>", "İnternet"),
])
def test_friendly_error(err, word):
    assert word in ai_client.friendly_error(err)


def test_service_set_config_clears_cache(settings_dir):
    svc = ai_client.AIService(cfg=ai_client.AIConfig("gemini", "", "m"))
    svc._cache["x"] = object()
    svc.set_config(ai_client.AIConfig("gemini", "k", "m"))
    assert svc.online and svc._cache == {}


@pytest.mark.parametrize("provider, url, model", [("openai", "api.openai.com", "gpt-5-mini"),
                                                  ("grok", "api.x.ai", "grok-4.6")])
def test_chat_providers_request_shape(monkeypatch, provider, url, model):
    sent = {}

    def fake_post(u, headers, body):
        sent.update(url=u, headers=headers, body=body)
        return {"choices": [{"message": {"content": "  tamam  "}}]}

    monkeypatch.setattr(ai_client, "_post_json", fake_post)
    cfg = ai_client.AIConfig(provider, "k-123", ai_client.DEFAULT_MODELS[provider])
    assert cfg.enabled and cfg.model == model
    assert ai_client.call_llm(cfg, "sistem", "kullanıcı", json_mode=True) == "tamam"
    assert url in sent["url"] and sent["headers"]["authorization"] == "Bearer k-123"
    b = sent["body"]
    assert b["messages"][0] == {"role": "system", "content": "sistem"}
    assert b["response_format"] == {"type": "json_object"}
    if provider == "openai":
        assert "temperature" not in b and b["max_completion_tokens"] > 0   # GPT-5 sıcaklık kabul etmez
    else:
        assert b["temperature"] == 0


def test_chat_provider_errors(monkeypatch):
    monkeypatch.setattr(ai_client, "_post_json", lambda u, h, b: {"choices": [{"message": {"content": ""}}]})
    with pytest.raises(ai_client.AIError):
        ai_client.call_llm(ai_client.AIConfig("grok", "k", "grok-4.6"), "s", "u")
    monkeypatch.setattr(ai_client, "_post_json", lambda u, h, b: {"error": "x"})
    with pytest.raises(ai_client.AIError):
        ai_client.call_llm(ai_client.AIConfig("openai", "k", "gpt-5-mini"), "s", "u")


def test_saved_new_providers_load(settings_dir):
    ai_settings.save("openai", "sk-o")
    cfg = ai_client.load_config()
    assert (cfg.provider, cfg.model, cfg.enabled) == ("openai", "gpt-5-mini", True)
    ai_settings.save("grok", "xai-k", "grok-özel")
    assert ai_client.load_config().model == "grok-özel"
