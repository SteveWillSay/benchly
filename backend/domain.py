"""Domain / website intelligence — a trust check for a hostname or URL.

Combines several public sources into one verdict so a technician can decide
whether to trust a domain:

  * RDAP (the modern, JSON successor to port-43 WHOIS) — registrar, registration
    / expiry dates, domain age, status flags, registrant org/country.
  * DNS records — A/AAAA/NS/MX/TXT, plus SPF and DMARC presence.
  * IP intelligence — for the resolved address: reverse DNS and the owning
    network/org/country (via RDAP for IP, no API key needed).
  * TLS certificate — issuer, validity window, SAN list, hostname match.
  * VirusTotal domain reputation — only if an API key is configured.

What leaves the machine: the domain name (to rdap.org and, if enabled, to
VirusTotal) and a TLS handshake to the host. No browsing history, no files.
"""

import datetime
import json
import re
import socket
import ssl
import urllib.error
import urllib.request

from . import settings
from .ps import ps_json, run_ps, as_list

_UA = "Benchly"
_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)([a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


# --------------------------------------------------------------------------- #
# input handling
# --------------------------------------------------------------------------- #
def _extract_host(query: str):
    q = (query or "").strip()
    q = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", "", q)   # drop scheme
    q = q.split("/")[0].split("?")[0].split("#")[0]       # drop path/query/frag
    q = q.split("@")[-1]                                   # drop userinfo
    q = q.split(":")[0]                                    # drop :port
    return q.strip().strip(".").lower()


def _apex(host: str):
    """Best-effort registrable domain (last two labels) for RDAP fallback."""
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) > 2 else host


# --------------------------------------------------------------------------- #
# RDAP (WHOIS successor)
# --------------------------------------------------------------------------- #
def _http_json(url: str, timeout: int = 20):
    req = urllib.request.Request(url, headers={"User-Agent": _UA,
                                               "Accept": "application/rdap+json, application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def _vcard_get(entity: dict, field: str):
    """Pull a field (fn, org, email, adr) out of an RDAP entity's vcardArray."""
    try:
        for item in entity.get("vcardArray", [None, []])[1]:
            if item and item[0] == field:
                val = item[3]
                if isinstance(val, list):
                    val = ", ".join(str(x) for x in val if x)
                return str(val).strip() or None
    except Exception:
        pass
    return None


def _find_entity(entities, role):
    for e in entities or []:
        if role in (e.get("roles") or []):
            return e
    return None


def _rdap_domain(host: str):
    data = None
    for target in (host, _apex(host)):
        try:
            data = _http_json(f"https://rdap.org/domain/{target}", timeout=18)
            break
        except urllib.error.HTTPError as e:
            if e.code in (404, 400) and target != _apex(host):
                continue
            return {"error": f"RDAP HTTP {e.code}"} if e.code != 404 else {"error": "Not found in any registry (RDAP 404)."}
        except Exception as e:
            return {"error": f"RDAP lookup failed: {e}"}
    if not data:
        return {"error": "RDAP returned no data."}

    events = {ev.get("eventAction"): ev.get("eventDate") for ev in data.get("events", []) if ev.get("eventAction")}
    entities = data.get("entities", [])
    registrar_e = _find_entity(entities, "registrar")
    registrant_e = _find_entity(entities, "registrant")

    abuse_email = None
    if registrar_e:
        abuse_e = _find_entity(registrar_e.get("entities", []), "abuse")
        if abuse_e:
            abuse_email = _vcard_get(abuse_e, "email")

    created = events.get("registration")
    age_days = None
    if created:
        try:
            dt = datetime.datetime.fromisoformat(created.replace("Z", "+00:00"))
            age_days = (datetime.datetime.now(datetime.timezone.utc) - dt).days
        except Exception:
            pass

    statuses = [s for s in (data.get("status") or [])]
    nameservers = [ns.get("ldhName", "").lower() for ns in data.get("nameservers", []) if ns.get("ldhName")]

    return {
        "registrar": (_vcard_get(registrar_e, "fn") if registrar_e else None)
                     or (registrar_e.get("handle") if registrar_e else None),
        "created": created,
        "updated": events.get("last changed"),
        "expires": events.get("expiration"),
        "age_days": age_days,
        "statuses": statuses,
        "nameservers": nameservers,
        "registrant_org": _vcard_get(registrant_e, "org") or _vcard_get(registrant_e, "fn") if registrant_e else None,
        "abuse_email": abuse_email,
    }


def _rdap_ip(ip: str):
    try:
        data = _http_json(f"https://rdap.org/ip/{ip}", timeout=12)
    except Exception:
        return None
    country = data.get("country")
    org = None
    for e in data.get("entities", []):
        roles = e.get("roles") or []
        if "registrant" in roles or "administrative" in roles:
            org = _vcard_get(e, "fn") or _vcard_get(e, "org")
            if org:
                break
    asn = None
    # Some RDAP IP responses carry the network name; surface it as a fallback.
    net_name = data.get("name")
    return {"network": net_name, "org": org or net_name, "country": country, "asn": asn}


# --------------------------------------------------------------------------- #
# DNS
# --------------------------------------------------------------------------- #
def _txt_of(row):
    strings = row.get("Strings")
    return " ".join(strings) if isinstance(strings, list) else str(strings or "")


def _dns_records(host: str):
    """All record types in a single PowerShell invocation (host is regex-validated)."""
    out = {"a": [], "aaaa": [], "ns": [], "mx": [], "txt": [], "spf": False, "dmarc": False}
    cmd = (
        f"$d='{host}'; $m='_dmarc.{host}'; $r=@(); "
        "foreach($t in 'A','AAAA','NS','MX','TXT'){ "
        "$r += Resolve-DnsName -Name $d -Type $t -DnsOnly -ErrorAction SilentlyContinue }; "
        "$r += Resolve-DnsName -Name $m -Type TXT -DnsOnly -ErrorAction SilentlyContinue; "
        "$r | Select-Object Name,Type,IPAddress,NameHost,NameExchange,Preference,Strings"
    )
    for r in as_list(ps_json(cmd, timeout=25)):
        t = r.get("Type")
        if t == 1 and r.get("IPAddress"):
            out["a"].append(r["IPAddress"])
        elif t == 28 and r.get("IPAddress"):
            out["aaaa"].append(r["IPAddress"])
        elif t == 2 and r.get("NameHost"):
            out["ns"].append(r["NameHost"].lower())
        elif t == 15 and r.get("NameExchange"):
            out["mx"].append({"host": r["NameExchange"].lower(), "pref": r.get("Preference")})
        elif t == 16:
            text = _txt_of(r)
            is_dmarc = str(r.get("Name") or "").lower().startswith("_dmarc.")
            if is_dmarc:
                if text.lower().startswith("v=dmarc1"):
                    out["dmarc"] = True
            elif text:
                out["txt"].append(text)
                if text.lower().startswith("v=spf1"):
                    out["spf"] = True
    out["mx"].sort(key=lambda m: (m.get("pref") if m.get("pref") is not None else 999))
    return out


def _reverse_dns(ip: str):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# TLS certificate
# --------------------------------------------------------------------------- #
def _name_from_rdn(rdn_seq):
    out = {}
    for rdn in rdn_seq or ():
        for key, val in rdn:
            out[key] = val
    return out


def _tls_info(host: str):
    cert, verified, verify_error = None, True, None
    try:
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        with socket.create_connection((host, 443), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ss:
                cert = ss.getpeercert()
    except ssl.SSLCertVerificationError as e:
        verified, verify_error = False, getattr(e, "verify_message", None) or str(e)
    except (socket.timeout, ConnectionRefusedError, socket.gaierror, OSError) as e:
        return {"ok": False, "error": str(e)}

    if cert is None:  # fetch unverified so we can still show + flag the details
        try:
            uctx = ssl._create_unverified_context()
            uctx.minimum_version = ssl.TLSVersion.TLSv1_2
            with socket.create_connection((host, 443), timeout=8) as sock:
                with uctx.wrap_socket(sock, server_hostname=host) as ss:
                    cert = ss.getpeercert()
        except Exception as e:
            return {"ok": False, "error": str(e), "verified": False, "verify_error": verify_error}

    if not cert:
        return {"ok": False, "error": "No certificate presented.", "verified": verified}

    issuer = _name_from_rdn(cert.get("issuer"))
    subject = _name_from_rdn(cert.get("subject"))
    sans = [v for (t, v) in cert.get("subjectAltName", ()) if t == "DNS"]

    days_left = None
    not_after = cert.get("notAfter")
    if not_after:
        try:
            secs = ssl.cert_time_to_seconds(not_after)
            days_left = int((datetime.datetime.fromtimestamp(secs, datetime.timezone.utc)
                             - datetime.datetime.now(datetime.timezone.utc)).total_seconds() // 86400)
        except Exception:
            pass

    return {
        "ok": True,
        "verified": verified,
        "verify_error": verify_error,
        "issuer": issuer.get("organizationName") or issuer.get("commonName"),
        "subject_cn": subject.get("commonName"),
        "not_before": cert.get("notBefore"),
        "not_after": not_after,
        "days_left": days_left,
        "sans": sans[:12],
        "san_count": len(sans),
    }


# --------------------------------------------------------------------------- #
# VirusTotal domain reputation (optional)
# --------------------------------------------------------------------------- #
def _vt_domain(host: str):
    api_key = (settings.get("vt_api_key") or "").strip()
    if not api_key:
        return None
    req = urllib.request.Request(
        f"https://www.virustotal.com/api/v3/domains/{host}",
        headers={"x-apikey": api_key, "User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"found": False}
        if e.code == 401:
            return {"error": "VirusTotal rejected the API key (401)."}
        if e.code == 429:
            return {"error": "VirusTotal rate limit reached (free tier: 4/min)."}
        return {"error": f"VirusTotal HTTP {e.code}."}
    except Exception as e:
        return {"error": f"VirusTotal lookup failed: {e}"}

    attr = (data.get("data") or {}).get("attributes") or {}
    stats = attr.get("last_analysis_stats") or {}
    return {
        "found": True,
        "malicious": stats.get("malicious", 0),
        "suspicious": stats.get("suspicious", 0),
        "harmless": stats.get("harmless", 0),
        "reputation": attr.get("reputation"),
        "link": f"https://www.virustotal.com/gui/domain/{host}",
    }


# --------------------------------------------------------------------------- #
# trust synthesis
# --------------------------------------------------------------------------- #
_BAD_STATUS = ("clienthold", "serverhold", "pendingdelete", "redemptionperiod")


def _flags(rdap, dns, tls, vt):
    flags = []
    age = (rdap or {}).get("age_days")
    if age is not None:
        if age < 30:
            flags.append({"level": "warn", "text": f"Registered only {age} day(s) ago — very young domains are common in phishing and scams."})
        elif age < 90:
            flags.append({"level": "warn", "text": f"Registered {age} days ago — still relatively new; treat with some caution."})
        elif age >= 730:
            flags.append({"level": "good", "text": f"Registered {age // 365} year(s) ago — an established domain."})
    for s in (rdap or {}).get("statuses", []):
        if any(b in s.lower().replace(" ", "") for b in _BAD_STATUS):
            flags.append({"level": "warn", "text": f"Registry status “{s}” — the domain may be held, expiring or in dispute."})
    if tls:
        if tls.get("ok") and tls.get("verified"):
            dl = tls.get("days_left")
            if dl is not None and dl < 0:
                flags.append({"level": "warn", "text": "TLS certificate has expired."})
            elif dl is not None and dl < 14:
                flags.append({"level": "warn", "text": f"TLS certificate expires in {dl} day(s)."})
            else:
                flags.append({"level": "good", "text": "Valid TLS certificate that matches the hostname."})
        elif tls.get("ok") and not tls.get("verified"):
            flags.append({"level": "warn", "text": "TLS certificate did not validate (name mismatch, self-signed or untrusted issuer)."})
        elif not tls.get("ok"):
            flags.append({"level": "warn", "text": "No HTTPS / TLS on port 443 — the site is not reachable over a secure connection."})
    if dns and not dns.get("spf"):
        flags.append({"level": "info", "text": "No SPF record — mail claiming to be from this domain is easier to spoof."})
    if dns and not dns.get("dmarc"):
        flags.append({"level": "info", "text": "No DMARC record — no published policy against email spoofing."})
    if vt and vt.get("found"):
        mal, susp = vt.get("malicious", 0), vt.get("suspicious", 0)
        if mal:
            flags.append({"level": "warn", "text": f"Flagged as malicious by {mal} security vendor(s) on VirusTotal."})
        elif susp:
            flags.append({"level": "warn", "text": f"Flagged as suspicious by {susp} vendor(s) on VirusTotal."})
        else:
            flags.append({"level": "good", "text": "No security vendor flags this domain on VirusTotal."})
    return flags


def lookup_domain(query: str):
    host = _extract_host(query)
    if not host or not _DOMAIN_RE.match(host):
        return {"ok": False, "error": "Enter a domain or website address, e.g. example.com"}

    rdap = _rdap_domain(host)
    rdap_err = rdap.pop("error", None) if isinstance(rdap, dict) else None
    if rdap_err:
        rdap = None

    dns = _dns_records(host)

    ip_info = None
    first_ip = dns["a"][0] if dns["a"] else (dns["aaaa"][0] if dns["aaaa"] else None)
    if first_ip:
        ip_info = _rdap_ip(first_ip) or {}
        ip_info["addr"] = first_ip
        ip_info["ptr"] = _reverse_dns(first_ip)

    tls = _tls_info(host)
    vt = _vt_domain(host)

    return {
        "ok": True,
        "domain": host,
        "rdap": rdap,
        "rdap_error": rdap_err,
        "dns": dns,
        "ip": ip_info,
        "tls": tls,
        "vt": vt,
        "flags": _flags(rdap, dns, tls, vt),
    }
