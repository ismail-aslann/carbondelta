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
