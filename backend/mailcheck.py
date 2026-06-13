"""Email header analyzer — phishing triage for pasted raw headers.

Pure local parsing (no network). Reconstructs the Received hop path, finds the
originating IP, reads SPF/DKIM/DMARC from Authentication-Results, and flags the
classic spoofing tells (Return-Path / Reply-To / display-name mismatches).
"""

import ipaddress
import re
from email import message_from_string
from email.policy import default as default_policy
from email.utils import parseaddr, parsedate_to_datetime

_RE_RECV_IP = re.compile(
    r"from\s+\S+.*?[\[\(]\s*(?:IPv6:)?(?P<ip>(?:\d{1,3}\.){3}\d{1,3}|[0-9a-fA-F:]{4,})\s*[\]\)]",
    re.IGNORECASE | re.DOTALL)
_RE_ANY_IPV4 = re.compile(r"\[(?P<ip>(?:\d{1,3}\.){3}\d{1,3})\]")
_RE_HELO = re.compile(r"from\s+(?P<helo>[^\s(]+)", re.IGNORECASE)
_RE_SPF = re.compile(r"\bspf=(?P<r>pass|fail|softfail|neutral|none|temperror|permerror|policy)\b", re.I)
_RE_DKIM = re.compile(r"\bdkim=(?P<r>pass|fail|neutral|none|temperror|permerror|policy)\b", re.I)
_RE_DMARC = re.compile(r"\bdmarc=(?P<r>pass|fail|none|temperror|permerror)\b", re.I)
_RE_DMARC_P = re.compile(r"dmarc=\w+\s*\([^)]*\bp=(?P<p>none|quarantine|reject)\b", re.I)

_BRANDS = ("paypal", "microsoft", "apple", "amazon", "netflix", "google", "facebook",
           "instagram", "hmrc", "irs", "dpd", "royal mail", "fedex", "ups", "dhl",
           "santander", "barclays", "hsbc", "lloyds", "nationwide", "natwest",
           "coinbase", "binance", "outlook", "office365", "bank")


def _domain(addr):
    addr = (addr or "").strip().strip("<>")
    return addr.rsplit("@", 1)[-1].lower() if "@" in addr else ""


def _reg_domain(d):
    """Naive registrable domain (last two labels) — good enough for comparison."""
    parts = (d or "").split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else d


def _auth_results(msg):
    spf = dkim = dmarc = dmarc_p = None
    for hdr in msg.get_all("Authentication-Results", []):
        h = " ".join(str(hdr).split())
        if spf is None and (m := _RE_SPF.search(h)):
            spf = m.group("r").lower()
        if dkim is None and (m := _RE_DKIM.search(h)):
            dkim = m.group("r").lower()
        if dmarc is None and (m := _RE_DMARC.search(h)):
            dmarc = m.group("r").lower()
        if dmarc_p is None and (m := _RE_DMARC_P.search(h)):
            dmarc_p = m.group("p").lower()
    # Fall back to Received-SPF
    if spf is None:
        for hdr in msg.get_all("Received-SPF", []):
            m = re.match(r"\s*(pass|fail|softfail|neutral|none|temperror|permerror)", str(hdr), re.I)
            if m:
                spf = m.group(1).lower()
                break
    return {"spf": spf, "dkim": dkim, "dmarc": dmarc, "dmarc_policy": dmarc_p}


def _hops(msg):
    hops = []
    received = msg.get_all("Received", [])
    for raw in received:
        val = " ".join(str(raw).split())
        m = _RE_RECV_IP.search(val) or _RE_ANY_IPV4.search(val)
        ip = m.group("ip") if m else None
        helo = (_RE_HELO.search(val).group("helo") if _RE_HELO.search(val) else None)
        ts = None
        if ";" in val:
            try:
                ts = parsedate_to_datetime(val.rsplit(";", 1)[-1].strip())
                ts = ts.strftime("%Y-%m-%d %H:%M") if ts else None
            except Exception:
                ts = None
        hops.append({"ip": ip, "helo": helo, "time": ts, "raw": val[:300]})
    return hops


def _originating_ip(hops):
    for hop in reversed(hops):  # bottom = origin
        ip = hop.get("ip")
        if not ip:
            continue
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if addr.is_global:
            return ip
    # else first parseable IP at all
    for hop in reversed(hops):
        if hop.get("ip"):
            return hop["ip"]
    return None


def analyze_headers(raw):
    raw = (raw or "").strip()
    if not raw or ":" not in raw:
        return {"ok": False, "error": "Paste the full raw email headers."}
    try:
        msg = message_from_string(raw + "\n\n", policy=default_policy)
    except Exception as e:
        return {"ok": False, "error": f"Could not parse headers: {e}"}

    from_name, from_addr = parseaddr(msg.get("From", ""))
    _, rp_addr = parseaddr(msg.get("Return-Path", ""))
    _, reply_addr = parseaddr(msg.get("Reply-To", ""))
    from_dom = _domain(from_addr)
    rp_dom = _domain(rp_addr)
    reply_dom = _domain(reply_addr)
    msgid = msg.get("Message-ID", "")
    msgid_dom = ""
    if (m := re.search(r"@([^>\s]+)", msgid or "")):
        msgid_dom = m.group(1).lower()

    auth = _auth_results(msg)
    hops = _hops(msg)
    origin = _originating_ip(hops)

    flags = []

    def flag(level, text):
        flags.append({"level": level, "text": text})

    if from_dom and rp_dom and _reg_domain(rp_dom) != _reg_domain(from_dom):
        flag("warn", f"Return-Path domain ({rp_dom}) differs from From domain ({from_dom}) — a common spoofing tell.")
    if from_dom and reply_dom and _reg_domain(reply_dom) != _reg_domain(from_dom):
        flag("warn", f"Reply-To domain ({reply_dom}) differs from From domain ({from_dom}) — replies would go elsewhere.")
    if auth["spf"] in ("fail", "softfail"):
        flag("warn", f"SPF {auth['spf']} — the sending server isn't authorised for this domain.")
    elif auth["spf"] == "pass":
        flag("good", "SPF passed.")
    if auth["dkim"] == "fail":
        flag("warn", "DKIM failed — the message signature didn't validate.")
    elif auth["dkim"] == "pass":
        flag("good", "DKIM passed.")
    if auth["dmarc"] == "fail":
        flag("warn", "DMARC failed — the message isn't aligned with the From domain.")
    elif auth["dmarc"] == "pass":
        flag("good", "DMARC passed.")
    elif auth["dmarc_policy"] == "none":
        flag("info", "DMARC policy is p=none — the domain owner isn't enforcing anti-spoofing.")

    if from_name and from_addr:
        nm = from_name.lower()
        for b in _BRANDS:
            if b in nm and b not in from_dom:
                flag("warn", f"Display name mentions “{from_name}” but the address domain is {from_dom or '(none)'} — possible brand impersonation.")
                break
    if msgid_dom and from_dom and _reg_domain(msgid_dom) != _reg_domain(from_dom):
        flag("info", f"Message-ID domain ({msgid_dom}) differs from the From domain.")
    if not hops:
        flag("info", "No Received headers found — can't trace the delivery path.")

    if not any(f["level"] == "warn" for f in flags):
        flag("good", "No major spoofing signals detected in these headers.")

    return {
        "ok": True,
        "from_name": from_name,
        "from_addr": from_addr,
        "return_path": rp_addr,
        "reply_to": reply_addr,
        "subject": str(msg.get("Subject", "")),
        "message_id": msgid,
        "auth": auth,
        "origin_ip": origin,
        "hops": hops,
        "x_mailer": str(msg.get("X-Mailer", "") or msg.get("User-Agent", "")),
        "flags": flags,
    }
