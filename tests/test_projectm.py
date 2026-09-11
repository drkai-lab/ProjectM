"""ProjectM 新機能テスト: root ロール階層 / ユーザーグループ / 検索エンジンモード."""
import pytest
from fastapi.testclient import TestClient

from app import auth, config
from app.db import SessionLocal, engine
from app.main import COOKIE, app
from app.models import Base, Keyword, User, UserGroup


def _make_user(email: str, role: str) -> User:
    db = SessionLocal()
    u = db.query(User).filter(User.email == email).first()
    if not u:
        u = User(email=email, name=email.split("@")[0], role=role,
                 password_hash=auth.hash_password("x"))
        db.add(u)
        db.commit()
        db.refresh(u)
    else:
        u.role = role
        db.commit()
        db.refresh(u)
    uid = u.id
    db.close()
    return uid


def _client_as(email: str):
    c = TestClient(app)
    c.get("/login")  # csrftoken クッキーを取得
    db = SessionLocal()
    u = db.query(User).filter(User.email == email).first()
    db.close()
    assert u is not None, f"no user {email}"
    c.cookies.set(COOKIE, auth.make_session_jwt(u))
    return c


def _csrf(c):
    return c.cookies.get("csrftoken")


@pytest.fixture(scope="module", autouse=True)
def users():
    Base.metadata.create_all(engine)
    for email, role in [
        ("root@test.local", "root"),
        ("admin2@test.local", "admin"),   # 2番目のスーパーユーザー
        ("editor@test.local", "editor"),
        ("viewer@test.local", "viewer"),
    ]:
        _make_user(email, role)
    yield


@pytest.fixture()
def root_client():
    return _client_as("root@test.local")


@pytest.fixture()
def admin_client():
    return _client_as("admin2@test.local")


@pytest.fixture()
def editor_client():
    return _client_as("editor@test.local")


# ---------------- ロール階層 / ユーザー管理 ----------------

def test_viewer_cannot_manage_users(editor_client):
    r = editor_client.post("/api/users", data={"email": "x@t.local"},
                           headers={"x-csrftoken": _csrf(editor_client)})
    assert r.status_code == 403


def test_admin_cannot_create_root(admin_client):
    h = {"x-csrftoken": _csrf(admin_client)}
    r = admin_client.post("/api/users", data={"email": "r1@t.local", "role": "root"}, headers=h)
    assert r.status_code == 200
    db = SessionLocal()
    u = db.query(User).filter(User.email == "r1@t.local").first()
    db.close()
    assert u.role == "viewer"  # admin は root を作れないため viewer に降格


def test_root_can_create_root(root_client):
    h = {"x-csrftoken": _csrf(root_client)}
    r = root_client.post("/api/users", data={"email": "r2@t.local", "role": "root"}, headers=h)
    assert r.status_code == 200
    db = SessionLocal()
    u = db.query(User).filter(User.email == "r2@t.local").first()
    db.close()
    assert u.role == "root"


def test_admin_cannot_modify_other_admin(admin_client):
    h = {"x-csrftoken": _csrf(admin_client)}
    db = SessionLocal()
    target = db.query(User).filter(User.email == "admin@test.local").first().id
    db.close()
    assert admin_client.put(f"/api/users/{target}", data={"role": "editor"}, headers=h).status_code == 403
    assert admin_client.put(f"/api/users/{target}", data={"frozen": "1"}, headers=h).status_code == 403
    assert admin_client.delete(f"/api/users/{target}", headers=h).status_code == 403


def test_root_can_modify_admin(root_client):
    h = {"x-csrftoken": _csrf(root_client)}
    db = SessionLocal()
    target = db.query(User).filter(User.email == "admin@test.local").first().id
    db.close()
    assert root_client.put(f"/api/users/{target}", data={"role": "editor"}, headers=h).status_code == 200
    # 戻す
    assert root_client.put(f"/api/users/{target}", data={"role": "admin"}, headers=h).status_code == 200


def test_user_cannot_freeze_self(root_client):
    h = {"x-csrftoken": _csrf(root_client)}
    db = SessionLocal()
    me = db.query(User).filter(User.email == "root@test.local").first().id
    db.close()
    assert root_client.put(f"/api/users/{me}", data={"frozen": "1"}, headers=h).status_code == 400


# ---------------- ユーザーグループ ----------------

def _clean_groups():
    db = SessionLocal()
    for g in db.query(UserGroup).all():
        g.members.clear()
        db.delete(g)
    db.commit()
    db.close()


def test_admin_creates_group_and_adds_editor(admin_client):
    _clean_groups()
    h = {"x-csrftoken": _csrf(admin_client)}
    r = admin_client.post("/api/groups", data={"name": "Ops Team", "description": "運用"}, headers=h)
    assert r.status_code == 200
    gid = r.json()["id"]
    db = SessionLocal()
    editor_id = db.query(User).filter(User.email == "editor@test.local").first().id
    db.close()
    r = admin_client.post(f"/api/groups/{gid}/members", data={"user_id": str(editor_id)}, headers=h)
    assert r.status_code == 200
    r = admin_client.get("/api/groups")
    g = next(x for x in r.json()["groups"] if x["id"] == gid)
    assert any(m["email"] == "editor@test.local" for m in g["members"])


def test_admin_cannot_group_another_admin(admin_client):
    _clean_groups()
    h = {"x-csrftoken": _csrf(admin_client)}
    gid = admin_client.post("/api/groups", data={"name": "G2"}, headers=h).json()["id"]
    db = SessionLocal()
    admin_id = db.query(User).filter(User.email == "admin@test.local").first().id
    db.close()
    r = admin_client.post(f"/api/groups/{gid}/members", data={"user_id": str(admin_id)}, headers=h)
    assert r.status_code == 403


def test_root_can_group_admin(root_client):
    _clean_groups()
    h = {"x-csrftoken": _csrf(root_client)}
    gid = root_client.post("/api/groups", data={"name": "SuperUsers"}, headers=h).json()["id"]
    db = SessionLocal()
    admin_id = db.query(User).filter(User.email == "admin@test.local").first().id
    db.close()
    r = root_client.post(f"/api/groups/{gid}/members", data={"user_id": str(admin_id)}, headers=h)
    assert r.status_code == 200
    # admin がそのグループ(メンバーに admin を含む)を削除しようとすると 403
    ac = _client_as("admin2@test.local")
    h2 = {"x-csrftoken": _csrf(ac)}
    assert ac.delete(f"/api/groups/{gid}", headers=h2).status_code == 403
    # root は削除できる
    assert root_client.delete(f"/api/groups/{gid}", headers=h).status_code == 200


def test_group_creator_only_edit(admin_client):
    _clean_groups()
    h = {"x-csrftoken": _csrf(admin_client)}
    gid = admin_client.post("/api/groups", data={"name": "Mine"}, headers=h).json()["id"]
    rc = _client_as("root@test.local")
    # root は他人のグループも編集できる
    assert rc.put(f"/api/groups/{gid}", data={"description": "by root"},
                  headers={"x-csrftoken": _csrf(rc)}).status_code == 200


def test_duplicate_group_name_rejected(admin_client):
    _clean_groups()
    h = {"x-csrftoken": _csrf(admin_client)}
    assert admin_client.post("/api/groups", data={"name": "Dup"}, headers=h).status_code == 200
    assert admin_client.post("/api/groups", data={"name": "Dup"}, headers=h).status_code == 400


# ---------------- 検索エンジンモード ----------------

def test_extract_terms_filters_stopwords():
    from app.search_engine import extract_terms
    results = [
        {"title": "visa application guide for malaysia", "snippet": "the visa application process requires documents and fees"},
        {"title": "Malaysia visa application requirements", "snippet": "check the visa application portal for updates on documents"},
        {"title": "and dan yang with the for", "snippet": "stopwords should not appear in the output"},
    ]
    terms = extract_terms(results, top_n=5)
    assert any("visa" in t or "application" in t for t in terms)
    joined = " ".join(terms)
    assert "the" not in [t.strip() for t in terms]


def test_search_related_api_merges_engines(monkeypatch, root_client):
    from app import search_engine

    monkeypatch.setattr(search_engine, "ddg_web_search",
                        lambda q, max_results=8: [{"title": f"DDG {q} result", "url": "https://example.com/1", "snippet": "visa application"}])
    monkeypatch.setattr(search_engine, "ddg_related_queries",
                        lambda q, max_results=10: ["related term one"])
    monkeypatch.setattr(search_engine, "brave_web_search",
                        lambda q, max_results=8: ([{"title": f"Brave {q}", "url": "https://example.com/2", "snippet": "x"}], True))

    h = {"x-csrftoken": _csrf(root_client)}
    r = root_client.post("/api/search/related", data={"q": "visa", "engines": "ddg,brave"}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert len(body["engines"]["ddg"]["results"]) == 1
    assert body["engines"]["brave"]["configured"] is True
    assert "related term one" in body["related_terms"]


def test_search_related_brave_not_configured(monkeypatch, root_client):
    from app import search_engine

    monkeypatch.setattr(search_engine, "ddg_web_search", lambda q, max_results=8: [])
    monkeypatch.setattr(search_engine, "ddg_related_queries", lambda q, max_results=10: [])
    monkeypatch.setattr(config, "BRAVE_API_KEY", "")
    monkeypatch.setattr(search_engine, "brave_web_search",
                        lambda q, max_results=8: ([], False))

    h = {"x-csrftoken": _csrf(root_client)}
    r = root_client.post("/api/search/related", data={"q": "test", "engines": "ddg,brave"}, headers=h)
    assert r.status_code == 200
    assert r.json()["engines"]["brave"]["configured"] is False


def test_search_page_requires_login():
    anon = TestClient(app)
    r = anon.get("/search", follow_redirects=False)
    assert r.status_code in (302, 401)


def test_search_page_renders(root_client):
    r = root_client.get("/search")
    assert r.status_code == 200
    assert "DuckDuckGo" in r.text and "BraveSearch" in r.text


# ---------------- キーワード一括追加 ----------------

def test_bulk_add_keywords(editor_client):
    db = SessionLocal()
    for t in ("BulkA", "BulkB"):
        db.query(Keyword).filter(Keyword.term == t).delete()
    db.commit()
    db.close()
    h = {"x-csrftoken": _csrf(editor_client)}
    r = editor_client.post("/api/keywords/bulk", data={"terms": "BulkA, BulkB; BulkC\nBulkA"}, headers=h)
    assert r.status_code == 200
    added = r.json()["added"]
    assert set(added) >= {"BulkA", "BulkB"}
    # 重複はスキップされる
    db = SessionLocal()
    count_a = db.query(Keyword).filter(Keyword.term == "BulkA").count()
    db.close()
    assert count_a == 1


# ---------------- root シーディング ----------------

def test_root_seeded_from_env(monkeypatch):
    from app import db as dbmod
    monkeypatch.setattr(config, "ROOT_EMAIL", "seedroot@test.local")
    monkeypatch.setattr(config, "ROOT_PASSWORD", "seed-pass-123")
    dbmod.init_db()
    db = SessionLocal()
    u = db.query(User).filter(User.email == "seedroot@test.local").first()
    db.close()
    assert u is not None and u.role == "root"
