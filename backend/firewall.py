"""Firewall profile + inbound-rules audit — 'what's actually been opened?'

The Security page already shows the firewall on/off. This goes deeper: the per-profile
state (Domain/Private/Public) and the inbound 'allow' rules that are actually enabled —
which app or port, on which profile, from where. Broad allows (any remote address,
especially on the Public profile) and allows for programs in user-writable paths get
flagged. Read-only by default; disabling a rule is optional, confirmed and reversible.
"""

from .ps import ps_json, as_list, run_ps
from . import security

# Genuinely user-writable spots a port-opening binary shouldn't normally live in.
# (ProgramData / Program Files are excluded — too many legit apps there.)
_USER_WRITABLE = ("\\appdata\\", "\\temp\\", "\\downloads\\", "\\\\temp\\")


def _action(v):
    s = str(v)
    if s in ("Block", "4"):
        return "Block"
    if s in ("Allow", "2"):
        return "Allow"
    return "Block (default)"   # NotConfigured → the Windows default, which is Block inbound


def firewall_overview():
    profiles = as_list(ps_json(
        "Get-NetFirewallProfile | Select-Object Name,Enabled,"
        "@{n='In';e={[string]$_.DefaultInboundAction}},"
        "@{n='Out';e={[string]$_.DefaultOutboundAction}}", timeout=25))
    out = []
    for p in profiles:
        if not isinstance(p, dict):
            continue
        out.append({
            "name": p.get("Name"),
            "enabled": p.get("Enabled") in (1, True, "True"),
            "inbound_default": _action(p.get("In")),
            "outbound_default": _action(p.get("Out")),
        })
    return {"ok": True, "profiles": out}


def inbound_allows():
    """Enabled inbound allow rules, joined to their app/port, worst-first."""
    raw = as_list(ps_json(
        "Get-NetFirewallRule -Enabled True -Direction Inbound -Action Allow "
        "-ErrorAction SilentlyContinue | ForEach-Object { "
        "$app = ($_ | Get-NetFirewallApplicationFilter -ErrorAction SilentlyContinue).Program; "
        "$pf  = $_ | Get-NetFirewallPortFilter -ErrorAction SilentlyContinue; "
        "$af  = $_ | Get-NetFirewallAddressFilter -ErrorAction SilentlyContinue; "
        "[pscustomobject]@{ Name=$_.DisplayName; Group=$_.DisplayGroup; "
        "Profiles=[string]$_.Profile; Program=$app; "
        "Proto=$pf.Protocol; Port=[string]$pf.LocalPort; "
        "Remote=[string]$af.RemoteAddress } }", timeout=60, depth=3))

    rules, seen = [], set()
    for r in raw:
        if not isinstance(r, dict):
            continue
        program = (r.get("Program") or "").strip()
        remote = (r.get("Remote") or "Any").strip()
        profiles = (r.get("Profiles") or "").strip()
        port = (r.get("Port") or "Any").strip()
        name = r.get("Name") or "(unnamed rule)"
        key = (name, program.lower(), port, remote, profiles)
        if key in seen:                 # Windows keeps near-duplicate per-binding rules
            continue
        seen.add(key)
        plow = program.lower()
        flags = []
        # the real signal: a port-opener running from a user-writable folder
        if program and program != "Any" and any(w in plow for w in _USER_WRITABLE):
            flags.append("Program runs from a user-writable folder (AppData/Temp/Downloads)")
        on_public = "public" in profiles.lower() or profiles in ("", "Any")
        broad = remote in ("Any", "*", "")
        rules.append({
            "name": name,
            "group": r.get("Group") or "",
            "program": program or "Any",
            "proto": r.get("Proto") or "",
            "port": port,
            "remote": remote,
            "profiles": profiles or "Any",
            "public_any": bool(broad and on_public),   # common & legit — shown, not flagged
            "flags": flags,
        })
    rules.sort(key=lambda x: (len(x["flags"]), x["public_any"]), reverse=True)
    flagged = sum(1 for r in rules if r["flags"])
    return {"ok": True, "rules": rules, "total": len(rules), "flagged": flagged}


def disable_rule(name):
    if not security.is_admin():
        return {"ok": False, "error": "Changing firewall rules needs elevation — use Run as admin."}
    safe = name.replace("'", "''")
    out = run_ps(f"& {{ Disable-NetFirewallRule -DisplayName '{safe}' -ErrorAction SilentlyContinue; 'OK' }}",
                 timeout=20)
    if "OK" in out:
        return {"ok": True, "where": f"Disabled inbound rule '{name}' (re-enable in Windows Firewall)."}
    return {"ok": False, "error": "Couldn't disable that rule."}
