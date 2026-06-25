"""Corporate update & network configuration — read-only managed-machine view.

Surfaces how this box is governed by IT: Windows Update management (WSUS /
Update for Business deferrals), the WinHTTP and per-user proxy, and the
machine's network identity (AD domain vs workgroup, DNS suffixes).

Everything here is read-only — registry reads and read-only PowerShell/netsh
queries. Nothing is ever written. Missing pieces degrade to None/empty with
sensible standalone-machine defaults; the module never raises.
"""

from .ps import ps_json, run_ps, as_list

# AUOptions decode — the classic gpedit "Configure Automatic Updates" values.
_AU_OPTIONS = {
    2: "Notify before download",
    3: "Auto download, notify install",
    4: "Auto download, schedule install",
    5: "Allow local admin to choose",
}

# Branch readiness level → channel name (Update for Business).
_BRANCH = {
    16: "Semi-Annual Channel (Targeted)",
    32: "Semi-Annual Channel",
}

# Read the WindowsUpdate policy keys (and the \AU subkey) in one shot. We emit
# a flat object of just the values we care about; absent values come back null.
_WU_PS = r"""
$wu = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate'
$au = "$wu\AU"
$p  = Get-ItemProperty -Path $wu -ErrorAction SilentlyContinue
$a  = Get-ItemProperty -Path $au -ErrorAction SilentlyContinue
[pscustomobject]@{
    WUServer            = $p.WUServer
    WUStatusServer      = $p.WUStatusServer
    DeferFeature        = $p.DeferFeatureUpdatesPeriodInDays
    DeferQuality        = $p.DeferQualityUpdatesPeriodInDays
    BranchReadiness     = $p.BranchReadinessLevel
    TargetReleaseVer    = $p.TargetReleaseVersion
    TargetReleaseInfo   = $p.TargetReleaseVersionInfo
    ProductVersion      = $p.ProductVersion
    UseWUServer         = $a.UseWUServer
    NoAutoUpdate        = $a.NoAutoUpdate
    AUOptions           = $a.AUOptions
}
"""

# Per-user proxy from the Internet Settings hive.
_USER_PROXY_PS = r"""
$k = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
$p = Get-ItemProperty -Path $k -ErrorAction SilentlyContinue
[pscustomobject]@{
    ProxyEnable   = $p.ProxyEnable
    ProxyServer   = $p.ProxyServer
    AutoConfigURL = $p.AutoConfigURL
}
"""

# Machine identity — domain membership + DNS suffixes.
_IDENTITY_PS = r"""
$cs = Get-CimInstance Win32_ComputerSystem -ErrorAction SilentlyContinue
$g  = Get-DnsClientGlobalSetting -ErrorAction SilentlyContinue
[pscustomobject]@{
    Domain        = $cs.Domain
    PartOfDomain  = $cs.PartOfDomain
    PrimarySuffix = $env:USERDNSDOMAIN
    SearchList    = @($g.SuffixSearchList)
}
"""


def _as_int(value):
    """Coerce a registry value to int, or None if absent/unparseable."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _update_management():
    """Section 1 — Windows Update governance (WSUS / Update for Business)."""
    info = {
        "mode": "Default (Microsoft Update, unmanaged)",
        "wsus": None,
        "defer_feature": None,
        "defer_quality": None,
        "target_version": None,
        "au_option": None,
    }
    data = ps_json(_WU_PS)
    if not isinstance(data, dict):
        return info

    wsus = (data.get("WUServer") or "").strip() or None
    use_wsus = _as_int(data.get("UseWUServer")) == 1
    info["defer_feature"] = _as_int(data.get("DeferFeature"))
    info["defer_quality"] = _as_int(data.get("DeferQuality"))

    target = (data.get("TargetReleaseVer") or data.get("ProductVersion") or "").strip()
    if data.get("TargetReleaseInfo"):
        # TargetReleaseVersionInfo holds the explicit version string (e.g. "23H2").
        target = str(data.get("TargetReleaseInfo")).strip() or target
    info["target_version"] = target or None

    au = _as_int(data.get("AUOptions"))
    if _as_int(data.get("NoAutoUpdate")) == 1:
        info["au_option"] = "Automatic updates disabled by policy"
    elif au is not None:
        info["au_option"] = _AU_OPTIONS.get(au, f"AUOptions={au}")

    branch = _BRANCH.get(_as_int(data.get("BranchReadiness")))
    has_deferrals = (
        info["defer_feature"] is not None
        or info["defer_quality"] is not None
        or info["target_version"] is not None
        or branch is not None
    )

    if use_wsus or wsus:
        info["wsus"] = wsus
        info["mode"] = f"Managed by WSUS ({wsus or 'server not specified'})"
    elif has_deferrals:
        info["mode"] = "Windows Update for Business (deferrals set)"
    # else: leave the unmanaged default.

    return info


def _winhttp_proxy():
    """Parse `netsh winhttp show proxy` → human-readable system proxy string."""
    out = run_ps("netsh winhttp show proxy", timeout=15) or ""
    proxy = None
    for line in out.splitlines():
        s = line.strip()
        low = s.lower()
        if "direct access" in low:
            return "Direct access (no proxy)"
        if "proxy server(s)" in low:
            _, _, val = s.partition(":")
            proxy = val.strip() or None
    return proxy or "Direct access (no proxy)"


def _proxy():
    """Section 2 — WinHTTP system proxy vs the per-user Internet Settings proxy."""
    info = {
        "winhttp": _winhttp_proxy(),
        "user_enabled": False,
        "user_proxy": None,
        "pac": None,
    }
    data = ps_json(_USER_PROXY_PS)
    if isinstance(data, dict):
        info["user_enabled"] = _as_int(data.get("ProxyEnable")) == 1
        info["user_proxy"] = (data.get("ProxyServer") or "").strip() or None
        info["pac"] = (data.get("AutoConfigURL") or "").strip() or None
    return info


def _network():
    """Section 3 — AD domain / workgroup + DNS suffixes."""
    info = {
        "domain": "WORKGROUP",
        "domain_joined": False,
        "primary_suffix": None,
        "search_list": [],
    }
    data = ps_json(_IDENTITY_PS)
    if isinstance(data, dict):
        domain = (data.get("Domain") or "").strip()
        if domain:
            info["domain"] = domain
        info["domain_joined"] = bool(data.get("PartOfDomain"))
        info["primary_suffix"] = (data.get("PrimarySuffix") or "").strip() or None
        info["search_list"] = [
            s.strip() for s in as_list(data.get("SearchList")) if isinstance(s, str) and s.strip()
        ]
    # On a domain box the primary suffix usually equals the AD domain.
    if not info["primary_suffix"] and info["domain_joined"]:
        info["primary_suffix"] = info["domain"]
    return info


def _summary(update, proxy, network):
    """One-line plain-English roll-up of the three sections."""
    bits = []
    if network["domain_joined"]:
        bits.append(f"Domain-joined ({network['domain']})")
    else:
        bits.append(f"Workgroup ({network['domain']})")
    bits.append(update["mode"])
    if proxy["winhttp"].lower().startswith("direct") and not proxy["user_enabled"] and not proxy["pac"]:
        bits.append("no proxy")
    else:
        bits.append("proxy configured")
    return "; ".join(bits) + "."


def corp_network():
    """Return the corporate update & network configuration (read-only).

    Shape:
        {"ok": True,
         "update":  {"mode", "wsus", "defer_feature", "defer_quality",
                     "target_version", "au_option"},
         "proxy":   {"winhttp", "user_enabled", "user_proxy", "pac"},
         "network": {"domain", "domain_joined", "primary_suffix", "search_list"},
         "summary": "<one-line>"}

    Never raises. A standalone machine degrades to update mode
    "Default (Microsoft Update, unmanaged)", no WSUS, and a WORKGROUP identity.
    """
    update = _update_management()
    proxy = _proxy()
    network = _network()
    return {
        "ok": True,
        "update": update,
        "proxy": proxy,
        "network": network,
        "summary": _summary(update, proxy, network),
    }
