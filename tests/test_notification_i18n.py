from app import config
from app import db
from app.scraper_engine import format_notification
from app import llm


def test_supported_notification_languages_have_localized_headings():
    expected = {
        "zh": ("关键词命中", "获取失败", "更新"),
        "ja": ("キーワードヒット", "取得失敗", "更新"),
        "en": ("Keyword Hits", "Failures", "Updates"),
        "ms": ("Padanan Kata Kunci", "Kegagalan", "Kemas Kini"),
        "ko": ("키워드 적중", "실패", "업데이트"),
    }
    for lang, headings in expected.items():
        text = format_notification(lang, ["🔔 https://example.test\n   keywords: 原文\n   原文snippet..."], ["❌ https://failed.test — HTTP 500"], 2)
        assert all(heading in text for heading in headings)
        assert "原文" in text
        assert "https://example.test" in text


def test_notification_language_uses_config_and_environment(monkeypatch):
    monkeypatch.setenv("PW_NOTIFY_LANG", "ja")
    assert db.notification_language() == "ja"
    monkeypatch.setenv("PW_NOTIFY_LANG", "invalid")
    assert db.notification_language() == "zh"


def test_telegram_notify_translates_existing_bilingual_body(monkeypatch):
    captured = []
    monkeypatch.setattr(db.httpx, "post", lambda *args, **kwargs: captured.append(kwargs["data"]))
    monkeypatch.setenv("PW_NOTIFY_LANG", "ja")
    db.telegram_notify("【关键词命中 / Keyword Hits】\n原文 URL https://example.test")
    assert "キーワードヒット" in captured[0]["text"]
    assert "原文 URL https://example.test" in captured[0]["text"]


def test_llm_settings_match_desktop_without_key_output():
    assert config.LLM_BASE_URL == "https://api.cheaperinference.com/v1"
    assert config.LLM_MODEL == "gpt-5.6-luna"
    assert config.LLM_ENABLED is False


def test_llm_disabled_returns_original(monkeypatch):
    monkeypatch.setattr(config, "LLM_ENABLED", False)
    assert llm.translate("原文", "ja") == "原文"


def test_llm_failure_returns_original_and_uses_config(monkeypatch):
    class Client:
        def __init__(self): self.request = None
        def post(self, url, **kwargs):
            self.request = (url, kwargs)
            raise RuntimeError("offline")
    client = Client()
    monkeypatch.setattr(config, "LLM_ENABLED", True)
    monkeypatch.setattr(config, "LLM_API_KEY", "sentinel")
    assert llm.translate("原文", "ja", client=client) == "原文"
    assert client.request is not None
    url, kwargs = client.request
    assert url == "https://api.cheaperinference.com/v1/chat/completions"
    assert kwargs["json"]["model"] == "gpt-5.6-luna"
