"""ProjectW設定。秘密値は環境変数からのみ読み込む。"""
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
DB_URL = os.getenv("PW_DB_URL", f"sqlite:///{DATA_DIR / 'projectw.db'}")

SECRET_KEY = os.getenv("PW_SECRET_KEY", "change-me-in-production-please-32bytes-min")
MAGIC_LINK_TTL = int(os.getenv("PW_MAGIC_TTL", "900"))
SESSION_TTL = int(os.getenv("PW_SESSION_TTL", str(30 * 24 * 3600)))
JWT_ALG = "HS256"

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
MAIL_FROM = os.getenv("PW_MAIL_FROM", "ProjectW <onboarding@resend.dev>")
PUBLIC_BASE_URL = os.getenv("PW_PUBLIC_URL", "http://localhost:8000")

SUPERUSER_EMAIL = os.getenv("PW_SUPERUSER_EMAIL", "iamworkingwell@gmail.com")
SUPERUSER_PASSWORD = os.getenv("PW_SUPERUSER_PASSWORD", "kaikeai34")
DEFAULT_TZ = os.getenv("PW_TZ", "Asia/Kuala_Lumpur")
REQUEST_TIMEOUT = int(os.getenv("PW_REQ_TIMEOUT", "45"))

# デスクトップHermesのカスタムプロバイダ設定と同じ値を既定値にする。
# キーの値はログ・レスポンスへ絶対に出さない。
LLM_BASE_URL = os.getenv("PW_LLM_BASE_URL", "https://api.cheaperinference.com/v1")
LLM_MODEL = os.getenv("PW_LLM_MODEL", "gpt-5.6-luna")
LLM_API_KEY = os.getenv("PW_LLM_API_KEY", os.getenv("HERMES_CUSTOM_API_CHEAPERINFERENCE_COM_API_KEY", ""))
# 通知翻訳は外部送信を伴うため明示的なオプトインのみ。
LLM_ENABLED = os.getenv("PW_LLM_ENABLED", "0").lower() in {"1", "true", "yes", "on"}

# Telegram通知(秘密値は環境変数のみ。未設定なら通知無効)
TELEGRAM_TOKEN = os.getenv("PW_TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("PW_TELEGRAM_CHAT_ID", "")

# 通知言語: zhを既定(既存運用設定)。UIは別途cookie/Accept-Languageで選択。
NOTIFY_LANG = os.getenv("PW_NOTIFY_LANG", "zh")
SUPPORTED_LANGS = ("ja", "en", "zh", "ms", "ko")
