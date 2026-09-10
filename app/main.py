"""ProjectW FastAPI アプリ本体."""
import datetime as dt
import http.cookies
import re
import threading
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.datastructures import MutableHeaders
from starlette.types import Message, Receive, Scope, Send
from starlette_csrf import CSRFMiddleware
from sqlalchemy.orm import Session as OrmSession
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from . import auth, config, db as dbmod, scheduler
from .i18n import COOKIE_NAME as LANG_COOKIE, SUPPORTED_LANGUAGES, TRANSLATIONS, template_context as i18n_context
from .models import Keyword, Run, Schedule, Site, User
from .scraper_engine import run_scan

app = FastAPI(title="ProjectW")
templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))
limiter = Limiter(key_func=get_remote_address, headers_enabled=True)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


COOKIE = "pw_session"


def _csrf_token_valid(token: str) -> bool:
    """現在の SECRET_KEY で復号できる(=今回のデプロイが発行した)トークンか."""
    from itsdangerous.url_safe import URLSafeSerializer
    try:
        URLSafeSerializer(config.SECRET_KEY, "csrftoken").loads(token)
        return True
    except Exception:
        return False


def _new_csrf_cookie() -> str:
    """starlette_csrf と同じ形式で新しい csrftoken クッキー文字列を生成."""
    import secrets
    from itsdangerous.url_safe import URLSafeSerializer
    token = URLSafeSerializer(config.SECRET_KEY, "csrftoken").dumps(secrets.token_urlsafe(128))
    c = http.cookies.SimpleCookie()
    c["csrftoken"] = token
    c["csrftoken"]["path"] = "/"
    c["csrftoken"]["secure"] = config.COOKIE_SECURE
    c["csrftoken"]["httponly"] = False
    c["csrftoken"]["samesite"] = "lax"
    return c.output(header="").strip()


class _CSRFCookieRefreshMiddleware:
    """stale な csrftoken クッキーを自動で再発行する。

    starlette_csrf はクッキーが「存在しない」場合のみ発行するため、
    PW_SECRET_KEY 更新前の古いトークンがブラウザに残り続けるとログインが
    403 (CSRF token verification failed) で詰む。このミドルウェアは
    リクエストの csrftoken が現在の secret で復号できない(stale)場合に、
    そのレスポンスへ新しいクッキーを付与して次回以降を修復する。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        cookie = Request(scope).cookies.get("csrftoken")
        stale = bool(cookie) and not _csrf_token_valid(cookie)

        async def send_wrapper(message: Message):
            if stale and message["type"] == "http.response.start":
                MutableHeaders(scope=message).append(
                    "set-cookie", _new_csrf_cookie())
            await send(message)

        await self.app(scope, receive, send_wrapper)


# 既存OSSのCSRF middlewareを使用。状態変更APIだけを保護する。
app.add_middleware(
    CSRFMiddleware,
    secret=config.SECRET_KEY,
    required_urls=[re.compile(r"^/auth/(magic|password)$"),
                   re.compile(r"^/api/")],
    sensitive_cookies={COOKIE},
    cookie_secure=config.COOKIE_SECURE,
    cookie_httponly=False,
    cookie_samesite="lax",
    header_name="x-csrftoken",
)
# CSRF の外側(後で追加した方が外側になる)。stale トークンの自動修復。
app.add_middleware(_CSRFCookieRefreshMiddleware)
def template_context(request: Request, values=None):
    values = i18n_context(request, values)
    values.setdefault("u", None)
    return values


@app.on_event("startup")
def _startup():
    config.validate_production_config()
    dbmod.init_db()
    scheduler.start()


def get_db():
    db = dbmod.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def current_user(request: Request, db: OrmSession = Depends(get_db)):
    tok = request.cookies.get(COOKIE)
    if not tok:
        return None
    data = auth.decode_session_jwt(tok)
    if not data:
        return None
    u = db.query(User).filter(User.id == int(data["sub"])).first()
    if not u or u.is_frozen:
        return None
    return u


def require_user(request: Request, db: OrmSession = Depends(get_db)):
    u = current_user(request, db)
    if not u:
        raise HTTPException(status_code=401, detail="ログインが必要です")
    return u


def require_admin(request: Request, db: OrmSession = Depends(get_db)):
    u = current_user(request, db)
    if not u or u.role != "admin":
        raise HTTPException(status_code=403, detail="管理者権限が必要です")
    return u


def require_editor(request: Request, db: OrmSession = Depends(get_db)):
    u = current_user(request, db)
    if not u or u.role not in ("admin", "editor"):
        raise HTTPException(status_code=403, detail="編集権限が必要です")
    return u


# ---------------- 認証 ----------------
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    ctx = template_context(request)
    import json as _json
    lang = ctx.get("lang", "ja")
    msgs = {
        "sending": TRANSLATIONS.get(lang, {}).get("scanning_now", "送信中…"),
        "link_sent": TRANSLATIONS.get(lang, {}).get("link_sent", "マジックリンクを送信しました"),
        "send_failed": TRANSLATIONS.get(lang, {}).get("send_failed", "送信に失敗しました"),
        "logged_in": TRANSLATIONS.get(lang, {}).get("updated", "ログインしました"),
        "login_failed": TRANSLATIONS.get(lang, {}).get("invalid_credentials", "ログインに失敗しました"),
    }
    ctx["msgs_json"] = _json.dumps(msgs, ensure_ascii=False)
    return templates.TemplateResponse(request, "login.html", ctx)


@app.get("/language/{lang}")
def set_language(lang: str, request: Request):
    if lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail="対応していない言語です")
    next_url = request.query_params.get("next", "/")
    parsed = urlsplit(next_url)
    next_url = parsed.path or "/"
    if parsed.scheme or parsed.netloc or not next_url.startswith("/") or next_url.startswith("//"):
        next_url = "/"
    elif parsed.query:
        next_url += "?" + parsed.query
    resp = RedirectResponse(next_url, status_code=303)
    resp.set_cookie(LANG_COOKIE, lang, max_age=31536000, samesite="lax")
    return resp


@app.post("/auth/magic")
@limiter.limit("3/15minutes")
def request_magic(request: Request, email: str = Form(...), db: OrmSession = Depends(get_db)):
    email = email.strip().lower()
    u = db.query(User).filter(User.email == email).first()
    if not u:
        # 情報漏洩を防ぐため常に成功レスポンス
        return JSONResponse({"ok": True, "msg": "リンクを送信しました(登録済みの場合)"})
    if u.is_frozen:
        return JSONResponse({"ok": False, "msg": "アカウントが凍結されています"}, status_code=403)
    token = auth.make_magic_token(email, db)
    link = f"{config.PUBLIC_BASE_URL}/auth/verify?token={token}"
    ok, info = auth.send_magic_email(email, link)
    return JSONResponse({"ok": ok, "msg": "ログインリンクを送信しました" if ok else f"送信失敗: {info}"})


def _login_error_response(request: Request, status_code: int, detail: str):
    """ログイン失敗レスポンス。HTMLクライアント(ネイティブPOSTフォールバック)は
    /login?error=1 へリダイレクトし、JSONクライアント(fetch)は401/403を返す。"""
    if "text/html" in request.headers.get("accept", ""):
        return RedirectResponse("/login?error=1", status_code=303)
    raise HTTPException(status_code=status_code, detail=detail)


@app.post("/auth/password")
@limiter.limit("5/minute")
def login_password(request: Request, email: str = Form(...), password: str = Form(...),
                   db: OrmSession = Depends(get_db)):
    wants_html = "text/html" in request.headers.get("accept", "")
    email = email.strip().lower()
    u = db.query(User).filter(User.email == email).first()
    bad = (not u or not u.password_hash or not auth.verify_password(password, u.password_hash))
    if bad or u.is_frozen:
        detail = "メールまたはパスワードが違います" if bad else "アカウントが凍結されています"
        _login_error_response(request, 401 if bad else 403, detail)
    u.last_login = dt.datetime.now(dt.timezone.utc)
    db.commit()
    if wants_html:
        resp = RedirectResponse("/", status_code=303)
    else:
        resp = JSONResponse({"ok": True, "redirect": "/"})
    resp.set_cookie(COOKIE, auth.make_session_jwt(u), httponly=True,
                    max_age=config.SESSION_TTL, samesite="lax", secure=config.COOKIE_SECURE)
    return resp


@app.get("/auth/verify")
def verify_magic(token: str, db: OrmSession = Depends(get_db)):
    email = auth.verify_magic_token(token, db)
    if not email:
        return HTMLResponse("<h3>リンクが無効または期限切れです</h3>", status_code=400)
    u = db.query(User).filter(User.email == email).first()
    if not u or u.is_frozen:
        return HTMLResponse("<h3>アカウントが無効です</h3>", status_code=403)
    u.last_login = dt.datetime.now(dt.timezone.utc)
    db.commit()
    resp = RedirectResponse("/", status_code=302)
    resp.set_cookie(COOKIE, auth.make_session_jwt(u), httponly=True,
                    max_age=config.SESSION_TTL, samesite="lax", secure=config.COOKIE_SECURE)
    return resp


@app.post("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie(COOKIE)
    return resp


# ---------------- ダッシュボード ----------------
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: OrmSession = Depends(get_db)):
    u = current_user(request, db)
    if not u:
        return RedirectResponse("/login", status_code=302)
    runs = db.query(Run).order_by(Run.started_at.desc()).limit(10).all()
    last = runs[0] if runs else None
    stats = {
        "sites": db.query(Site).count(),
        "sites_on": db.query(Site).filter(Site.enabled == True).count(),  # noqa: E712
        "keywords": db.query(Keyword).count(),
        "users": db.query(User).count(),
        "next_run": scheduler.next_run_time(),
        "last": last,
    }
    return templates.TemplateResponse(request, "dashboard.html",
                                      template_context(request, {"u": u, "stats": stats, "runs": runs, "active_page": "home"}))


@app.get("/sites", response_class=HTMLResponse)
def sites_page(request: Request, db: OrmSession = Depends(get_db)):
    u = current_user(request, db)
    if not u:
        return RedirectResponse("/login", status_code=302)
    sites = db.query(Site).order_by(Site.id).all()
    kws = db.query(Keyword).order_by(Keyword.id).all()
    return templates.TemplateResponse(request, "sites.html",
                                      template_context(request, {"u": u, "sites": sites, "kws": kws, "active_page": "sites"}))


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: OrmSession = Depends(get_db)):
    u = current_user(request, db)
    if not u:
        return RedirectResponse("/login", status_code=302)
    sched = db.query(Schedule).first()
    users = db.query(User).order_by(User.id).all() if u.role == "admin" else []
    return templates.TemplateResponse(request, "settings.html",
                                      template_context(request, {"u": u, "sched": sched, "users": users, "active_page": "settings"}))


# ---------------- サイト CRUD ----------------
@app.post("/api/sites")
def add_site(url: str = Form(...), label: str = Form(""), profile: str = Form("chrome"),
             db: OrmSession = Depends(get_db), u: User = Depends(require_editor)):
    url = url.strip()
    from .scraper_engine import validate_target_url
    safe, reason = validate_target_url(url)
    if not safe:
        raise HTTPException(400, f"監視先URLを登録できません: {reason}")
    if db.query(Site).filter(Site.url == url).first():
        raise HTTPException(400, "既に登録済みのURLです")
    db.add(Site(url=url, label=label, profile=profile, enabled=True))
    db.commit()
    return {"ok": True}


@app.put("/api/sites/{sid}")
def update_site(sid: int, url: str = Form(None), label: str = Form(None),
                profile: str = Form(None), enabled: str = Form(None),
                db: OrmSession = Depends(get_db), u: User = Depends(require_editor)):
    s = db.get(Site, sid)
    if not s:
        raise HTTPException(404, "見つかりません")
    if url is not None:
        from .scraper_engine import validate_target_url
        url = url.strip()
        safe, reason = validate_target_url(url)
        if not safe:
            raise HTTPException(400, f"監視先URLを変更できません: {reason}")
        s.url = url
    if label is not None:
        s.label = label
    if profile is not None:
        s.profile = profile
    if enabled is not None:
        s.enabled = enabled in ("1", "true", "on", "True")
    db.commit()
    return {"ok": True}


@app.delete("/api/sites/{sid}")
def delete_site(sid: int, db: OrmSession = Depends(get_db), u: User = Depends(require_editor)):
    s = db.get(Site, sid)
    if s:
        db.delete(s)
        db.commit()
    return {"ok": True}


# ---------------- キーワード CRUD ----------------
@app.post("/api/keywords")
def add_keyword(term: str = Form(...), label: str = Form(""), db: OrmSession = Depends(get_db),
                u: User = Depends(require_editor)):
    term = term.strip()
    if db.query(Keyword).filter(Keyword.term == term).first():
        raise HTTPException(400, "既に登録済みです")
    db.add(Keyword(term=term, label=label.strip(), enabled=True))
    db.commit()
    return {"ok": True}


@app.put("/api/keywords/{kid}")
def update_keyword(kid: int, term: str = Form(""), label: str = Form(""), enabled: str = Form(""),
                   db: OrmSession = Depends(get_db), u: User = Depends(require_editor)):
    k = db.get(Keyword, kid)
    if not k:
        raise HTTPException(404, "キーワードがありません")
    if term and term.strip():
        t2 = term.strip()
        dup = db.query(Keyword).filter(Keyword.term == t2, Keyword.id != kid).first()
        if dup:
            raise HTTPException(400, "既に登録済みです")
        k.term = t2
    k.label = label.strip()
    if enabled in ("1", "0"):
        k.enabled = (enabled == "1")
    db.commit()
    return {"ok": True}


@app.delete("/api/keywords/{kid}")
def delete_keyword(kid: int, db: OrmSession = Depends(get_db),
                   u: User = Depends(require_editor)):
    k = db.get(Keyword, kid)
    if k:
        db.delete(k)
        db.commit()
    return {"ok": True}


# ---------------- 手動スキャン ----------------
@app.post("/api/scan")
@limiter.limit("1/minute")
def manual_scan(request: Request, db: OrmSession = Depends(get_db), u: User = Depends(require_editor)):
    def _bg():
        run_scan(dbmod.SessionLocal, trigger="manual", notify=dbmod.telegram_notify)
    threading.Thread(target=_bg, daemon=True).start()
    return {"ok": True, "msg": "スキャンを開始しました"}


# ---------------- スケジュール ----------------
@app.post("/api/schedule")
def update_schedule(mode: str = Form(...), interval_hours: int = Form(6),
                    daily_times: str = Form(""), cron_expr: str = Form(""),
                    max_runs_per_day: int = Form(0), timezone: str = Form("Asia/Kuala_Lumpur"),
                    enabled: str = Form("on"), db: OrmSession = Depends(get_db),
                    u: User = Depends(require_editor)):
    s = db.query(Schedule).first()
    if not s:
        s = Schedule()
        db.add(s)
    s.mode = mode
    s.interval_hours = interval_hours
    s.daily_times = daily_times
    s.cron_expr = cron_expr
    s.max_runs_per_day = max_runs_per_day
    s.timezone = timezone
    s.enabled = enabled in ("1", "true", "on", "True")
    db.commit()
    scheduler.reconfigure()
    return {"ok": True, "next_run": scheduler.next_run_time()}


# ---------------- ユーザー管理 (Admin) ----------------
@app.post("/api/users")
def add_user(email: str = Form(...), name: str = Form(""), role: str = Form("viewer"),
             db: OrmSession = Depends(get_db), u: User = Depends(require_admin)):
    email = email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "既に存在します")
    nu = User(email=email, name=name, role=role if role in ("admin", "editor", "viewer") else "viewer")
    db.add(nu)
    db.commit()
    # 招待マジックリンク送信
    token = auth.make_magic_token(email, db)
    link = f"{config.PUBLIC_BASE_URL}/auth/verify?token={token}"
    auth.send_magic_email(email, link)
    return {"ok": True, "msg": "ユーザーを追加し招待リンクを送信しました"}


@app.put("/api/users/{uid}")
def update_user(uid: int, name: str = Form(None), role: str = Form(None),
                frozen: str = Form(None), db: OrmSession = Depends(get_db),
                u: User = Depends(require_admin)):
    tu = db.get(User, uid)
    if not tu:
        raise HTTPException(404, "見つかりません")
    if tu.email == config.SUPERUSER_EMAIL.lower() and (role and role != "admin"):
        raise HTTPException(400, "スーパーユーザーのロールは変更できません")
    if name is not None:
        tu.name = name
    if role is not None and role in ("admin", "editor", "viewer"):
        tu.role = role
    if frozen is not None:
        if tu.email == config.SUPERUSER_EMAIL.lower():
            raise HTTPException(400, "スーパーユーザーは凍結できません")
        tu.is_frozen = frozen in ("1", "true", "on", "True")
    db.commit()
    return {"ok": True}


@app.delete("/api/users/{uid}")
def delete_user(uid: int, db: OrmSession = Depends(get_db), u: User = Depends(require_admin)):
    tu = db.get(User, uid)
    if not tu:
        raise HTTPException(404, "見つかりません")
    if tu.email == config.SUPERUSER_EMAIL.lower():
        raise HTTPException(400, "スーパーユーザーは削除できません")
    db.delete(tu)
    db.commit()
    return {"ok": True}


@app.get("/static/sw.js")
def service_worker():
    """SW をルートスコープで登録できるようヘッダ付きで配信."""
    from fastapi.responses import FileResponse
    return FileResponse(str(config.BASE_DIR / "static" / "sw.js"),
                        media_type="application/javascript",
                        headers={"Service-Worker-Allowed": "/"})


app.mount("/static", StaticFiles(directory=str(config.BASE_DIR / "static")), name="static")


@app.get("/api/health")
def health():
    return {"ok": True, "next_run": scheduler.next_run_time()}
