"""Identity & domain join — 'what kind of machine is this, really?'

Is it Entra (Azure AD) joined, hybrid, on a traditional AD domain, or just a
workgroup PC? This reads `dsregcmd /status` plus the computer-system info and the
signed-in user, and turns it into a one-line verdict — the fast answer to 'why won't
Teams/Outlook/SSO sign in here?'. Read-only.
"""

from .ps import ps_json, run_ps

# dsregcmd fields worth surfacing, mapped to friendly labels.
_FIELDS = {
    "AzureAdJoined": "Entra (Azure AD) joined",
    "EnterpriseJoined": "Enterprise (on-prem DRS) joined",
    "DomainJoined": "AD domain joined",
    "WorkplaceJoined": "Workplace (Entra registered) joined",
    "TenantName": "Tenant",
    "TenantId": "Tenant ID",
    "DeviceId": "Device ID",
    "AzureAdPrt": "Entra SSO token (PRT) present",
    "DomainName": "Domain",
}
_ROLE = {0: "Standalone workstation", 1: "Domain-member workstation",
         2: "Standalone server", 3: "Domain-member server",
         4: "Backup domain controller", 5: "Primary domain controller"}


def _parse_dsreg(text):
    """dsregcmd /status is a block of 'Key : Value' lines — pull the ones we care about."""
    out = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k, v = k.strip(), v.strip()
        if k in _FIELDS and v:
            out[k] = v
    return out


def _yes(v):
    return str(v).upper() == "YES"


def identity_status():
    cim = ps_json(
        "$c = Get-CimInstance Win32_ComputerSystem; [pscustomobject]@{ "
        "Domain=$c.Domain; PartOfDomain=$c.PartOfDomain; Role=[int]$c.DomainRole; "
        "Workgroup=$c.Workgroup; User=$c.UserName; "
        "Upn=(whoami /upn 2>$null) }", timeout=25) or {}

    ds = _parse_dsreg(run_ps("dsregcmd /status", timeout=25) or "")

    aad = _yes(ds.get("AzureAdJoined"))
    domain = _yes(ds.get("DomainJoined")) or cim.get("PartOfDomain") is True
    workplace = _yes(ds.get("WorkplaceJoined"))

    if aad and domain:
        verdict, level = "Hybrid-joined (AD + Entra)", "info"
    elif aad:
        verdict, level = "Entra (Azure AD) joined", "info"
    elif domain:
        verdict, level = "AD domain joined", "info"
    elif workplace:
        verdict, level = "Entra registered (workplace-joined)", "info"
    else:
        verdict, level = "Workgroup — not managed", "good"

    # Friendly key/value rows from whatever dsregcmd gave us.
    rows = []
    for key, label in _FIELDS.items():
        if key in ds:
            val = ds[key]
            if key in ("AzureAdJoined", "EnterpriseJoined", "DomainJoined",
                       "WorkplaceJoined", "AzureAdPrt"):
                val = "Yes" if _yes(val) else "No"
            rows.append({"label": label, "value": val})

    managed = aad or domain or _yes(ds.get("EnterpriseJoined"))
    return {
        "ok": True,
        "verdict": verdict, "level": level, "managed": managed,
        "domain": cim.get("Domain") if cim.get("PartOfDomain") else None,
        "workgroup": cim.get("Workgroup"),
        "role": _ROLE.get(cim.get("Role")),
        "user": cim.get("User"),
        "upn": (cim.get("Upn") or "").strip() or None,
        "rows": rows,
        "dsreg_available": bool(ds),
    }
