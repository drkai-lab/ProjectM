"""スクレイピングエンジン. curl_cffi があれば使い、無ければ httpx にフォールバック.
DB のサイト/キーワードを対象に実行し、Run/Hit を記録する。"""
import datetime as dt
import hashlib
import html as htmllib
import random
import re
import time

from . import config
from .models import Hit, Keyword, Run, Site

NOTIFICATION_HEADINGS = {
    "zh": {"hits": "关键词命中", "failures": "获取失败", "updates": "更新"},
    "ja": {"hits": "キーワードヒット", "failures": "取得失敗", "updates": "更新"},
    "en": {"hits": "Keyword Hits", "failures": "Failures", "updates": "Updates"},
    "ms": {"hits": "Padanan Kata Kunci", "failures": "Kegagalan", "updates": "Kemas Kini"},
    "ko": {"hits": "키워드 적중", "failures": "실패", "updates": "업데이트"},
}


def format_notification(lang, hits, failures, updated=0):
    headings = NOTIFICATION_HEADINGS.get(lang, NOTIFICATION_HEADINGS["zh"])
    parts = []
    if hits:
        parts.append(f"【{headings['hits']}】\n" + "\n\n".join(hits))
    if failures:
        parts.append(f"【{headings['failures']}】\n" + "\n".join(failures))
    if updated:
        parts.append(f"【{headings['updates']}: {updated}】")
    return "\n\n".join(parts)

try:
    from curl_cffi import requests as creq
    _HAS_CURL_CFFI = True
except Exception:
    import httpx
    _HAS_CURL_CFFI = False


def _fetch(url: str, profile: str = "chrome"):
    """戻り値 (status, text_body or None, error or None)."""
    err = None
    for attempt in range(3):
        try:
            if _HAS_CURL_CFFI:
                r = creq.get(url, impersonate=profile or "chrome",
                             timeout=config.REQUEST_TIMEOUT, verify=False,
                             allow_redirects=True)
                status, body = r.status_code, r.text
            else:
                with httpx.Client(timeout=config.REQUEST_TIMEOUT, verify=False,
                                  follow_redirects=True,
                                  headers={"User-Agent": "Mozilla/5.0"}) as c:
                    r = c.get(url)
                    status, body = r.status_code, r.text
            if status in (429, 503) and attempt < 2:
                time.sleep(10 * (attempt + 1))
                continue
            return status, body, None
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            if attempt < 2:
                time.sleep(5)
    return None, None, err


def extract_text(html: str) -> str:
    s = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = htmllib.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def run_scan(SessionLocal, trigger: str = "manual", notify=None):
    """1回のフルスキャンを実行。notify(text) はコールバック(Telegram等)."""
    db = SessionLocal()
    run = Run(trigger=trigger, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    sites = db.query(Site).filter(Site.enabled == True).all()  # noqa: E712
    keywords = [k.term for k in db.query(Keyword).filter(Keyword.enabled == True).all()]  # noqa: E712
    run.total = len(sites)
    hits, failures, updated = [], [], 0

    for site in sites:
        status, body, err = _fetch(site.url, site.profile)
        site.last_checked = dt.datetime.now(dt.timezone.utc)
        site.last_status = status or 0
        if body is None or status != 200:
            failures.append(f"❌ {site.url} — {err or f'HTTP {status}'}")
            db.commit()
            continue
        run.ok += 1
        text = extract_text(body)
        h = hashlib.sha256(text.encode()).hexdigest()[:16]
        prev = site.last_hash
        if prev and prev != h:
            updated += 1
            matched = [k for k in keywords if k.lower() in text.lower()]
            if matched:
                snippet = text[:300]
                hit = Hit(run_id=run.id, url=site.url,
                          matched=", ".join(matched), snippet=snippet)
                db.add(hit)
                hits.append(f"🔔 {site.url}\n   keywords: {', '.join(matched)}\n   {snippet}...")
        site.last_hash = h
        db.commit()
        time.sleep(1 + random.random() * 2)

    run.updated = updated
    run.hits = len(hits)
    run.failed = len(failures)
    run.finished_at = dt.datetime.now(dt.timezone.utc)
    run.status = "done"
    db.commit()

    if notify:
        import os
        lang = os.getenv("PW_NOTIFY_LANG", getattr(config, "NOTIFY_LANG", "zh"))
        parts = format_notification(lang, hits, failures, updated)
        if parts:
            notify(parts)

    rid = run.id
    db.close()
    return rid
