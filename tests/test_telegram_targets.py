"""Telegram通知先の管理APIと、通知のファンアウト送信のテスト。"""
import pytest
from fastapi.testclient import TestClient

from app import auth
from app import db as dbmod
from app.db import SessionLocal, engine
from app.main import COOKIE, app
from app.models import Base, TelegramTarget, User


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


def _csrf(client) -> str:
    token = client.cookies.get("csrftoken")
    assert token
    return token


@pytest.fixture(autouse=True)
def _clean_targets():
    """通知先テーブルを毎テスト空にして、順序に依存しないようにする。"""
    db = SessionLocal()
    db.query(TelegramTarget).delete()
    db.commit()
    db.close()


@pytest.fixture()
def captured(monkeypatch):
    """httpx.post を差し替え、送信された chat_id を記録する。"""
    sent = []

    def fake_post(url, data=None, **kwargs):
        payload = data or {}
        sent.append(str(payload["chat_id"]))

    monkeypatch.setattr(dbmod.httpx, "post", fake_post)
    return sent


def _target_id(chat_id: str):
    db = SessionLocal()
    row = db.query(TelegramTarget).filter(TelegramTarget.chat_id == chat_id).first()
    tid = row.id if row else None
    db.close()
    return tid


def _add(chat_id: str, label: str = "", enabled: bool = True):
    db = SessionLocal()
    db.add(TelegramTarget(chat_id=chat_id, label=label, enabled=enabled))
    db.commit()
    db.close()


def test_notify_sends_to_env_and_enabled_targets(captured, monkeypatch):
    """環境変数の宛先と有効な通知先すべてへ1回ずつ送る。"""
    monkeypatch.setattr(dbmod, "TELEGRAM_CHAT_ID", "111111")
    _add("222222", "サブ1")
    _add("333333", "サブ2")
    dbmod.telegram_notify("テスト本文")
    assert sorted(captured) == ["111111", "222222", "333333"]


def test_notify_skips_disabled_targets(captured, monkeypatch):
    """無効な通知先には送らない。"""
    monkeypatch.setattr(dbmod, "TELEGRAM_CHAT_ID", "111111")
    _add("444444", "停止中", enabled=False)
    _add("555555", "稼働中")
    dbmod.telegram_notify("テスト本文")
    assert captured.count("555555") == 1
    assert "444444" not in captured


def test_notify_deduplicates_same_chat_id(captured, monkeypatch):
    """環境変数とDBで同じ宛先なら1回だけ送る。"""
    monkeypatch.setattr(dbmod, "TELEGRAM_CHAT_ID", "111111")
    _add("111111", "重複")
    dbmod.telegram_notify("テスト本文")
    assert captured == ["111111"]


def test_add_target_rejects_invalid_chat_id(client):
    """数字以外・短すぎるチャットIDは400で拒否する。"""
    h = {"x-csrftoken": _csrf(client)}
    assert client.post("/api/telegram_targets", data={"chat_id": "abc"}, headers=h).status_code == 400
    assert client.post("/api/telegram_targets", data={"chat_id": "12345"}, headers=h).status_code == 400


def test_add_target_rejects_duplicate(client):
    """同じチャットIDの二重登録は400で拒否する。"""
    h = {"x-csrftoken": _csrf(client)}
    assert client.post("/api/telegram_targets", data={"chat_id": "8207494814"}, headers=h).status_code == 200
    assert client.post("/api/telegram_targets", data={"chat_id": "8207494814"}, headers=h).status_code == 400


def test_add_test_delete_target_roundtrip(client, captured):
    """追加→テスト送信（その宛先のみ）→削除 が通る。"""
    h = {"x-csrftoken": _csrf(client)}
    r = client.post("/api/telegram_targets", data={"chat_id": " 8207494814 ", "label": "K K"}, headers=h)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    tid = _target_id("8207494814")
    assert tid is not None

    r2 = client.post(f"/api/telegram_targets/{tid}/test", headers=h)
    assert r2.status_code == 200
    assert captured == ["8207494814"]

    r3 = client.delete(f"/api/telegram_targets/{tid}", headers=h)
    assert r3.status_code == 200
    assert _target_id("8207494814") is None


def test_delete_missing_target_returns_404(client):
    """存在しない通知先の削除は404。"""
    h = {"x-csrftoken": _csrf(client)}
    assert client.delete("/api/telegram_targets/999999", headers=h).status_code == 404


def _viewer_client():
    """viewer 権限のクライアントを返す(カード非表示・権限確認用)。"""
    db = SessionLocal()
    u = db.query(User).filter(User.email == "viewer@test.local").first()
    if not u:
        u = User(email="viewer@test.local", name="Test Viewer", role="viewer",
                 password_hash=auth.hash_password("x"))
        db.add(u)
        db.commit()
        db.refresh(u)
    db.close()
    c = TestClient(app)
    c.get("/login")
    c.cookies.set(COOKIE, auth.make_session_jwt(u))
    return c


def test_viewer_cannot_manage_targets(client):
    """管理者以外は通知先を操作できない(403)。"""
    c = _viewer_client()
    h = {"x-csrftoken": _csrf(c)}
    assert c.post("/api/telegram_targets", data={"chat_id": "8207494814"}, headers=h).status_code == 403


def test_settings_page_shows_target_card_for_admin(client):
    """管理者の設定ページに通知先カードが描画される(GUI確認)。"""
    r = client.get("/settings")
    assert r.status_code == 200
    assert "Telegram通知先" in r.text


def test_settings_page_hides_target_card_for_viewer():
    """viewer の設定ページには通知先カードを表示しない。"""
    r = _viewer_client().get("/settings")
    assert r.status_code == 200
    assert "Telegram通知先" not in r.text