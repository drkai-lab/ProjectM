"""認証: scrypt パスワードハッシュ, マジックリンク(itsdangerous), JWTセッション Cookie."""
import datetime as dt
import hashlib
import hmac
import os
import secrets

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from jose import jwt
from sqlalchemy import update

from . import config, mailer
from .models import MagicToken, User

_serializer = URLSafeTimedSerializer(config.SECRET_KEY, salt="magic-link")


# ---------- パスワード (stdlib scrypt, bcrypt不要) ----------
def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        algo, salt_hex, dk_hex = stored.split("$")
        if algo != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.scrypt(pw.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


# ---------- マジックリンク ----------
_invite_serializer = URLSafeTimedSerializer(config.SECRET_KEY, salt="magic-invite")


def make_magic_token(email: str, db, kind: str = "login") -> str:
    """kind="invite" は招待用。ログイン用より長い期限の署名器で発行する。"""
    jti = secrets.token_urlsafe(24)
    db.add(MagicToken(jti=jti, email=email.lower(), used=False))
    db.commit()
    payload = {"email": email.lower(), "jti": jti}
    if kind == "invite":
        return _invite_serializer.dumps(payload)
    return _serializer.dumps(payload)


def _load_token(token: str):
    """ログイン用 → 招待用の順で検証し、payload(dict) か None を返す。"""
    try:
        return _serializer.loads(token, max_age=config.MAGIC_LINK_TTL)
    except (BadSignature, SignatureExpired):
        pass
    try:
        return _invite_serializer.loads(token, max_age=config.INVITE_LINK_TTL)
    except (BadSignature, SignatureExpired):
        return None


def verify_magic_token(token: str, db):
    """戻り値 email or None. ワンタイム保証(jti を used に)."""
    data = _load_token(token)
    if not data:
        return None
    rec = db.query(MagicToken).filter(MagicToken.jti == data["jti"]).first()
    if not rec or rec.used or rec.email != data.get("email", "").lower():
        return None
    result = db.execute(update(MagicToken).where(
        MagicToken.jti == data["jti"], MagicToken.used.is_(False)
    ).values(used=True))
    if result.rowcount != 1:
        db.rollback()
        return None
    db.commit()
    return data["email"]


# ---------- JWTセッション ----------
def make_session_jwt(user: User) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {"sub": str(user.id), "email": user.email, "role": user.role,
               "iat": now, "exp": now + dt.timedelta(seconds=config.SESSION_TTL)}
    return jwt.encode(payload, config.SECRET_KEY, algorithm=config.JWT_ALG)


def decode_session_jwt(token: str):
    try:
        return jwt.decode(token, config.SECRET_KEY, algorithms=[config.JWT_ALG])
    except Exception:
        return None


# ---------- メール送信 ----------
# 送信は app/mailer.py に集約。戻り値 (ok, detail) をそのまま返し、成功を偽装しない。
def send_magic_email(to_email: str, link: str, kind: str = "login") -> tuple[bool, str]:
    minutes = max(1, config.MAGIC_LINK_TTL // 60)
    days = max(1, config.INVITE_LINK_TTL // 86400)
    valid = f"{minutes}分間有効"
    if kind == "invite":
        valid = f"{days}日間有効"
    subject = f"{config.MAIL_SUBJECT_PREFIX}ログインリンク"
    text = (f"下のリンクからログインしてください（{valid}）。\n\n{link}\n\n"
            "心当たりが無い場合はこのメールを無視してください。\n")
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto">
      <h2 style="color:#0381fe">ProjectM ログイン</h2>
      <p>下のボタンからログインしてください（15分間有効）。</p>
      <a href="{link}" style="display:inline-block;background:#0381fe;color:#fff;
         padding:14px 28px;border-radius:26px;text-decoration:none;font-weight:600">
         ログイン / Login</a>
      <p style="color:#888;font-size:12px;margin-top:24px">
         心当たりが無い場合はこのメールを無視してください。</p>
    </div>"""
    return mailer.send_mail(to_email, subject, text, html)
