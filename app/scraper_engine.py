"""スクレイピングエンジン. curl_cffi があれば使い、無ければ httpx にフォールバック.
DB のサイト/キーワードを対象に実行し、Run/Hit を記録する。"""
import datetime as dt
import hashlib
import html as htmllib
import random
import re
import socket
import time
import httpx
from ipaddress import ip_address
from urllib.parse import urljoin, urlsplit

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


def validate_target_url(url: str) -> tuple[bool, str]:
    """Reject non-web and non-public destinations before server-side fetching."""
    try:
        p = urlsplit(url.strip())
        if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
            return False, "unsupported URL"
        if p.port is not None and not (1 <= p.port <= 65535):
            return False, "invalid port"
        for info in socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80),
                                       type=socket.SOCK_STREAM):
            ip = ip_address(info[4][0])
            if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                    or ip.is_unspecified or ip.is_multicast):
                return False, "private destination"
        return True, ""
    except (ValueError, OSError):
        return False, "invalid or unresolved host"


def _read_limited(response):
    """Read a bounded response body, protecting workers from oversized pages."""
    length = response.headers.get("content-length")
    if length and int(length) > config.MAX_RESPONSE_BYTES:
        raise ValueError("response too large")
    chunks, total = [], 0
    for chunk in response.iter_bytes(65536):
        total += len(chunk)
        if total > config.MAX_RESPONSE_BYTES:
            raise ValueError("response too large")
        chunks.append(chunk)
    return b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")

try:
    from curl_cffi import requests as creq
    _HAS_CURL_CFFI = True
except Exception:
    _HAS_CURL_CFFI = False


def _fetch(url: str, profile: str = "chrome"):
    """戻り値 (status, text_body or None, error or None)."""
    err = None
    content_type = ""
    safe, reason = validate_target_url(url)
    if not safe:
        return None, None, reason
    for attempt in range(3):
        try:
            if _HAS_CURL_CFFI:
                r = creq.get(url, impersonate=profile or "chrome",
                             timeout=config.REQUEST_TIMEOUT, verify=True,
                             allow_redirects=False)
                if int(r.headers.get("content-length", "0") or 0) > config.MAX_RESPONSE_BYTES:
                    raise ValueError("response too large")
                status, body = r.status_code, r.text[:config.MAX_RESPONSE_BYTES]
            else:
                with httpx.Client(timeout=config.REQUEST_TIMEOUT, verify=True,
                                  follow_redirects=False,
                                  headers={"User-Agent": "Mozilla/5.0"}) as c:
                    with c.stream("GET", url) as r:
                        if int(r.headers.get("content-length", "0") or 0) > config.MAX_RESPONSE_BYTES:
                            raise ValueError("response too large")
                        raw = bytearray()
                        for chunk in r.iter_bytes(65536):
                            raw.extend(chunk)
                            if len(raw) > config.MAX_RESPONSE_BYTES:
                                raise ValueError("response too large")
                        status = r.status_code
                        body = bytes(raw).decode(r.encoding or "utf-8", errors="replace")
                        location = r.headers.get("location")
                        current_url = str(r.url)
                        content_type = r.headers.get("content-type", "").lower()
                    redirects = 0
                    while status in (301, 302, 303, 307, 308) and redirects < config.MAX_REDIRECTS:
                        if not location:
                            break
                        next_url = urljoin(current_url, location)
                        safe, reason = validate_target_url(next_url)
                        if not safe:
                            return None, None, reason
                        with c.stream("GET", next_url) as r:
                            if int(r.headers.get("content-length", "0") or 0) > config.MAX_RESPONSE_BYTES:
                                raise ValueError("response too large")
                            raw = bytearray()
                            for chunk in r.iter_bytes(65536):
                                raw.extend(chunk)
                                if len(raw) > config.MAX_RESPONSE_BYTES:
                                    raise ValueError("response too large")
                            status = r.status_code
                            body = bytes(raw).decode(r.encoding or "utf-8", errors="replace")
                            location = r.headers.get("location")
                            current_url = str(r.url)
                            content_type = r.headers.get("content-type", "").lower()
                        redirects += 1
                    if status in (301, 302, 303, 307, 308):
                        return None, None, "too many redirects"
            if status in (429, 503) and attempt < 2:
                time.sleep(10 * (attempt + 1))
                continue
            if status == 200 and content_type and not any(t in content_type for t in ("text/html", "application/xhtml+xml")):
                return status, None, "unsupported content type"
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
