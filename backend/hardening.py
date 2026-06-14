"""CIS-lite hardening scorecard + Attack Surface Reduction roller.

A curated set of high-value Windows hardening checks scored into a number, each
with a one-click, reversible fix that documents exactly what it changes. ASR rules
get an audit-first roller (audit just logs; block enforces). Nothing is applied
automatically — every fix is opt-in and admin-gated.
"""

import re
import winreg

from .ps import ps_json, as_list, run_ps
from . import security

HKLM = winreg.HKEY_LOCAL_MACHINE

# Registry DWORD controls: key -> (path, name, recommended, label, cat, help, where, apply_needs_reboot)
_REG = {
    "llmnr": (r"SOFTWARE\Policies\Microsoft\Windows NT\DNSClient", "EnableMulticast", 0,
              "Disable LLMNR", "Network",
              "LLMNR lets attackers on the LAN poison name resolution to steal credentials.",
              r"HKLM\SOFTWARE\Policies\Microsoft\Windows NT\DNSClient\EnableMulticast = 0"),
    "scriptblock": (r"SOFTWARE\Policies\Microsoft\Windows\PowerShell\ScriptBlockLogging",
                    "EnableScriptBlockLogging", 1,
                    "Log PowerShell script blocks", "Logging",
                    "Records what PowerShell actually runs — essential evidence after a fileless attack.",
                    r"HKLM\…\PowerShell\ScriptBlockLogging\EnableScriptBlockLogging = 1"),
    "autorun": (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer", "NoDriveTypeAutoRun", 255,
                "Disable AutoRun on all drives", "Removable media",
                "Stops programs auto-running off USB sticks and network drives.",
                r"HKLM\…\Policies\Explorer\NoDriveTypeAutoRun = 255"),
    "nla": (r"SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp", "UserAuthentication", 1,
            "Require Network Level Auth for RDP", "Remote Desktop",
            "Forces authentication before a remote-desktop session is created.",
            r"HKLM\SYSTEM\…\RDP-Tcp\UserAuthentication = 1"),
    "installer_noelevate": (r"SOFTWARE\Policies\Microsoft\Windows\Installer", "AlwaysInstallElevated", 0,
            "Block always-elevated installers", "Privilege",
            "AlwaysInstallElevated lets any user install as SYSTEM — a classic privilege-escalation hole.",
            r"HKLM\…\Windows\Installer\AlwaysInstallElevated = 0"),
}


def _reg_read(path, name):
    try:
        k = winreg.OpenKey(HKLM, path)
        try:
            v, _ = winreg.QueryValueEx(k, name)
            return v
        finally:
            winreg.CloseKey(k)
    except OSError:
        return None


def _reg_write(path, name, value):
    k = winreg.CreateKeyEx(HKLM, path, 0, winreg.KEY_SET_VALUE)
    try:
        winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, value)
    finally:
        winreg.CloseKey(k)


def _special_state():
    """SMBv1, Guest account, Defender PUA — read current state."""
    out = ps_json(
        "[pscustomobject]@{ "
        "Smb1=(Get-SmbServerConfiguration -ErrorAction SilentlyContinue).EnableSMB1Protocol; "
        "Guest=(Get-LocalUser -Name 'Guest' -ErrorAction SilentlyContinue).Enabled; "
        "Pua=(Get-MpPreference -ErrorAction SilentlyContinue).PUAProtection }", timeout=30) or {}
    return out


def scorecard():
    admin = security.is_admin()
    sp = _special_state()
    controls = []

    def add(key, cat, label, help_, where, ok, current, recommended, fixable=True, needs_admin=True):
        controls.append({"key": key, "cat": cat, "label": label, "help": help_, "where": where,
                         "ok": ok, "current": current, "recommended": recommended,
                         "fixable": fixable, "admin": needs_admin})

    for key, (path, name, rec, label, cat, help_, where) in _REG.items():
        cur = _reg_read(path, name)
        add(key, cat, label, help_, where, cur == rec,
            "set" if cur == rec else ("not set" if cur is None else str(cur)),
            str(rec))

    # specials
    add("smb1", "Network", "Disable the SMBv1 protocol",
        "SMBv1 is ancient and wormable (EternalBlue/WannaCry). Disable it unless a very old NAS needs it.",
        "Set-SmbServerConfiguration -EnableSMB1Protocol $false",
        sp.get("Smb1") is False, "disabled" if sp.get("Smb1") is False else "enabled", "disabled")
    add("guest", "Accounts", "Disable the Guest account",
        "The built-in Guest account should stay disabled.",
        "Disable-LocalUser -Name Guest",
        sp.get("Guest") is not True, "disabled" if sp.get("Guest") is not True else "enabled", "disabled")
    add("pua", "Defender", "Block potentially unwanted apps (PUA)",
        "Defender's PUA protection blocks bundleware, adware and dodgy 'optimisers'.",
        "Set-MpPreference -PUAProtection 1",
        sp.get("Pua") in (1, 2), "on" if sp.get("Pua") in (1, 2) else "off", "on")

    passed = sum(1 for c in controls if c["ok"])
    score = round(passed / len(controls) * 100) if controls else 0
    return {"ok": True, "is_admin": admin, "controls": controls,
            "passed": passed, "total": len(controls), "score": score}


def apply_control(key):
    if not security.is_admin():
        return {"ok": False, "error": "Hardening changes need elevation — use Run as admin."}
    if key in _REG:
        path, name, rec, label, *_ = _REG[key]
        try:
            _reg_write(path, name, rec)
            return {"ok": True, "where": f"HKLM\\{path}\\{name} = {rec}",
                    "reboot": key in ("nla",)}
        except OSError as e:
            return {"ok": False, "error": str(e)}
    cmd = {
        "smb1": "Set-SmbServerConfiguration -EnableSMB1Protocol $false -Force; 'OK'",
        "guest": "Disable-LocalUser -Name 'Guest' -ErrorAction Stop; 'OK'",
        "pua": "Set-MpPreference -PUAProtection 1; 'OK'",
    }.get(key)
    if not cmd:
        return {"ok": False, "error": "Unknown control."}
    out = run_ps("& { " + cmd + " }", timeout=40)
    if "OK" in out:
        return {"ok": True, "where": cmd.split(";")[0]}
    return {"ok": False, "error": "The change didn't apply (it may need a higher privilege)."}


# --------------------------------------------------------------------------- #
# ASR rules — audit-first roller
# --------------------------------------------------------------------------- #
_ASR = {
    "d4f940ab-401b-4efc-aadc-ad5f3c50688a": "Block Office apps from creating child processes",
    "3b576869-a4ec-4529-8536-b80a7769e899": "Block Office apps from creating executable content",
    "5beb7efe-fd9a-4556-801d-275e5ffc04cc": "Block obfuscated scripts",
    "92e97fa1-2edf-4476-bdd6-9dd0b4dddc7b": "Block Win32 API calls from Office macros",
    "b2b3f03d-6a65-4f7b-a9c7-1c7ef74a9ba4": "Block untrusted/unsigned processes from USB",
    "be9ba2d9-53ea-4cdc-84e5-9b1eeee46550": "Block executable content from email & webmail",
    "01443614-cd74-433a-b99e-2ecdc07bfc25": "Block executables unless they meet age/prevalence",
    "c1db55ab-c21a-4637-bb3f-a12568109d35": "Use advanced ransomware protection",
}
_STATE = {0: "off", 1: "block", 2: "audit", 6: "warn"}


def asr_rules():
    d = ps_json("$p=Get-MpPreference -ErrorAction SilentlyContinue; [pscustomobject]@{ "
                "Ids=@($p.AttackSurfaceReductionRules_Ids); Actions=@($p.AttackSurfaceReductionRules_Actions) }",
                timeout=30, depth=3) or {}
    ids = [str(i).lower() for i in as_list(d.get("Ids"))]
    actions = as_list(d.get("Actions"))
    state = {ids[i]: actions[i] for i in range(min(len(ids), len(actions)))}
    rules = []
    for rid, label in _ASR.items():
        act = state.get(rid, 0)
        rules.append({"id": rid, "label": label, "state": _STATE.get(act, "off")})
    return {"ok": True, "rules": rules, "is_admin": security.is_admin()}


def set_asr(rule_id, mode):
    if not security.is_admin():
        return {"ok": False, "error": "Changing ASR rules needs elevation — use Run as admin."}
    if rule_id.lower() not in _ASR:
        return {"ok": False, "error": "Unknown ASR rule."}
    action = {"off": "Disabled", "audit": "AuditMode", "block": "Enabled"}.get(mode)
    if not action:
        return {"ok": False, "error": "Mode must be off, audit or block."}
    out = run_ps(f"& {{ Add-MpPreference -AttackSurfaceReductionRules_Ids '{rule_id}' "
                 f"-AttackSurfaceReductionRules_Actions {action} -ErrorAction SilentlyContinue; 'OK' }}", timeout=30)
    if "OK" in out:
        return {"ok": True, "where": f"ASR {rule_id} → {mode}"}
    return {"ok": False, "error": "Couldn't change the ASR rule."}
