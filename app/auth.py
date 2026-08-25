"""認証: scrypt パスワードハッシュ, マジックリンク(itsdangerous), JWTセッション Cookie."""
import datetime as dt
import hashlib
import hmac
import os
import secrets

import httpx
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from jose import jwt

from . import config
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
def make_magic_token(email: str, db) -> str:
    jti = secrets.token_urlsafe(24)
    db.add(MagicToken(jti=jti, email=email.lower(), used=False))
    db.commit()
    return _serializer.dumps({"email": email.lower(), "jti": jti})


def verify_magic_token(token: str, db):
    """戻り値 email or None. ワンタイム保証(jti を used に)."""
    try:
        data = _serializer.loads(token, max_age=config.MAGIC_LINK_TTL)
    except (BadSignature, SignatureExpired):
        return None
    rec = db.query(MagicToken).filter(MagicToken.jti == data["jti"]).first()
    if not rec or rec.used:
        return None
    rec.used = True
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


# ---------- メール送信 (Resend HTTP API) ----------
def send_magic_email(to_email: str, link: str) -> tuple[bool, str]:
    if not config.RESEND_API_KEY:
        # キー未設定時はコンソール出力にフォールバック(開発用)
        print(f"[MAGIC-LINK for {to_email}] {link}")
        return True, "console"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto">
      <h2 style="color:#0381fe">ProjectW ログイン</h2>
      <p>下のボタンからログインしてください（15分間有効）。</p>
      <a href="{link}" style="display:inline-block;background:#0381fe;color:#fff;
         padding:14px 28px;border-radius:26px;text-decoration:none;font-weight:600">
         ログイン / Login</a>
      <p style="color:#888;font-size:12px;margin-top:24px">
         心当たりが無い場合はこのメールを無視してください。</p>
    </div>"""
    try:
        r = httpx.post("https://api.resend.com/emails",
                       headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
                       json={"from": config.MAIL_FROM, "to": [to_email],
                             "subject": "ProjectW ログインリンク", "html": html},
                       timeout=20)
        if r.status_code in (200, 201):
            return True, "sent"
        return False, f"resend {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
