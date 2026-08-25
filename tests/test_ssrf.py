import socket

from app.scraper_engine import validate_target_url


def _fake_getaddrinfo(host, port, type=None):
    mapping = {
        "public.example": "93.184.216.34",
        "localhost.example": "127.0.0.1",
        "private.example": "10.0.0.2",
        "linklocal.example": "169.254.169.254",
        "v6local.example": "::1",
    }
    return [(socket.AF_INET6 if ":" in mapping[host] else socket.AF_INET,
             socket.SOCK_STREAM, 6, "", (mapping[host], port))]


def test_target_url_rejects_non_http_schemes():
    assert validate_target_url("file:///etc/passwd")[0] is False
    assert validate_target_url("javascript:alert(1)")[0] is False
    assert validate_target_url("https://user:pass@public.example/")[0] is False


def test_target_url_rejects_private_destinations(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)
    for host in ("localhost.example", "private.example", "linklocal.example", "v6local.example"):
        assert validate_target_url(f"https://{host}/")[0] is False


def test_target_url_accepts_public_https(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)
    assert validate_target_url("https://public.example/path")[0] is True
