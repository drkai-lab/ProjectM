# Project M

マレーシアの政府機関や関連機関のウェブサイトを定期的に見回り、ページの更新や、指定したキーワードの登場を知らせるための監視ダッシュボードです。ProjectW をベースに、**root ユーザー階層**・**ユーザーグループ**・**検索エンジンモード**を追加した派生版です。

## 何ができるか

- 登録したウェブサイトを自動で定期チェック
- ページの内容が前回から変わったかを確認
- 「申請」「パス」「料金」など、指定した言葉が出たページを記録
- 更新やキーワードのヒットをTelegramへ通知
- ブラウザから監視先とキーワードを追加・削除・一時停止
- 次回のチェック時刻や、過去のチェック結果をダッシュボードで確認
- マジックリンクまたはパスワードでログイン
- 日本語、英語、中国語、マレー語、インドネシア語、韓国語の画面表示に対応

### ProjectM で追加された機能

#### root ユーザー(スーパーユーザーより上位)

ロール階層は **root > admin(スーパーユーザー) > editor > viewer** です。

- `PW_ROOT_EMAIL` / `PW_ROOT_PASSWORD` を設定すると、初回起動時に root ユーザーが自動作成されます
- root はすべてのユーザー(スーパーユーザー/admin 含む)の作成・ロール変更・凍結・削除ができます
- admin(スーパーユーザー)は editor/viewer の管理と、admin への昇格までできます。root ロールの作成や他の admin への操作は root のみです

#### ユーザーグループ

- root と admin はユーザーをグループ化し、ロールの割り当てができます
- **root** はスーパーユーザー(admin)もグループに含められます(例: 「SuperUsers」グループ)
- **admin** がグループ化・外せるのは一般ユーザー(editor/viewer)のみです
- グループの作成・編集・削除は作成者または root。メンバーに admin を含むグループの削除は root のみです

#### 検索エンジンモード (DuckDuckGo / BraveSearch)

ダッシュボード下部ナビの「関連語検索」から利用できます。

- 単語を入力すると **DuckDuckGo**(APIキー不要)と **BraveSearch**(`BRAVE_SEARCH_API_KEY` 設定時)からWeb結果を取得します
- DuckDuckGo の公式関連クエリ + 結果テキストからの頻出語抽出により、**関連語候補**を表示します
- 候補を1件ずつ、またはまとめて監視キーワードとして登録できます(編集者以上)

## 画面の見方

### ダッシュボード

登録サイト数、有効になっているサイト数、キーワード数、最近のチェック結果、次回チェック時刻をまとめて表示します。

### サイト

監視するURLを管理します。サイトごとに表示名、アクセス時のブラウザ設定、有効・無効を設定できます。

### 関連語検索

DuckDuckGo / BraveSearch で関連語を検索し、キーワード候補として表示します。

### 設定

チェックの間隔や実行時刻、タイムゾーンを変更できます。管理者以上はユーザーの追加、権限変更、アカウント凍結、グループ管理も行えます。

## 権限

| 操作 | root | admin(スーパーユーザー) | editor | viewer |
| --- | :-: | :-: | :-: | :-: |
| ダッシュボード/サイト閲覧 | ○ | ○ | ○ | ○ |
| サイト・キーワード・スケジュール変更 | ○ | ○ | ○ | - |
| 関連語検索 | ○ | ○ | ○ | ○ |
| キーワード登録(検索候補から) | ○ | ○ | ○ | - |
| editor/viewer の作成・ロール変更・凍結・削除 | ○ | ○ | - | - |
| admin の作成・ロール変更・凍結・削除 | ○ | - | - | - |
| root の作成・ロール変更 | ○(自分以外) | - | - | - |
| グループ: 一般ユーザーのグループ化 | ○ | ○ | - | - |
| グループ: スーパーユーザー(admin)のグループ化 | ○ | - | - | - |

## 動作の流れ

1. Project Mが登録済みの有効なサイトへアクセスします。
2. ページの文章を読み取り、前回の内容と比べます。
3. 内容が変わっていれば、登録キーワードを探します。
4. キーワードが見つかったページと短い抜粋を履歴へ保存します。
5. 設定されていれば、結果をTelegramへ送ります。

サイトへのアクセスに失敗した場合も、失敗したURLと理由を結果に残します。アクセス先が大きすぎる場合や、画像・ファイルなど文章ではないコンテンツは対象外です。

## セットアップ

### 必要なもの

- Python 3.11以上
- `uv`
- Telegram通知を使う場合は、Telegram Botのトークンと通知先チャットID
- メール形式のマジックリンクを使う場合は、ResendのAPIキー
- BraveSearch を使う場合は、Brave Search API のキー(任意)

### インストール

```bash
uv sync
```

### 環境変数

秘密情報は `.env` または実行環境の環境変数に設定します。秘密情報をソースコードへ直接書かないでください。

```dotenv
PW_ENV=development
PW_SECRET_KEY=十分に長いランダムな文字列
# ProjectM: root ユーザー(スーパーユーザーより上位)
PW_ROOT_EMAIL=root@example.com
PW_ROOT_PASSWORD=rootのパスワード
PW_SUPERUSER_EMAIL=管理者のメールアドレス
PW_SUPERUSER_PASSWORD=管理者のパスワード
PW_PUBLIC_URL=http://localhost:8000

# 任意: Telegram通知
PW_TELEGRAM_TOKEN=Telegram Botのトークン
PW_TELEGRAM_CHAT_ID=通知先のチャットID
PW_NOTIFY_LANG=ja

# 任意: マジックリンクメール
RESEND_API_KEY=ResendのAPIキー
PW_MAIL_FROM=ProjectM <送信元アドレス>

# 任意: 検索エンジンモード (未設定時はDuckDuckGoのみ)
BRAVE_SEARCH_API_KEY=Brave Search APIキー
```

本番環境では、`PW_SECRET_KEY`を32文字以上にし、`PW_COOKIE_SECURE=1`を設定してください。スーパーユーザーのメールアドレスとパスワードも必須です。root は `PW_ROOT_EMAIL`/`PW_ROOT_PASSWORD` で設定するか、既存の root 経由でロール変更してください。

### 起動

開発中は次のコマンドで起動できます。

```bash
uv run uvicorn app.main:app --reload
```

ブラウザで `http://localhost:8000` を開いてください。

## デプロイ (Shinjiru / pm.vorlors.com)

本番デプロイ手順(VPSへのセットアップ、nginx、SSL、systemd)と、`pm.vorlors.com` のDNSサーバー設定方法は **[DNS.md](./DNS.md)** にまとめられています。

## データ保存

既定では、SQLiteデータベースを `data/projectm.db` に保存します。別の場所を使う場合は、次のように指定できます。

```dotenv
PW_DATA_DIR=/path/to/data
# または
PW_DB_URL=sqlite:////path/to/projectm.db
```

監視履歴、登録サイト、キーワード、ユーザー設定はこのデータベースに保存されます。

## APIのヘルスチェック

```text
GET /api/health
```

正常に動作していれば、`ok` と次回チェック時刻が返ります。

## テスト

```bash
uv run pytest
```

## 注意点

- 登録するURLは、公開されているHTTPまたはHTTPSのウェブサイトに限られます。
- 内部ネットワーク、localhost、プライベートIPアドレスへのアクセスは拒否します。
- パスワード、署名鍵、TelegramトークンなどはGitへコミットしないでください。
- このツールはページの変化を知らせるものです。重要な手続きや期限については、必ず公式サイトを直接確認してください。

## 技術構成

Project Mは、FastAPI、SQLAlchemy、SQLite、APScheduler、Jinja2を使ったサーバーアプリケーションです。スマートフォンでも使いやすいPWAとして動作し、サイト取得には通常のHTTPクライアントを使い、利用できる環境ではブラウザに近いアクセス方法も使います。検索エンジンモードは httpx で DuckDuckGo(html.duckduckgo.com / links.duckduckgo.com)と Brave Search API を直接呼び出します(追加の依存ライブラリはありません)。
