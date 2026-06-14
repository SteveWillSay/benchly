"""Microsoft Defender exclusion & tamper audit.

Exclusions are the quietest place for malware to hide — a path, extension or
process that Defender is told to ignore. Almost nobody reviews this list. This
surfaces every exclusion, flags the dangerous shapes (user-writable folders,
whole drives, scripting hosts), and shows tamper-protection / real-time / ASR
state. Removal is reversible and admin-gated.
"""

import re

from .ps import ps_json, as_list, run_ps
from . import security

_AUDIT_PS = r"""
$p = Get-MpPreference -ErrorAction SilentlyContinue
$s = Get-MpComputerStatus -ErrorAction SilentlyContinue
[pscustomobject]@{
    Paths      = @($p.ExclusionPath)
    Exts       = @($p.ExclusionExtension)
    Procs      = @($p.ExclusionProcess)
    Ips        = @($p.ExclusionIpAddress)
    AsrIds     = @($p.AttackSurfaceReductionRules_Ids)
    AsrActions = @($p.AttackSurfaceReductionRules_Actions)
    Tamper     = $s.IsTamperProtected
    Rtp        = $s.RealTimeProtectionEnabled
    AmService  = $s.AMServiceEnabled
    SigAge     = $s.AntivirusSignatureAge
    Defender   = ($s -ne $null)
}
"""

_USER_WRITABLE = re.compile(r"\\(appdata|temp|tmp|downloads|programdata|public|users\\public|\$recycle)", re.I)
_SCRIPT_EXT = {".ps1", ".bat", ".cmd", ".vbs", ".vbe", ".js", ".jse", ".hta", ".wsf", ".wsh", ".scr"}
_SCRIPT_HOST = re.compile(r"\\(powershell|pwsh|wscript|cscript|mshta|cmd|rundll32|regsvr32|msbuild)\.exe$", re.I)


def _flag_path(p):
    low = (p or "").lower().strip()
    if re.fullmatch(r"[a-z]:\\?", low):
        return "excludes an entire drive"
    if _USER_WRITABLE.search(low):
        return "in a folder any program can write to"
    return None


def audit_defender():
    d = ps_json(_AUDIT_PS, timeout=45, depth=3) or {}
    if not d.get("Defender"):
        return {"ok": True, "defender": False,
                "message": "Microsoft Defender isn't the active antivirus on this PC, so there are no Defender exclusions to audit."}

    # Without admin, Get-MpPreference returns a "Must be an administrator" placeholder
    raw_excl = as_list(d.get("Paths")) + as_list(d.get("Exts")) + as_list(d.get("Procs"))
    if any("must be an administrator" in str(v).lower() for v in raw_excl):
        flags = []
        if d.get("Tamper"):
            flags.append({"level": "good", "text": "Tamper Protection is on."})
        if d.get("Rtp") is False:
            flags.append({"level": "info", "text": "Microsoft Defender real-time protection is off (a third-party antivirus is likely active)."})
        flags.append({"level": "warn", "text": "Run as admin to read and review the Defender exclusion list."})
        return {"ok": True, "defender": True, "needs_admin": True,
                "exclusions": [], "flagged": 0, "tamper": d.get("Tamper"), "rtp": d.get("Rtp"),
                "asr": {"total": len(as_list(d.get("AsrIds"))), "block": 0, "audit": 0}, "flags": flags}

    exclusions, flagged = [], 0
    for p in as_list(d.get("Paths")):
        reason = _flag_path(p)
        exclusions.append({"kind": "path", "value": p, "risk": reason})
        if reason:
            flagged += 1
    for e in as_list(d.get("Exts")):
        ext = e if str(e).startswith(".") else "." + str(e)
        reason = "a script/executable type — risky to exclude" if ext.lower() in _SCRIPT_EXT else None
        exclusions.append({"kind": "extension", "value": e, "risk": reason})
        if reason:
            flagged += 1
    for pr in as_list(d.get("Procs")):
        reason = "a scripting/living-off-the-land host" if _SCRIPT_HOST.search(str(pr)) else None
        exclusions.append({"kind": "process", "value": pr, "risk": reason})
        if reason:
            flagged += 1
    for ip in as_list(d.get("Ips")):
        exclusions.append({"kind": "ip", "value": ip, "risk": None})

    # ASR rules summary
    asr_ids = as_list(d.get("AsrIds"))
    asr_actions = as_list(d.get("AsrActions"))
    asr_block = sum(1 for a in asr_actions if a == 1)
    asr_audit = sum(1 for a in asr_actions if a == 2)

    flags = []
    if d.get("Tamper") is False:
        flags.append({"level": "warn", "text": "Tamper Protection is OFF — settings can be changed by software."})
    elif d.get("Tamper"):
        flags.append({"level": "good", "text": "Tamper Protection is on."})
    if d.get("Rtp") is False:
        flags.append({"level": "warn", "text": "Real-time protection is OFF."})
    if flagged:
        flags.append({"level": "warn", "text": f"{flagged} exclusion(s) look risky — review them below."})
    elif exclusions:
        flags.append({"level": "good", "text": "No risky-looking exclusions."})
    else:
        flags.append({"level": "good", "text": "No Defender exclusions are set."})
    if not asr_ids:
        flags.append({"level": "info", "text": "No Attack Surface Reduction rules are configured (hardening opportunity)."})

    # risky first
    exclusions.sort(key=lambda x: (x["risk"] is None, x["kind"]))
    return {
        "ok": True, "defender": True,
        "exclusions": exclusions, "flagged": flagged,
        "tamper": d.get("Tamper"), "rtp": d.get("Rtp"), "sig_age_days": d.get("SigAge"),
        "asr": {"total": len(asr_ids), "block": asr_block, "audit": asr_audit},
        "flags": flags,
    }


_REMOVE = {"path": "ExclusionPath", "extension": "ExclusionExtension",
           "process": "ExclusionProcess", "ip": "ExclusionIpAddress"}


def remove_exclusion(kind, value):
    if not security.is_admin():
        return {"ok": False, "error": "Removing an exclusion needs elevation — use Run as admin."}
    param = _REMOVE.get(kind)
    if not param:
        return {"ok": False, "error": "Unknown exclusion type."}
    safe = str(value).replace("'", "''")
    out = run_ps(f"& {{ Remove-MpPreference -{param} '{safe}' -ErrorAction SilentlyContinue; 'OK' }}", timeout=30)
    if "OK" in out:
        return {"ok": True, "where": f"Remove-MpPreference -{param} '{value}'"}
    return {"ok": False, "error": "Couldn't remove the exclusion (it may need a higher privilege)."}
