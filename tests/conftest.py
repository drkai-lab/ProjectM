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
