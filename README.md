# ProjectW — MyGov Monitor Dashboard

マレーシア官公庁サイト(デフォルト100件)を監視し、キーワードヒット・更新・失敗を Telegram 通知する FastAPI アプリ。Web ダッシュボード(OneUI 風 PWA)からサイト・キーワード・スケジュール・ユーザーを管理できる。

## 技術スタック

- **Backend**: FastAPI + Uvicorn/Gunicorn
- **DB**: SQLite (SQLAlchemy 2.0)
- **認証**: マジックリンク(itsdangerous 署名 + Resend HTTP API)+ JWT Cookie セッション。パスワードは stdlib `hashlib.scrypt`(bcrypt 不要)
- **スケジューラ**: APScheduler(interval / daily / cron、1日最大回数、TZ 指定)
- **スクレイパー**: curl_cffi(あれば)→ httpx フォールバック
- **UI**: Jinja2 + OneUI 風 CSS、PWA(manifest + Service Worker)
- **パッケージ管理**: uv のみ(pip 不使用)

## 権限モデル

| ロール | 権限 |
|---|---|
| admin | 全操作 + ユーザー管理(招待/凍結解除/ロール/情報変更) |
| editor | サイト・キーワード編集、手動スキャン、スケジュール変更 |
| viewer | 閲覧のみ |

スーパーユーザー(admin)は初回起動時に `.env` の `PW_SUPERUSER_EMAIL` / `PW_SUPERUSER_PASSWORD` から自動作成される。

## セットアップ

```bash
uv sync
cp .env.example .env   # 値を編集(SECRET_KEY, Resend キー等)
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 環境変数(.env)

| 変数 | 説明 |
|---|---|
| PW_SECRET_KEY | 署名・JWT 用シークレット |
| PW_SUPERUSER_EMAIL / PW_SUPERUSER_PASSWORD | 初期 admin |
| RESEND_API_KEY | Resend API キー(未設定時はコンソールにリンク出力) |
| PW_PUBLIC_URL | 公開 URL(マジックリンク生成に使用) |
| PW_LLM_BASE_URL / PW_LLM_MODEL | LLM翻訳等を使う場合のOpenAI互換エンドポイント/モデル。デスクトップ既定値は cheaperinference + gpt-5.6-luna |
| PW_LLM_API_KEY | LLM APIキー(秘密。ログへ出力しない) |
| PW_TELEGRAM_TOKEN / PW_TELEGRAM_CHAT_ID | Telegram通知の接続情報(秘密。ログへ出力しない) |
| PW_NOTIFY_LANG | Telegram通知言語(ja/en/zh/ms/ko、既定zh) |
| PW_TZ | スケジュールのデフォルト TZ |

## 多言語

UIはブラウザ/OSの `Accept-Language` を自動判定し、対応する言語(日本語・英語・簡体中国語・マレー語・韓国語)で表示する。画面の言語セレクターで手動指定した場合は `pw_lang` Cookie が優先される。Telegram通知は `PW_NOTIFY_LANG` で固定指定する。

## デプロイ

Gunicorn + Uvicorn worker + Nginx + Let's Encrypt(HTTPS)。systemd user サービスで常駐。
