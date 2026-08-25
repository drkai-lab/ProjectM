"""ProjectW FastAPI アプリ本体."""
import datetime as dt
import threading
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session as OrmSession

from . import auth, config, db as dbmod, scheduler
from .i18n import COOKIE_NAME as LANG_COOKIE, SUPPORTED_LANGUAGES, template_context as i18n_context
from .models import Hit, Keyword, Run, Schedule, Site, User
from .scraper_engine import run_scan

app = FastAPI(title="ProjectW")
templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))


COOKIE = "pw_session"
def template_context(request: Request, values=None):
    values = i18n_context(request, values)
    values.setdefault("u", None)
    return values


@app.on_event("startup")
def _startup():
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
    return templates.TemplateResponse(request, "login.html", template_context(request))


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
def request_magic(email: str = Form(...), db: OrmSession = Depends(get_db)):
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


@app.post("/auth/password")
def login_password(email: str = Form(...), password: str = Form(...),
                   db: OrmSession = Depends(get_db)):
    email = email.strip().lower()
    u = db.query(User).filter(User.email == email).first()
    if not u or not u.password_hash or not auth.verify_password(password, u.password_hash):
        raise HTTPException(status_code=401, detail="メールまたはパスワードが違います")
    if u.is_frozen:
        raise HTTPException(status_code=403, detail="アカウントが凍結されています")
    u.last_login = dt.datetime.now(dt.timezone.utc)
    db.commit()
    resp = JSONResponse({"ok": True, "redirect": "/"})
    resp.set_cookie(COOKIE, auth.make_session_jwt(u), httponly=True,
                    max_age=config.SESSION_TTL, samesite="lax")
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
                    max_age=config.SESSION_TTL, samesite="lax")
    return resp


@app.get("/logout")
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
    if db.query(Site).filter(Site.url == url).first():
        raise HTTPException(400, "既に登録済みのURLです")
    db.add(Site(url=url, label=label, profile=profile, enabled=True))
    db.commit()
    return {"ok": True}


@app.put("/api/sites/{sid}")
def update_site(sid: int, url: str = Form(None), label: str = Form(None),
                profile: str = Form(None), enabled: str = Form(None),
                db: OrmSession = Depends(get_db), u: User = Depends(require_editor)):
    s = db.query(Site).get(sid)
    if not s:
        raise HTTPException(404, "見つかりません")
    if url is not None:
        s.url = url.strip()
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
    s = db.query(Site).get(sid)
    if s:
        db.delete(s)
        db.commit()
    return {"ok": True}


# ---------------- キーワード CRUD ----------------
@app.post("/api/keywords")
def add_keyword(term: str = Form(...), db: OrmSession = Depends(get_db),
                u: User = Depends(require_editor)):
    term = term.strip()
    if db.query(Keyword).filter(Keyword.term == term).first():
        raise HTTPException(400, "既に登録済みです")
    db.add(Keyword(term=term, enabled=True))
    db.commit()
    return {"ok": True}


@app.delete("/api/keywords/{kid}")
def delete_keyword(kid: int, db: OrmSession = Depends(get_db),
                   u: User = Depends(require_editor)):
    k = db.query(Keyword).get(kid)
    if k:
        db.delete(k)
        db.commit()
    return {"ok": True}


# ---------------- 手動スキャン ----------------
@app.post("/api/scan")
def manual_scan(db: OrmSession = Depends(get_db), u: User = Depends(require_editor)):
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
    tu = db.query(User).get(uid)
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
    tu = db.query(User).get(uid)
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
