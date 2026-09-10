"""ログインページのインライン JS が有効であること + CSRF フォールバックの回帰テスト。

背景 (実障害): login.html の `var msgs = {{ msgs_json|default({}) }};` は Jinja の
自動エスケープで `&#34;` を含む文字列になり、<script> 内では HTML エンティティが
デコードされないため SyntaxError でインラインスクリプト全体が死んでいた。
結果、submit ハンドラが付かずネイティブ form POST になり x-csrftoken ヘッダーが
送られず 403 "CSRF token verification failed" でログイン不能だった。
"""
import json
import re

from fastapi.testclient import TestClient

from app import auth, config, db as dbmod
from app.main import COOKIE, CSRF_COOKIE, app


def _login_page_script() -> str:
    c = TestClient(app)
    r = c.get("/login")
    assert r.status_code == 200
    m = re.search(r"<script>(.*?)</script>", r.text, re.S)
    assert m, "インラインスクリプトが見つからない"
    return m.group(1)


def test_login_page_msgs_is_valid_js_object():
    script = _login_page_script()
    # HTML エンティティが混入していない(混入すると SyntaxError)
    assert "&#34;" not in script and "&quot;" not in script
    m = re.search(r"var msgs = (\{.*?\});", script, re.S)
    assert m, "var msgs 行が見つからない"
    msgs = json.loads(m.group(1))
    assert msgs["login_failed"]


def test_login_page_keeps_script_safe_after_translation_with_quotes():
    """翻訳文に引用符が入っても JS が壊れないこと(tojson は \\u エスケープする)。"""
    import app.main as main
    original = main.TRANSLATIONS["ja"].get("invalid_credentials")
    main.TRANSLATIONS["ja"]["invalid_credentials"] = 'a "</script>" b'
    try:
        script = _login_page_script()
        assert "</script>" not in script
    finally:
        if original is None:
            main.TRANSLATIONS["ja"].pop("invalid_credentials", None)
        else:
            main.TRANSLATIONS["ja"]["invalid_credentials"] = original


def test_native_post_with_cookie_but_no_header_is_accepted():
    """JS が動かないネイティブ form POST (ヘッダー無し) でも CSRF を通す。

    認証情報が無いユーザーなので CSRF 通過後に 401/303 が返る = 403 でないこと。
    """
    c = TestClient(app)
    r0 = c.get("/login")
    tok = c.cookies.get(CSRF_COOKIE)
    assert tok, "csrftoken クッキーが発行されていない"
    r = c.post("/auth/password",
               data={"email": "nobody@example.com", "password": "wrongpass"},
               headers={"accept": "application/json"})
    assert r.status_code == 401, f"ネイティブPOSTがCSRFで弾かれた: {r.status_code} {r.text}"


def test_cross_origin_post_still_rejected():
    """別オリジンからの POST はフォールバックさせない(403/401のまま)。"""
    c = TestClient(app)
    c.get("/login")
    r = c.post("/auth/password",
               data={"email": "nobody@example.com", "password": "wrongpass"},
               headers={"origin": "https://evil.example", "accept": "application/json"})
    assert r.status_code == 403


def test_valid_login_with_native_post_sets_session():
    """ヘッダー無しのネイティブPOSTで正しい認証情報ならログインできる。"""
    dbmod.init_db()
    db = dbmod.SessionLocal()
    email = "csrf@example.com"
    if not db.query(dbmod.User).filter_by(email=email).first():
        db.add(dbmod.User(email=email, password_hash=auth.hash_password("pw12345")))
        db.commit()
    db.close()
    c = TestClient(app)
    c.get("/login")
    r = c.post("/auth/password", data={"email": email, "password": "pw12345"})
    assert r.status_code in (200, 303), r.text
    assert c.cookies.get(COOKIE)
