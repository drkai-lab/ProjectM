# ProjectM デプロイ & DNS 設定 (pm.vorlors.com @ Shinjiru)

本ドキュメントは、ProjectM を **Shinjiru の VPS** にデプロイし、**`https://pm.vorlors.com`** で公開するための手順をまとめたものです。

1. [VPS のIPアドレスを確認する](#1-vps-のipアドレスを確認する)
2. [DNSレコードを設定する (A レコード)](#2-dnsレコードを設定する-a-レコード)
3. [DNS反映の確認](#3-dns反映の確認)
4. [VPS へのデプロイ (Ubuntu 22.04/24.04 想定)](#4-vps-への-deploy)
5. [SSL証明書 (Let's Encrypt / certbot)](#5-ssl証明書-letsencrypt--certbot)
6. [nginx の設定](#6-nginx-の設定)
7. [ファイアウォール](#7-ファイアウォール)
8. [最終確認](#8-最終確認)
9. [更新時の手順 (git pull)](#9-更新時の手順-git-pull)

---

## 1. VPS のIPアドレスを確認する

Shinjiru クライアントエリア (https://www.shinjiru.com/member/) にログインし、対象VPSの **パブリックIPv4アドレス** を確認します。以下では `203.0.113.10` と仮定しています(実際には自分のIPに置き換えてください)。

> 参考: ローカルマシンから既知の Shinjiru VPS は `35.226.183.100` (known_hosts に登録済み) です。SSHポート22が閉じている場合は、クライアントエリアでVPSの再起動またはファイアウォール設定を確認してください。

## 2. DNSレコードを設定する (A レコード)

ドメイン `vorlors.com` を管理している **レジストラ/ネームサーバー** の管理画面(例: Cloudflare, GoDaddy, Namecheap, お使いのDNSプロバイダ)にログインし、以下のレコードを追加します。

| 種類 | ホスト (名前) | 値 (ポイント先) | TTL |
| --- | --- | --- | --- |
| **A** | `pm` | `<VPSのパブリックIPv4>` (例: `203.0.113.10`) | `300` (5分) ※安定後に3600へ変更可 |

- 「ホスト」欄に `@` ではなく **`pm`** と入力すると、`pm.vorlors.com` が作成されます
- IPv6アドレスがある場合は、同様に **AAAA** レコードも追加できます(任意)
- Cloudflare を使っている場合: プロキシ(オレンジクラウド)でもDNSのみのグレークラウドでも動作しますが、初回は **DNSのみ (グレー)** にして certbot のHTTP検証を通すのが確実です。証明書取得後にプロキシに戻しても構いません

### レジストラ別の操作例

**Cloudflare**
1. ダッシュボード → vorlors.com → DNS → Records
2. 「Add record」: Type=`A`, Name=`pm`, IPv4 address=`<VPS IP>`, Proxy status=「DNS only」, TTL=Auto(300)
3. Save

**GoDaddy / Namecheap 等**
1. DNS管理画面を開く
2. レコード追加: Type=`A`, Host/Name=`pm`, Points to/Value=`<VPS IP>`, TTL=300
3. 保存

## 3. DNS反映の確認

```bash
# Windows (PowerShell)
Resolve-DnsName pm.vorlors.com -Type A
nslookup pm.vorlors.com 8.8.8.8

# Linux / macOS
dig +short pm.vorlors.com A
host pm.vorlors.com
```

VPSのIPが返れば反映完了です。通常は数分〜1時間、TTLやネームサーバーのキャッシュによっては最大24時間かかる場合があります。

## 4. VPS へのデプロイ (Ubuntu 22.04/24.04 想定)

VPSにSSHで接続して以下を実行します(ユーザーは `root` または sudo ユーザー)。

### 4-1. 基本パッケージと uv のインストール

```bash
apt update && apt -y upgrade
apt install -y git nginx python3-pip curl
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc   # uv を PATH に追加 (または export PATH="$HOME/.local/bin:$PATH")
```

### 4-2. アプリの取得とセットアップ

```bash
mkdir -p /opt/projectm && cd /opt/projectm
git clone https://github.com/<あなたのGitHub>/ProjectM.git .
# または fork を origin に設定済みなら: git pull
uv sync --frozen
```

### 4-3. 本番環境変数 (.env)

```bash
cd /opt/projectm
cat > .env <<'EOF'
PW_ENV=production
# 生成方法: python -c "import secrets; print(secrets.token_urlsafe(48))"
PW_SECRET_KEY=<64文字のランダム文字列>
PW_ROOT_EMAIL=root@<あなたのドメイン>
PW_ROOT_PASSWORD=<rootのパスワード>
PW_SUPERUSER_EMAIL=admin@<あなたのドメイン>
PW_SUPERUSER_PASSWORD=<スーパーユーザーのパスワード>
PW_TZ=Asia/Kuala_Lumpur
PW_PUBLIC_URL=https://pm.vorlors.com
PW_COOKIE_SECURE=1
# 任意: Telegram通知 / メール / BraveSearch
PW_TELEGRAM_TOKEN=
PW_TELEGRAM_CHAT_ID=
PW_NOTIFY_LANG=ja
RESEND_API_KEY=
PW_MAIL_FROM=ProjectM <onboarding@resend.dev>
BRAVE_SEARCH_API_KEY=<Brave Search APIキー(任意)>
EOF
chmod 600 .env
```

### 4-4. systemd サービス (gunicorn + uvicorn worker)

`/etc/systemd/system/projectm.service`:

```ini
[Unit]
Description=ProjectM - MyGov Monitor dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/projectm
EnvironmentFile=/opt/projectm/.env
ExecStart=/opt/projectm/.venv/bin/gunicorn app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 2 --bind 127.0.0.1:8000 --timeout 60
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now projectm
systemctl status projectm   # active (running) を確認
curl -s http://127.0.0.1:8000/api/health   # {"ok":true,...} が返ればOK
```

## 5. SSL証明書 (Let's Encrypt / certbot)

DNS(Aレコード)が反映されたことを確認してから実行します。

```bash
apt install -y certbot python3-certbot-nginx
# 先に nginx を最小設定(下記6のserverブロックを port 80 のみで)入れてから:
certbot --nginx -d pm.vorlors.com
# メールアドレス入力 → 同意 → 自動リニューアル有効化の確認で Yes
```

自動更新は systemd タイマー(`certbot.timer`)で毎週確認されます。動作確認: `sudo certbot renew --dry-run`

## 6. nginx の設定

`/etc/nginx/sites-available/projectm.conf`:

```nginx
server {
    listen 80;
    server_name pm.vorlors.com;

    # certbot が自動で 443/server_block を追加します。手動の場合は以下も追記:
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    client_max_body_size 5m;
}
```

```bash
ln -s /etc/nginx/sites-available/projectm.conf /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default   # デフォルトサイトと競合する場合
nginx -t && systemctl reload nginx
```

## 7. ファイアウォール

```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'     # 80/443
ufw enable
ufw status
```

Shinjiru の管理画面に独自のファイアウォール機能がある場合は、そちらでも **22 / 80 / 443** を許可してください。

## 8. 最終確認

1. ブラウザで `https://pm.vorlors.com` を開く → ログイン画面が表示される
2. root アカウント(`PW_ROOT_EMAIL`)でログインできる
3. 設定画面に「ユーザーグループ管理」セクションが表示される
4. 下部ナビの「関連語検索」から単語を検索し、DuckDuckGo の結果と関連語候補が表示される
5. `BRAVE_SEARCH_API_KEY` を設定している場合、BraveSearch の結果も表示される(未設定時は「APIキー未設定」バッジ)

## 9. 更新時の手順 (git pull)

```bash
cd /opt/projectm
git pull origin main
uv sync --frozen          # 依存関係に変更がある場合のみ
systemctl restart projectm
```

DBは SQLite (`/opt/projectm/data/projectm.db`) なので、バックアップはこのファイルと `.env` をコピーしてください。

---

### トラブルシューティング

| 症状 | 確認事項 |
| --- | --- |
| pm.vorlors.com が解決しない | Aレコードのホストが `pm` (pm.pm や @ ではないか)、TTL/キャッシュ、ネームサーバー設定 |
| 502 Bad Gateway | `systemctl status projectm` でアプリ起動中か確認。`journalctl -u projectm -n 50` |
| ログイン後 403 (CSRF) | `PW_COOKIE_SECURE=1` のまま http:// でアクセスしていないか(https 必須)。SECRET_KEY 変更後は再ログイン |
| SSL更新失敗 | DNSがAレコードでVPSを指しているか、80ポートが開いているかを確認 |
