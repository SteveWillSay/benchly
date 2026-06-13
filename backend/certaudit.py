"""Trusted root certificate audit — flag unexpected / interception root CAs.

A rogue or interception root CA in the trusted store lets someone silently MITM
all TLS (adware like Superfish, AV "HTTPS scanning", corporate proxies, dev
tools). The highest-signal heuristic: a self-signed root that is NOT issued by a
well-known public CA and is NOT a known-good Windows root. "Few roots present" is
normal (Windows fetches program roots on demand), so store size is never flagged.
"""

from .ps import ps_json, as_list

# Well-known legitimate public / Microsoft CA org keywords (matched in Subject).
_LEGIT = [
    "digicert", "sectigo", "comodo", "usertrust", "addtrust", "globalsign",
    "godaddy", "starfield", "entrust", "amazon", "google trust", "gts",
    "isrg", "let's encrypt", "microsoft", "baltimore cybertrust", "dst root",
    "quovadis", "thawte", "verisign", "symantec", "geotrust", "rapidssl",
    "certum", "buypass", "identrust", "swisssign", "t-telesec", "deutsche telekom",
    "actalis", "ssl.com", "harica", "twca", "telia", "sonera", "affirmtrust",
    "d-trust", "secom", "certainly", "apple", "wells fargo", "visa", " vTrus",
    "e-szigno", "netlock", "atos", "izenpe", "camerfirma", "wosign",
]

# Known interception / adware / proxy root signatures (matched in Subject).
_BAD = [
    ("Superfish", "superfish", "adware MITM (ships a shared private key)"),
    ("eDellRoot", "edellroot", "Dell interception root (ships a private key)"),
    ("DSDTestProvider", "dsdtestprovider", "Dell test interception root"),
    ("Fiddler", "fiddler", "Fiddler debugging proxy root"),
    ("Charles Proxy", "charles proxy", "Charles debugging proxy root"),
    ("Charles Proxy", "xk72", "Charles debugging proxy root"),
    ("Burp Suite", "portswigger", "Burp Suite intercepting proxy root"),
    ("mkcert", "mkcert", "mkcert local-dev root"),
    ("Zscaler", "zscaler", "Zscaler corporate proxy (TLS interception)"),
    ("Fortinet", "fortinet", "Fortinet/FortiGate proxy (TLS interception)"),
    ("Fortinet", "fortigate", "FortiGate proxy (TLS interception)"),
    ("Palo Alto", "palo alto", "Palo Alto decryption (TLS interception)"),
    ("Avast", "avast", "Avast antivirus HTTPS scanning"),
    ("AVG", "avg technologies", "AVG antivirus HTTPS scanning"),
    ("Kaspersky", "kaspersky", "Kaspersky antivirus HTTPS scanning"),
    ("Bitdefender", "bitdefender", "Bitdefender antivirus HTTPS scanning"),
    ("ESET", "eset", "ESET SSL/TLS protocol filtering"),
    ("Sendori", "sendori", "Sendori adware root"),
    ("Komodia", "komodia", "Komodia interception SDK (Superfish-class)"),
    ("PrivDog", "privdog", "PrivDog adware MITM"),
    ("Wajam", "wajam", "Wajam adware MITM"),
    ("BlueCoat", "blue coat", "Blue Coat/Symantec proxy (TLS interception)"),
]

_STORES = [
    r"Cert:\LocalMachine\Root", r"Cert:\CurrentUser\Root",
    r"Cert:\LocalMachine\CA", r"Cert:\CurrentUser\CA",
]

_PS = r"""
$stores = '__STORES__'
foreach ($s in ($stores -split ';')) {
  Get-ChildItem $s -ErrorAction SilentlyContinue | ForEach-Object {
    $rsa=$null; $ecc=$null
    try { $rsa=[System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPublicKey($_) } catch {}
    try { $ecc=[System.Security.Cryptography.X509Certificates.ECDsaCertificateExtensions]::GetECDsaPublicKey($_) } catch {}
    $ks = if ($rsa) { $rsa.KeySize } elseif ($ecc) { $ecc.KeySize } else { 0 }
    [pscustomobject]@{
      Store=$s; Subject=$_.Subject; Issuer=$_.Issuer; Thumbprint=$_.Thumbprint;
      Friendly=$_.FriendlyName;
      NotAfter=$_.NotAfter.ToString('yyyy-MM-dd');
      Sig=$_.SignatureAlgorithm.FriendlyName; KeySize=$ks
    }
  }
}
"""


def _classify(c):
    subject = (c.get("Subject") or "")
    issuer = (c.get("Issuer") or "")
    friendly = (c.get("Friendly") or "")
    hay = (subject + " " + friendly).lower()
    self_signed = subject.strip().lower() == issuer.strip().lower()
    is_root = "root" in (c.get("Store") or "").lower()
    sig = (c.get("Sig") or "").lower()
    ks = c.get("KeySize") or 0

    reasons = []
    score = 0

    for name, needle, desc in _BAD:
        if needle in hay:
            return ("alert", [f"Known interception/adware root: {name} — {desc}."], name)

    legit = any(k in hay for k in _LEGIT)
    if self_signed and is_root and not legit:
        score += 3
        reasons.append("Self-signed root not issued by a recognised public CA.")
    if "sha1" in sig or "md5" in sig:
        score += 1
        reasons.append(f"Weak signature algorithm ({c.get('Sig')}).")
    if 0 < ks < 2048:
        score += 1
        reasons.append(f"Weak key size ({ks}-bit).")
    if "currentuser" in (c.get("Store") or "").lower() and self_signed and not legit:
        score += 1
        reasons.append("Installed in the per-user store (no admin needed to add).")

    if score >= 3:
        return ("review", reasons, None)
    if legit:
        return ("ok", [], None)
    return ("ok", reasons, None)


def audit_certs():
    cmd = _PS.replace("__STORES__", ";".join(_STORES))
    rows = as_list(ps_json(cmd, timeout=45, depth=3))
    certs = []
    alert = review = 0
    for c in rows:
        level, reasons, label = _classify(c)
        if level == "alert":
            alert += 1
        elif level == "review":
            review += 1
        certs.append({
            "subject": c.get("Subject") or "",
            "issuer": c.get("Issuer") or "",
            "friendly": c.get("Friendly") or "",
            "thumbprint": c.get("Thumbprint") or "",
            "store": (c.get("Store") or "").replace("Cert:\\", ""),
            "not_after": c.get("NotAfter"),
            "sig": c.get("Sig"),
            "key_size": c.get("KeySize") or 0,
            "level": level,
            "reasons": reasons,
            "label": label,
        })
    # Most concerning first
    order = {"alert": 0, "review": 1, "ok": 2}
    certs.sort(key=lambda x: (order[x["level"]], x["subject"].lower()))
    return {"ok": True, "certs": certs, "total": len(certs),
            "alert": alert, "review": review}
