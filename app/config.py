"""ProjectM設定。秘密値は環境変数からのみ読み込む。"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("PW_DATA_DIR", BASE_DIR.parent / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_URL = os.getenv("PW_DB_URL", f"sqlite:///{DATA_DIR / 'projectm.db'}")

SECRET_KEY = os.getenv("PW_SECRET_KEY", "")
MAGIC_LINK_TTL = int(os.getenv("PW_MAGIC_TTL", "900"))
SESSION_TTL = int(os.getenv("PW_SESSION_TTL", str(30 * 24 * 3600)))
JWT_ALG = "HS256"

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
MAIL_FROM = os.getenv("PW_MAIL_FROM", "ProjectM <info@vorlors.com>")
MAIL_REPLY_TO = os.getenv("PW_MAIL_REPLY_TO", "info@vorlors.com")
MAIL_SUBJECT_PREFIX = os.getenv("PW_MAIL_SUBJECT_PREFIX", "ProjectM ")
MAIL_RELAY_URL = os.getenv("PW_MAIL_RELAY_URL", "")
MAIL_RELAY_KEY = os.getenv("PW_MAIL_RELAY_KEY", "")
MAIL_TIMEOUT = int(os.getenv("PW_MAIL_TIMEOUT", "25"))
MAIL_ALLOW_CONSOLE = os.getenv("PW_MAIL_ALLOW_CONSOLE", "0").lower() in {"1", "true", "yes", "on"}
INVITE_LINK_TTL = int(os.getenv("PW_INVITE_TTL", str(7 * 24 * 3600)))
PUBLIC_BASE_URL = os.getenv("PW_PUBLIC_URL", "http://localhost:8000")

# ProjectM: root ユーザー(スーパーユーザー/admin より上位)。設定すると初回起動時に作成される。
ROOT_EMAIL = os.getenv("PW_ROOT_EMAIL", "")
ROOT_PASSWORD = os.getenv("PW_ROOT_PASSWORD", "")

SUPERUSER_EMAIL = os.getenv("PW_SUPERUSER_EMAIL", "")
SUPERUSER_PASSWORD = os.getenv("PW_SUPERUSER_PASSWORD", "")
DEFAULT_TZ = os.getenv("PW_TZ", "Asia/Kuala_Lumpur")
REQUEST_TIMEOUT = int(os.getenv("PW_REQ_TIMEOUT", "45"))
MAX_RESPONSE_BYTES = int(os.getenv("PW_MAX_RESPONSE_BYTES", str(5 * 1024 * 1024)))
MAX_REDIRECTS = int(os.getenv("PW_MAX_REDIRECTS", "3"))
COOKIE_SECURE = os.getenv("PW_COOKIE_SECURE", "0").lower() in {"1", "true", "yes", "on"}
ENVIRONMENT = os.getenv("PW_ENV", "development").lower()


def validate_production_config():
    """本番だけ既知の開発用フォールバックを拒否する。"""
    if ENVIRONMENT != "production":
        return
    if not SECRET_KEY or len(SECRET_KEY) < 32:
        raise RuntimeError("PW_SECRET_KEY must be set to at least 32 characters in production")
    if not SUPERUSER_EMAIL or not SUPERUSER_PASSWORD:
        raise RuntimeError("PW_SUPERUSER_EMAIL and PW_SUPERUSER_PASSWORD are required in production")
    if not COOKIE_SECURE:
        raise RuntimeError("PW_COOKIE_SECURE must be enabled in production")

# Telegram通知(秘密値は環境変数のみ。未設定なら通知無効)
TELEGRAM_TOKEN = os.getenv("PW_TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("PW_TELEGRAM_CHAT_ID", "")

# 通知言語: zhを既定(既存運用設定)。UIは別途cookie/Accept-Languageで選択。
NOTIFY_LANG = os.getenv("PW_NOTIFY_LANG", "zh")
SUPPORTED_LANGS = ("ja", "en", "zh", "ms", "ko")

# 検索エンジンモード: BraveSearch APIキー(未設定時はDuckDuckGoのみ動作)
BRAVE_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "") or os.getenv("BRAVE_API_KEY", "")
