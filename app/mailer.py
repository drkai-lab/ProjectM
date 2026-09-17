"""メール送信の単一経路。

VPS から外向き SMTP(25/465/587)は遮断されているため、送信は vorlors.com 上の
HTTPS リレー(PHP mail())に委譲する。Resend とコンソール出力はフォールバック。
戻り値は常に (ok, detail)。送信していないのに ok=True を返してはならない。
"""
from . import config

try:
    import httpx
except Exception:
    httpx = None


def _relay_configured() -> bool:
    return bool(config.MAIL_RELAY_URL and config.MAIL_RELAY_KEY)


def _send_relay(to_email: str, subject: str, text: str, html: str) -> tuple[bool, str]:
    if httpx is None:
        return False, "httpx がありません"
    payload = {"to": to_email, "subject": subject, "text": text,
               "html": html or "", "reply_to": config.MAIL_REPLY_TO}
    headers = {"X-Relay-Key": config.MAIL_RELAY_KEY,
               "Content-Type": "application/json"}
    r = httpx.post(config.MAIL_RELAY_URL, json=payload, headers=headers,
                   timeout=config.MAIL_TIMEOUT)
    if r.status_code != 200:
        return False, f"relay {r.status_code}: {r.text[:200]}"
    try:
        data = r.json()
    except Exception:
        return False, f"relay 応答が不正: {r.text[:120]}"
    if not data.get("ok"):
        return False, f"relay 拒否: {str(data)[:200]}"
    return True, "relay"


def _send_resend(to_email: str, subject: str, text: str, html: str) -> tuple[bool, str]:
    if httpx is None:
        return False, "httpx がありません"
    r = httpx.post("https://api.resend.com/emails",
                   headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
                   json={"from": config.MAIL_FROM, "to": [to_email],
                         "subject": subject, "html": html or text},
                   timeout=config.MAIL_TIMEOUT)
    if r.status_code in (200, 201):
        return True, "resend"
    return False, f"resend {r.status_code}: {r.text[:200]}"


def _send_console(to_email: str, subject: str, text: str) -> tuple[bool, str]:
    print(f"[MAIL-CONSOLE to={to_email}] {subject}\n{text}")
    return True, "console"


def console_allowed() -> bool:
    """コンソール出力を成功とみなしてよいのは開発環境のみ。"""
    if config.MAIL_ALLOW_CONSOLE:
        return True
    return config.ENVIRONMENT == "development"


def send_mail(to_email: str, subject: str, text: str, html: str = "") -> tuple[bool, str]:
    """(ok, detail) を返す。バックエンド未設定なら (False, "not-configured")。"""
    if _relay_configured():
        try:
            return _send_relay(to_email, subject, text, html)
        except Exception as e:
            return False, f"relay {type(e).__name__}: {e}"
    if config.RESEND_API_KEY:
        try:
            return _send_resend(to_email, subject, text, html)
        except Exception as e:
            return False, f"resend {type(e).__name__}: {e}"
    if not console_allowed():
        return False, "not-configured"
    return _send_console(to_email, subject, text)
