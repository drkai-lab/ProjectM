"""キーワードCRUD API (add / update / toggle / delete / duplicate) のテスト。"""
import pytest
from fastapi.testclient import TestClient

from app import auth
from app.db import SessionLocal, engine
from app.main import COOKIE, app
from app.models import Base, Keyword, User


@pytest.fixture(scope="module")
def admin():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    u = db.query(User).filter(User.email == "admin@test.local").first()
    if not u:
        u = User(email="admin@test.local", name="Test Admin", role="admin",
                 password_hash=auth.hash_password("x"))
        db.add(u)
        db.commit()
        db.refresh(u)
    db.close()
    return u


@pytest.fixture()
def client(admin):
    c = TestClient(app)
    c.get("/login")                      # csrftoken クッキーを取得
    c.cookies.set(COOKIE, auth.make_session_jwt(admin))
    return c


def _csrf(client):
    return client.cookies.get("csrftoken")


def _clean_keywords():
    db = SessionLocal()
    db.query(Keyword).delete()
    db.commit()
    db.close()


def test_add_keyword_saves_label(client):
    _clean_keywords()
    r = client.post("/api/keywords", data={"term": "Wajib", "label": "必須"},
                    headers={"x-csrftoken": _csrf(client)})
    assert r.status_code == 200
    db = SessionLocal()
    kw = db.query(Keyword).filter(Keyword.term == "Wajib").first()
    db.close()
    assert kw is not None
    assert kw.label == "必須"
    assert kw.enabled is True


def test_duplicate_keyword_rejected(client):
    _clean_keywords()
    h = {"x-csrftoken": _csrf(client)}
    assert client.post("/api/keywords", data={"term": "Pas"}, headers=h).status_code == 200
    assert client.post("/api/keywords", data={"term": "Pas"}, headers=h).status_code == 400


def test_update_keyword_term_label(client):
    _clean_keywords()
    h = {"x-csrftoken": _csrf(client)}
    client.post("/api/keywords", data={"term": "Pas"}, headers=h)
    db = SessionLocal()
    kid = db.query(Keyword).first().id
    db.close()
    r = client.put(f"/api/keywords/{kid}",
                   data={"term": "Pas Baharu", "label": "新しいパス"},
                   headers=h)
    assert r.status_code == 200
    db = SessionLocal()
    kw = db.get(Keyword, kid)
    db.close()
    assert kw.term == "Pas Baharu"
    assert kw.label == "新しいパス"


def test_toggle_keyword_disabled(client):
    _clean_keywords()
    h = {"x-csrftoken": _csrf(client)}
    client.post("/api/keywords", data={"term": "Majikan"}, headers=h)
    db = SessionLocal()
    kid = db.query(Keyword).first().id
    db.close()
    r = client.put(f"/api/keywords/{kid}", data={"enabled": "0"}, headers=h)
    assert r.status_code == 200
    db = SessionLocal()
    assert db.get(Keyword, kid).enabled is False
    db.close()


def test_delete_keyword(client):
    _clean_keywords()
    h = {"x-csrftoken": _csrf(client)}
    client.post("/api/keywords", data={"term": "Kriteria"}, headers=h)
    db = SessionLocal()
    kid = db.query(Keyword).first().id
    db.close()
    r = client.delete(f"/api/keywords/{kid}", headers=h)
    assert r.status_code == 200
    db = SessionLocal()
    assert db.query(Keyword).count() == 0
    db.close()


def test_keyword_api_requires_auth(client):
    anon = TestClient(app)
    r = anon.post("/api/keywords", data={"term": "X"})
    assert r.status_code in (401, 403)


def test_sites_page_renders_keyword_rows(client):
    _clean_keywords()
    h = {"x-csrftoken": _csrf(client)}
    client.post("/api/keywords", data={"term": "Pas", "label": "就労パス"}, headers=h)
    r = client.get("/sites")
    assert r.status_code == 200
    assert "kw-row" in r.text
    assert "就労パス" in r.text