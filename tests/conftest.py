"""pytest全体設定: テスト専用DB/秘密値へ環境を固定(実DBに触れない)。"""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="pw_test_")
os.environ["PW_DB_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["PW_SECRET_KEY"] = "test-secret-key-32chars-minimum!!"
os.environ["PW_SUPERUSER_EMAIL"] = "admin@test.local"
os.environ["PW_SUPERUSER_PASSWORD"] = "test-pass-123"
os.environ["PW_ENV"] = "development"
os.environ["PW_COOKIE_SECURE"] = "0"
# 外部への実送信を遮断する。本番の .env があるディレクトリで pytest を走らせても
# 実メール/実Telegramを送らない(load_dotenv は既存の環境変数を上書きしない)。
os.environ["PW_MAIL_RELAY_URL"] = ""
os.environ["PW_MAIL_RELAY_KEY"] = ""
os.environ["RESEND_API_KEY"] = ""
os.environ["PW_MAIL_ALLOW_CONSOLE"] = "1"
os.environ["PW_TELEGRAM_TOKEN"] = ""

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _init_test_db():
    """全テストが順序に依存せず users テーブルを使えるようにする。"""
    from app import db as dbmod

    dbmod.init_db()
