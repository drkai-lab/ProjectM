"""CSRF クッキーのstaleトークン自動修復テスト。

PW_SECRET_KEY 更新前の古い csrftoken がブラウザに残っている場合、
starlette_csrf は「クッキーが存在する」ため再発行せずログインが403で詰む。
_CSRFCookieRefreshMiddleware が stale トークンを検出し新しいクッキーを
レスポンスへ付与することを検証する。
"""
import http.cookies

from fastapi.testclient import TestClient

from app.main import _csrf_token_valid, _new_csrf_cookie, app


def _cookie_value(set_cookie_header: str) -> str:
    c = http.cookies.SimpleCookie()
    c.load(set_cookie_header)
    return c["csrftoken"].value


def test_fresh_get_sets_csrf_cookie(client=None):
    c = TestClient(app)
    r = c.get("/login")
    assert r.status_code == 200
    setc = r.headers.get("set-cookie", "")
    assert "csrftoken=" in setc


def test_stale_token_is_invalid():
    # 現在の secret で復号できないトークンは stale と判定される
    assert _csrf_token_valid(".eJwFbogusAAANB_stale.abc123") is False


def test_new_cookie_roundtrips_through_middleware_serializer():
    from itsdangerous.url_safe import URLSafeSerializer
    from app import config
    setc = _new_csrf_cookie()
    tok = _cookie_value(setc)
    # starlette_csrf と同じ salt/secret で復号可能であること
    URLSafeSerializer(config.SECRET_KEY, "csrftoken").loads(tok)


def test_stale_cookie_refreshed_on_login_page():
    c = TestClient(app)
    stale = ".eJwFbogusAAANB_stale_token_from_old_secret.abc123"
    r = c.get("/login", cookies={"csrftoken": stale})
    assert r.status_code == 200
    setc = r.headers.get("set-cookie", "")
    fresh = _cookie_value(setc)
    assert fresh != stale
    # 新しいトークンは現在の secret で復号できる(=次回ログインで有効)
    assert _csrf_token_valid(fresh)


def test_stale_cookie_refreshed_on_failed_login():
    """403 の CSRF 失敗レスポンスにも新しいクッキーが付与されること。"""
    c = TestClient(app)
    stale = ".eJwFbogusAAANB_stale.abc123"
    r = c.post("/auth/password",
               data={"email": "nobody@example.com", "password": "wrongpass"},
               cookies={"csrftoken": stale},
               headers={"x-csrftoken": stale})
    assert r.status_code == 403
    setc = r.headers.get("set-cookie", "")
    fresh = _cookie_value(setc)
    assert fresh != stale and _csrf_token_valid(fresh)


def test_valid_cookie_not_refreshed():
    """有効なトークンはそのまま(毎回書き換えない)。"""
    c = TestClient(app)
    r0 = c.get("/login")
    tok = _cookie_value(r0.headers["set-cookie"])
    r1 = c.get("/login", cookies={"csrftoken": tok})
    setc = r1.headers.get("set-cookie", "")
    # 有効なトークンなら再発行しない(空 or 同じ値)
    assert not setc or _cookie_value(setc) == tok
