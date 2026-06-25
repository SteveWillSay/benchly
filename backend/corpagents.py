"""Corporate management & security agents — 'how is this PC administered?'

Surfaces the management-plane and security tooling a managed PC carries:
ConfigMgr/SCCM, Intune, MDM enrollment, Defender for Endpoint, third-party
EDR/AV, VPN/ZTNA clients and backup agents. Each known agent is detected by
its Windows service (matched case-insensitively against one Win32_Service
snapshot) and/or a registry/WMI read, then reported with running state and,
where cheap, a version. Only agents that are actually present are listed —
absent products are not enumerated — but the one-line summary always names the
management plane. Read-only; never raises.
"""

import winreg

from .ps import ps_json, as_list

# Known agents keyed by category. Each entry: friendly name, the set of service
# names that indicate presence (lowercased at match time), and a short note.
# (name, [service names], detail-when-present)
_MANAGEMENT = [
    ("ConfigMgr / SCCM client", ["ccmexec"], "SMS Agent Host"),
    ("Microsoft Intune Management Extension",
     ["microsoft intune management extension"], "Intune Win32 app / script agent"),
]

_SECURITY = [
    ("Microsoft Defender for Endpoint (Sense)", ["sense"], "MDE EDR sensor"),
    ("CrowdStrike Falcon", ["csfalconservice"], "CrowdStrike EDR"),
    ("SentinelOne", ["sentinelagent", "sentinelhelperservice", "sentinelstaticengine"],
     "SentinelOne EDR"),
    ("VMware Carbon Black", ["cbdefense", "carbonblack", "cbdefensewsc"],
     "Carbon Black EDR"),
    ("Sophos", ["sophos endpoint defense service", "savservice",
                "sophos system protection service"], "Sophos endpoint"),
    ("Cylance", ["cylancesvc"], "Cylance PROTECT"),
]

_VPN = [
    ("Cisco AnyConnect / Secure Client", ["vpnagent", "csc_vpnagent"],
     "Cisco VPN agent"),
    ("Palo Alto GlobalProtect", ["pangps"], "GlobalProtect VPN"),
    ("Zscaler", ["zsaservice", "zscalerservice", "zsatrayhelper"], "Zscaler ZTNA"),
    ("Tailscale", ["tailscale"], "Tailscale mesh VPN"),
    ("OpenVPN", ["openvpnservice", "openvpnserviceinteractive"], "OpenVPN client"),
]

_BACKUP = [
    ("Veeam Agent", ["veeamendpointbackupsvc", "veeamservice", "veeamagent"],
     "Veeam backup agent"),
    ("Acronis", ["acronis agent core service", "acronisagent",
                 "acronis managed machine service"], "Acronis backup"),
    ("Cohesity", ["cohesityagent"], "Cohesity backup agent"),
    ("CrashPlan", ["crashplanservice", "code42service"], "CrashPlan / Code42 backup"),
]

_CATEGORIES = [
    ("Management", _MANAGEMENT),
    ("Security/EDR", _SECURITY),
    ("VPN", _VPN),
    ("Backup", _BACKUP),
]


def _services():
    """One Win32_Service snapshot → list of dicts with lowercased name keys."""
    rows = as_list(ps_json(
        "Get-CimInstance Win32_Service | "
        "Select-Object Name,DisplayName,State,StartMode,PathName", timeout=40))
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        out.append({
            "name": (r.get("Name") or ""),
            "name_lc": (r.get("Name") or "").lower(),
            "display": r.get("DisplayName") or "",
            "state": (r.get("State") or ""),
            "path": r.get("PathName") or "",
        })
    return out


def _exe_path(pathname):
    """Pull the bare executable path out of a service PathName (handles quotes/args)."""
    if not pathname:
        return None
    p = pathname.strip()
    if p.startswith('"'):
        end = p.find('"', 1)
        return p[1:end] if end > 0 else p[1:]
    # Unquoted: take up to the first space that ends a ".exe".
    low = p.lower()
    idx = low.find(".exe")
    return p[:idx + 4] if idx > 0 else p.split(" ")[0]


def _file_version(pathname):
    """Best-effort file version of a service exe via WMI; None if unavailable."""
    exe = _exe_path(pathname)
    if not exe or ".exe" not in exe.lower():
        return None
    safe = exe.replace("'", "''")
    info = ps_json(
        f"$f = Get-Item -LiteralPath '{safe}'; "
        "$f.VersionInfo.ProductVersion", timeout=20)
    if isinstance(info, str) and info.strip():
        return info.strip()
    return None


def _reg_open(hive, path):
    try:
        return winreg.OpenKey(hive, path)
    except OSError:
        return None


def _reg_val(key, name):
    try:
        value, _ = winreg.QueryValueEx(key, name)
        return value
    except OSError:
        return None


def _sccm_version():
    """ConfigMgr client version from WMI root\\ccm SMS_Client; None if absent."""
    info = ps_json(
        "(Get-CimInstance -Namespace root\\ccm -ClassName SMS_Client"
        " -ErrorAction SilentlyContinue).ClientVersion", timeout=25)
    if isinstance(info, str) and info.strip():
        return info.strip()
    return None


def _mdm_enrollment():
    """Inspect HKLM\\SOFTWARE\\Microsoft\\Enrollments\\* for a real MDM enrollment.

    Returns (enrolled: bool, provider: str|None, upn: str|None).
    Subkeys with a UPN and/or ProviderID indicate an active enrollment; the GUID
    'placeholder' subkeys without those values are ignored.
    """
    root = _reg_open(winreg.HKEY_LOCAL_MACHINE,
                     r"SOFTWARE\Microsoft\Enrollments")
    if not root:
        return False, None, None
    provider = None
    upn = None
    enrolled = False
    with root:
        try:
            count = winreg.QueryInfoKey(root)[0]
        except OSError:
            count = 0
        for i in range(count):
            try:
                sub = winreg.OpenKey(root, winreg.EnumKey(root, i))
            except OSError:
                continue
            with sub:
                sub_upn = _reg_val(sub, "UPN")
                sub_provider = _reg_val(sub, "ProviderID")
                # EnrollmentState == 1 also marks an active enrollment.
                state = _reg_val(sub, "EnrollmentState")
                if sub_upn or sub_provider or state == 1:
                    enrolled = True
                    provider = provider or (str(sub_provider) if sub_provider else None)
                    upn = upn or (str(sub_upn) if sub_upn else None)
    return enrolled, provider, upn


def _mde_onboarded():
    """Defender for Endpoint onboarding state (OnboardingState == 1)."""
    key = _reg_open(
        winreg.HKEY_LOCAL_MACHINE,
        r"SOFTWARE\Microsoft\Windows Advanced Threat Protection\Status")
    if not key:
        return None
    with key:
        state = _reg_val(key, "OnboardingState")
    if state is None:
        return None
    return state == 1


def _match(services, svc_names):
    """Return the matching service dict (preferring a running one), or None."""
    wanted = set(svc_names)
    hits = [s for s in services if s["name_lc"] in wanted]
    if not hits:
        return None
    running = [s for s in hits if s["state"].lower() == "running"]
    return running[0] if running else hits[0]


def corp_agents():
    try:
        services = _services()
        agents = []

        for category, entries in _CATEGORIES:
            for name, svc_names, detail in entries:
                svc = _match(services, svc_names)
                if not svc:
                    continue
                running = svc["state"].lower() == "running"
                version = None
                if name.startswith("ConfigMgr"):
                    version = _sccm_version()
                if not version:
                    version = _file_version(svc["path"])
                full_detail = detail
                if svc["display"]:
                    full_detail = f"{detail} (service '{svc['display']}')"
                agents.append({
                    "name": name,
                    "category": category,
                    "present": True,
                    "running": running,
                    "version": version,
                    "detail": full_detail,
                })

        # MDM enrollment — registry only, no service.
        enrolled, provider, upn = _mdm_enrollment()
        if enrolled:
            detail = "MDM enrolled"
            if provider:
                detail += f" via {provider}"
            if upn:
                detail += f" ({upn})"
            agents.append({
                "name": "MDM enrollment",
                "category": "Management",
                "present": True,
                "running": None,
                "version": None,
                "detail": detail,
            })

        # Defender for Endpoint onboarding — annotate or add from registry.
        mde_onboarded = _mde_onboarded()
        mde = next((a for a in agents if a["name"].startswith("Microsoft Defender for Endpoint")), None)
        if mde_onboarded is True:
            if mde:
                mde["detail"] += " — onboarded"
            else:
                # Onboarded per registry even though the Sense service wasn't matched.
                agents.append({
                    "name": "Microsoft Defender for Endpoint (Sense)",
                    "category": "Security/EDR",
                    "present": True,
                    "running": None,
                    "version": None,
                    "detail": "MDE EDR sensor — onboarded (per registry)",
                })
        elif mde and mde_onboarded is False:
            mde["detail"] += " — not onboarded"

        present_count = len(agents)
        summary = _summarize(agents)
        return {
            "ok": True,
            "agents": agents,
            "present_count": present_count,
            "summary": summary,
        }
    except Exception as exc:
        return {
            "ok": False,
            "agents": [],
            "present_count": 0,
            "summary": f"Could not enumerate corporate agents: {exc}",
        }


def _summarize(agents):
    if not agents:
        return ("No corporate management or security agents detected — "
                "looks like a standalone PC.")

    mgmt = [a for a in agents if a["category"] == "Management"]
    parts = []

    # Management plane.
    mgmt_bits = []
    if any(a["name"].startswith("ConfigMgr") for a in mgmt):
        mgmt_bits.append("SCCM")
    if any("Intune" in a["name"] for a in mgmt):
        mgmt_bits.append("Intune")
    if any(a["name"] == "MDM enrollment" for a in mgmt):
        mgmt_bits.append("MDM")
    if mgmt_bits:
        parts.append("Managed by " + " + ".join(mgmt_bits))
    else:
        parts.append("No central management agent")

    # Defender for Endpoint.
    mde = next((a for a in agents if a["name"].startswith("Microsoft Defender for Endpoint")), None)
    if mde:
        if "onboarded" in mde["detail"] and "not onboarded" not in mde["detail"]:
            parts.append("Defender for Endpoint onboarded")
        else:
            parts.append("Defender for Endpoint present")

    # Other EDR/AV (excluding MDE, already covered).
    for a in agents:
        if a["category"] == "Security/EDR" and not a["name"].startswith("Microsoft Defender"):
            state = "running" if a["running"] else "installed (stopped)"
            parts.append(f"{a['name'].split(' ')[0]} {state}")

    # VPN / backup — just name them.
    for cat, label in (("VPN", "VPN"), ("Backup", "backup")):
        names = [a["name"] for a in agents if a["category"] == cat]
        if names:
            parts.append(f"{label}: {', '.join(names)}")

    return "; ".join(parts) + "."
