"""URL / redirect unmasker — expand short links and reveal the final destination.

Follows the HTTP redirect chain manually (capturing every hop) without executing
anything. Detects meta-refresh and JavaScript redirects (which it cannot follow),
recognises URL shorteners, and flags chained shorteners. Only http/https schemes
are ever requested — file:/data:/javascript: targets are refused.
"""

import re
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlsplit

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Benchly/1.8 URL-Unmasker"
_REDIRECT_CODES = {301, 302, 303, 307, 308}

_RE_META = re.compile(
    r'<meta[^>]+http-equiv=["\']?refresh["\']?[^>]+content=["\'][^"\']*url=(?P<u>[^"\'>\s]+)', re.I)
_RE_JS = re.compile(r"(?:window\.location|location\.href|location\.replace)\s*[=(]", re.I)

SHORTENERS = {
    "bit.ly", "t.co", "tinyurl.com", "goo.gl", "ow.ly", "buff.ly", "is.gd",
    "rebrand.ly", "cutt.ly", "rb.gy", "shorturl.at", "t.ly", "tiny.cc", "bit.do",
    "soo.gd", "s.id", "lnkd.in", "db.tt", "qr.ae", "adf.ly", "bl.ink", "snip.ly",
    "mcaf.ee", "su.pr", "clck.ru", "v.gd", "x.co", "po.st", "trib.al", "linktr.ee",
    "flip.it", "shor.by",
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # don't auto-follow; hand the 3xx back to us


_opener = urllib.request.build_opener(_NoRedirect)


def _host(url):
    return (urlsplit(url).hostname or "").lower().lstrip("www.")


def unmask_url(url, max_hops=12, timeout=10):
    url = (url or "").strip()
    if not re.match(r"^https?://", url, re.I):
        if "." in url and " " not in url:
            url = "http://" + url            # be forgiving of a bare domain
        else:
            return {"ok": False, "error": "Enter an http(s) URL."}

    hops = []
    seen = set()
    current = url
    final = None
    note = None

    for _ in range(max_hops + 1):
        if current in seen:
            hops.append({"url": current, "note": "redirect loop detected"})
            note = "loop"
            break
        seen.add(current)
        scheme = urlsplit(current).scheme.lower()
        if scheme not in ("http", "https"):
            hops.append({"url": current, "note": f"refused non-web scheme ({scheme}:)"})
            note = "blocked-scheme"
            break

        req = urllib.request.Request(current, method="GET",
                                     headers={"User-Agent": _UA, "Accept": "*/*"})
        try:
            resp = _opener.open(req, timeout=timeout)
            status = resp.getcode()
            location = resp.headers.get("Location")
            body = b"" if status in _REDIRECT_CODES else resp.read(4096)
            resp.close()
        except urllib.error.HTTPError as e:
            status, location, body = e.code, e.headers.get("Location"), b""
        except Exception as e:
            hops.append({"url": current, "error": str(e)[:160]})
            note = "error"
            break

        hop = {"url": current, "status": status,
               "shortener": _host(current) in SHORTENERS}
        if location and status in _REDIRECT_CODES:
            nxt = urljoin(current, location)
            hop["redirects_to"] = nxt
            hops.append(hop)
            current = nxt
            continue

        # terminal hop — inspect a little body for client-side redirects
        text = body.decode("utf-8", "replace") if body else ""
        if (m := _RE_META.search(text)):
            hop["meta_refresh"] = urljoin(current, m.group("u"))
            note = "meta-refresh (not followed)"
        elif _RE_JS.search(text):
            hop["js_redirect"] = True
            note = "JavaScript redirect (needs a browser to resolve)"
        hops.append(hop)
        final = current
        break
    else:
        note = "too many redirects"

    shortener_hops = sum(1 for h in hops if h.get("shortener"))
    flags = []
    if shortener_hops >= 2:
        flags.append({"level": "warn", "text": f"Chained through {shortener_hops} URL shorteners — a common way to hide a destination."})
    elif shortener_hops == 1:
        flags.append({"level": "info", "text": "Starts with a URL shortener."})
    if final and _host(final) != _host(url):
        flags.append({"level": "info", "text": f"Final destination: {_host(final)}"})
    if any(h.get("js_redirect") or h.get("meta_refresh") for h in hops):
        flags.append({"level": "warn", "text": "Destination is hidden behind a client-side redirect — open in a sandbox to be sure."})
    if final and re.match(r"^\d{1,3}(\.\d{1,3}){3}$", _host(final) or ""):
        flags.append({"level": "warn", "text": "Final host is a raw IP address — unusual for a legitimate site."})
    if final and (_host(final) or "").startswith("xn--"):
        flags.append({"level": "warn", "text": "Final host uses punycode (xn--) — possible look-alike domain."})

    return {
        "ok": True,
        "start": url,
        "final": final,
        "final_host": _host(final) if final else None,
        "hop_count": len(hops),
        "hops": hops,
        "note": note,
        "flags": flags,
    }
