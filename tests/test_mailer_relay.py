"""メール送信経路(HTTPS リレー)と招待トークンの回帰テスト。

「送っていないのに成功を返す」不具合が再発しないことを固定する。
"""
import http.server
import json
import threading

import pytest

from app import auth, config, mailer


class _Handler(http.server.BaseHTTPRequestHandler):
    status = 200
    response_body = {"ok": True, "ms": 3}
    seen = {}
    headers_seen = {}

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length", "0"))
        _Handler.seen = json.loads(self.rfile.read(n) or b"{}")
        _Handler.headers_seen = dict(self.headers)
        payload = json.dumps(_Handler.response_body).encode()
        self.send_response(_Handler.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        return


@pytest.fixture
def stub():
    srv = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/relay.php"
    srv.shutdown()


def _configure_relay(monkeypatch, url):
    monkeypatch.setattr(config, "MAIL_RELAY_URL", url)
    monkeypatch.setattr(config, "MAIL_RELAY_KEY", "test-key")
    monkeypatch.setattr(config, "RESEND_API_KEY", "")


def test_relay_success(monkeypatch, stub):
    _Handler.status, _Handler.response_body = 200, {"ok": True, "ms": 3}
    _configure_relay(monkeypatch, stub)
    ok, detail = mailer.send_mail("user@example.com", "件名", "本文")
    assert (ok, detail) == (True, "relay")
    assert _Handler.headers_seen.get("X-Relay-Key") == "test-key"
    assert _Handler.seen["to"] == "user@example.com"
    assert _Handler.seen["reply_to"] == config.MAIL_REPLY_TO
    assert _Handler.seen["subject"] == "件名"


def test_relay_http_error_is_failure(monkeypatch, stub):
    _Handler.status, _Handler.response_body = 401, {"ok": False, "error": "bad key"}
    _configure_relay(monkeypatch, stub)
    ok, detail = mailer.send_mail("user@example.com", "件名", "本文")
    assert ok is False
    assert "401" in detail


def test_relay_ok_false_is_failure(monkeypatch, stub):
    _Handler.status, _Handler.response_body = 200, {"ok": False, "error": "blocked"}
    _configure_relay(monkeypatch, stub)
    ok, detail = mailer.send_mail("user@example.com", "件名", "本文")
    assert ok is False
    assert "拒否" in detail


def test_relay_unreachable_is_failure(monkeypatch):
    _configure_relay(monkeypatch, "http://127.0.0.1:9/relay.php")
    monkeypatch.setattr(config, "MAIL_TIMEOUT", 2)
    ok, detail = mailer.send_mail("user@example.com", "件名", "本文")
    assert ok is False
    assert detail.startswith("relay ")


def test_unconfigured_staging_is_failure(monkeypatch):
    _configure_relay(monkeypatch, "")
    monkeypatch.setattr(config, "MAIL_RELAY_KEY", "")
    monkeypatch.setattr(config, "ENVIRONMENT", "staging")
    monkeypatch.setattr(config, "MAIL_ALLOW_CONSOLE", False)
    ok, detail = mailer.send_mail("user@example.com", "件名", "本文")
    assert (ok, detail) == (False, "not-configured")


def test_unconfigured_development_uses_console(monkeypatch, capsys):
    _configure_relay(monkeypatch, "")
    monkeypatch.setattr(config, "MAIL_RELAY_KEY", "")
    monkeypatch.setattr(config, "ENVIRONMENT", "development")
    monkeypatch.setattr(config, "MAIL_ALLOW_CONSOLE", False)
    ok, detail = mailer.send_mail("user@example.com", "件名", "本文")
    assert (ok, detail) == (True, "console")
    assert "MAIL-CONSOLE" in capsys.readouterr().out


def test_invite_and_login_tokens_use_separate_serializers():
    payload = {"email": "a@example.com", "jti": "abc"}
    login_tok = auth._serializer.dumps(payload)
    invite_tok = auth._invite_serializer.dumps(payload)
    assert login_tok != invite_tok
    assert auth._load_token(login_tok)["jti"] == "abc"
    assert auth._load_token(invite_tok)["jti"] == "abc"
    assert auth._load_token("not-a-token") is None
    assert config.INVITE_LINK_TTL > config.MAGIC_LINK_TTL
