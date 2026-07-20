"""WebBrowser: a minimal web-browsing ability for the DreamEngine.

Uses ``requests`` and honours the environment proxy (HTTPS_PROXY), so it works inside the
sandbox. Everything is best-effort and never raises into the engine — a failed fetch returns
an ``ok: False`` dict. This gives the autonomous loop real outside-context access (fetch a
reference page, look something up) without any heavyweight dependency.
"""
from __future__ import annotations

import html
import re
from urllib.parse import quote_plus

try:
    import requests
    _HAVE_REQUESTS = True
except Exception:  # pragma: no cover
    _HAVE_REQUESTS = False

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_UA = "nexus-ccs-dreamer/1.0 (+observability research)"


def _strip_html(s: str) -> str:
    return _WS.sub(" ", html.unescape(_TAG.sub(" ", s))).strip()


class WebBrowser:
    def __init__(self, enabled: bool = True, timeout: float = 12.0):
        self.enabled = enabled and _HAVE_REQUESTS
        self.timeout = timeout

    def online(self, probe: str = "https://duckduckgo.com") -> bool:
        return bool(self.fetch(probe, max_chars=64).get("ok"))

    def fetch(self, url: str, max_chars: int = 2000) -> dict:
        """Fetch a URL and return {ok, status, url, text} (text is stripped + truncated)."""
        if not self.enabled:
            return {"ok": False, "url": url, "error": "web disabled or requests missing"}
        try:
            r = requests.get(url, timeout=self.timeout, headers={"User-Agent": _UA})
            text = _strip_html(r.text) if "text" in r.headers.get("content-type", "") or r.text else ""
            return {"ok": r.ok, "status": r.status_code, "url": url, "text": text[:max_chars]}
        except Exception as e:
            return {"ok": False, "url": url, "error": f"{type(e).__name__}: {e}"}

    def wiki(self, topic: str) -> dict:
        """Fetch a one-paragraph summary of ``topic`` from the Wikipedia REST API (reliable)."""
        if not self.enabled:
            return {"ok": False, "topic": topic, "error": "web disabled"}
        slug = quote_plus(topic.replace(" ", "_"))
        try:
            r = requests.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}",
                             timeout=self.timeout, headers={"User-Agent": _UA})
            data = r.json() if r.ok else {}
            extract = _WS.sub(" ", data.get("extract", "")).strip()
            return {"ok": bool(extract), "topic": topic, "title": data.get("title"),
                    "extract": extract, "status": r.status_code}
        except Exception as e:
            return {"ok": False, "topic": topic, "error": f"{type(e).__name__}: {e}"}

    def search(self, query: str, max_results: int = 3) -> dict:
        """Best-effort web search via the DuckDuckGo HTML endpoint."""
        if not self.enabled:
            return {"ok": False, "query": query, "results": [], "error": "web disabled"}
        url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
        try:
            r = requests.get(url, timeout=self.timeout, headers={"User-Agent": _UA})
            titles = [_strip_html(m) for m in
                      re.findall(r'result__a[^>]*>(.*?)</a>', r.text, re.S)][:max_results]
            return {"ok": r.ok and bool(titles), "query": query,
                    "results": titles, "status": r.status_code}
        except Exception as e:
            return {"ok": False, "query": query, "results": [], "error": f"{type(e).__name__}: {e}"}
