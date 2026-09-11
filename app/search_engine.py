"""検索エンジンモード: DuckDuckGo と BraveSearch から関連語を検索する。

- DuckDuckGo: APIキー不要 (html.duckduckgo.com のWeb結果 + links.duckduckgo.com の関連クエリ)
- BraveSearch: 公式API (BRAVE_SEARCH_API_KEY / BRAVE_API_KEY が設定されている場合のみ)

両エンジンのWeb結果から頻出語を抽出し、監視キーワード候補(related_terms)として返す。
"""
import html as _html
import re
from collections import Counter
from urllib.parse import parse_qs, unquote, urlsplit

import httpx

from . import config

DDG_HTML_URL = "https://html.duckduckgo.com/html/"
DDG_RELATED_URL = "https://links.duckduckgo.com/ddg/related/"
BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# 関連語抽出用のストップワード (英語 / マレー語 / 日本語の頻出機能語)
_STOPWORDS = {
    # en
    "the", "and", "for", "with", "that", "this", "from", "are", "was", "were",
    "you", "your", "our", "its", "his", "her", "they", "them", "have", "has",
    "had", "will", "would", "can", "could", "should", "not", "but", "all",
    "any", "about", "into", "over", "under", "between", "more", "most",
    "some", "such", "than", "then", "there", "here", "when", "where", "which",
    "who", "whom", "why", "how", "what", "www", "com", "http", "https",
    # ms
    "dan", "yang", "di", "ke", "dari", "untuk", "dengan", "pada", "ini",
    "itu", "atau", "juga", "adalah", "telah", "akan", "dapat", "oleh", "para",
    # ja (ラテン文字表記の機能語)
    "no", "wa", "ni", "ha", "ka", "sa", "ta", "na", "ma", "ra", "ya",
}

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9'\-]{2,}")


def _clean(text: str) -> str:
    return _html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _ddg_result_url(href: str) -> str:
    """DDG のリダイレクトリンク (//duckduckgo.com/l/?uddg=...) を解く."""
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    parts = urlsplit(href)
    if "duckduckgo.com" in parts.netloc and parts.path.startswith("/l/"):
        uddg = parse_qs(parts.query).get("uddg", [""])[0]
        return unquote(uddg)
    return href


def ddg_web_search(query: str, max_results: int = 8) -> list[dict]:
    """DuckDuckGo HTML版のWeb結果を返す [{title,url,snippet}]."""
    try:
        r = httpx.get(DDG_HTML_URL, params={"q": query},
                      headers={"User-Agent": UA}, timeout=15, follow_redirects=True)
        if r.status_code != 200:
            return []
    except Exception as e:
        print(f"[search] ddg web failed: {type(e).__name__}: {e}")
        return []

    results = []
    # result__a (タイトル+URL) と result__snippet をペアで抽出
    blocks = re.findall(
        r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
        r'.*?(?:<a[^>]*class="result__snippet"[^>]*>(.*?)</a>)?',
        r.text, re.S)
    for href, title, snippet in blocks:
        url = _ddg_result_url(href)
        if not url.startswith(("http://", "https://")):
            continue
        results.append({"title": _clean(title), "url": url,
                        "snippet": _clean(snippet)[:300]})
        if len(results) >= max_results:
            break
    return results


def ddg_related_queries(query: str, max_results: int = 10) -> list[str]:
    """DuckDuckGo の関連クエリ (公式JSONエンドポイント、キー不要)."""
    try:
        r = httpx.get(DDG_RELATED_URL, params={"q": query},
                      headers={"User-Agent": UA}, timeout=10, follow_redirects=True)
        if r.status_code != 200:
            return []
        data = r.json()
    except Exception as e:
        print(f"[search] ddg related failed: {type(e).__name__}: {e}")
        return []
    out = []
    for item in (data.get("results") or [])[:max_results]:
        text = str(item.get("text", "")).strip()
        if text and text.lower() != query.lower():
            out.append(text)
    return out


def brave_web_search(query: str, max_results: int = 8) -> tuple[list[dict], bool]:
    """BraveSearch Web結果を返す (results, configured). キー未設定は ([], False)."""
    if not config.BRAVE_API_KEY:
        return [], False
    try:
        r = httpx.get(BRAVE_API_URL, params={"q": query, "count": max_results},
                      headers={"Accept": "application/json",
                               "X-Subscription-Token": config.BRAVE_API_KEY},
                      timeout=15)
        if r.status_code != 200:
            print(f"[search] brave failed: {r.status_code} {r.text[:200]}")
            return [], True
        data = r.json()
    except Exception as e:
        print(f"[search] brave failed: {type(e).__name__}: {e}")
        return [], True
    results = []
    for item in (data.get("web", {}).get("results") or [])[:max_results]:
        url = item.get("url", "")
        if not url.startswith(("http://", "https://")):
            continue
        results.append({"title": _clean(item.get("title", "")), "url": url,
                        "snippet": _clean(item.get("description", ""))[:300]})
    return results, True


def extract_terms(results: list[dict], top_n: int = 12) -> list[str]:
    """Web結果のタイトル/抜粋から頻出語(関連語候補)を抽出する."""
    counter: Counter = Counter()
    for item in results:
        text = f"{item.get('title', '')} {item.get('snippet', '')}".lower()
        tokens = [t for t in _TOKEN_RE.findall(text) if t not in _STOPWORDS]
        counter.update(tokens)
        # 2語フレーズも候補にする(例: "visa application")
        for a, b in zip(tokens, tokens[1:]):
            counter[f"{a} {b}"] += 1
    ranked = [term for term, _ in counter.most_common(top_n * 3)]
    # 単語が既に候補なら、それを含まれる2語フレーズは除外(重複圧縮)
    singles = {t for t in ranked if " " not in t}
    out = []
    for term in ranked:
        if " " in term and any(w in singles for w in term.split()):
            continue
        out.append(term)
        if len(out) >= top_n:
            break
    return out


def search_related(query: str, engines=("ddg", "brave"), max_results: int = 8) -> dict:
    """指定エンジンのWeb結果 + 関連語候補をまとめて返す."""
    query = (query or "").strip()
    if not query:
        return {"ok": False, "error": "クエリが空です"}

    engines_out: dict = {}
    all_results: list[dict] = []

    if "ddg" in engines:
        ddg_res = ddg_web_search(query, max_results)
        related_q = ddg_related_queries(query)
        engines_out["ddg"] = {"ok": True, "results": ddg_res,
                              "related_queries": related_q}
        all_results.extend(ddg_res)

    if "brave" in engines:
        brave_res, configured = brave_web_search(query, max_results)
        engines_out["brave"] = {"ok": True, "configured": configured,
                                "results": brave_res}
        all_results.extend(brave_res)

    # 関連語候補: DDG公式の関連クエリを優先し、不足分は頻出語で補完
    terms: list[str] = []
    if engines_out.get("ddg", {}).get("related_queries"):
        terms.extend(engines_out["ddg"]["related_queries"])
    for term in extract_terms(all_results, top_n=12):
        if term not in terms and len(terms) < 15:
            terms.append(term)

    return {"ok": True, "query": query, "engines": engines_out,
            "related_terms": terms[:15]}
