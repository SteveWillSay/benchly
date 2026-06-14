"""Consumer-safety checks: remote-access / scam aftermath, and browser hijack detection.

Detection-first and reversible — Benchly flags and explains, it does not delete
heuristically-flagged files. Real malware removal is handed off to Defender/Malwarebytes.
"""

import glob
import json
import os
import re

import psutil

from .ps import ps_json, run_ps, as_list
from . import software

# Remote-access tools scammers commonly leave behind. (display-name fragment, friendly)
_RAT_TOOLS = {
    "anydesk": "AnyDesk", "teamviewer": "TeamViewer", "ultraviewer": "UltraViewer",
    "screenconnect": "ScreenConnect / ConnectWise", "connectwise": "ConnectWise Control",
    "logmein": "LogMeIn", "gotoassist": "GoToAssist", "go2assist": "GoToAssist",
    "splashtop": "Splashtop", "remotepc": "RemotePC", "supremo": "Supremo",
    "aeroadmin": "AeroAdmin", "dwagent": "DWAgent", "dwservice": "DWService",
    "zoho assist": "Zoho Assist", "zohoassist": "Zoho Assist", "ammyy": "Ammyy Admin",
    "vnc": "VNC (some variant)", "remoteutilities": "Remote Utilities",
    "chrome remote desktop": "Chrome Remote Desktop", "rustdesk": "RustDesk",
    "quickassist": "Quick Assist", "atera": "Atera agent", "syncro": "Syncro agent",
}
_RAT_PROC = {
    "anydesk.exe", "teamviewer.exe", "tv_w32.exe", "tv_x64.exe", "ultraviewer_desktop.exe",
    "screenconnect.clientservice.exe", "connectwisecontrol.client.exe", "logmein.exe",
    "lmiguardiansvc.exe", "g2comm.exe", "g2svc.exe", "srserver.exe", "splashtop.exe",
    "strwinclt.exe", "remotepcservice.exe", "supremosystem.exe", "supremo.exe",
    "aeroadmin.exe", "dwagent.exe", "dwagsvc.exe", "rustdesk.exe", "remoteutilities.exe",
    "rutserv.exe", "rfusclient.exe", "winvnc.exe", "tvnserver.exe", "quickassist.exe",
    "remotedesktophost.exe", "ammyy.exe", "zaservice.exe", "zohours.exe",
}


def remote_access_audit():
    # installed + running RAT tools
    installed = software.get_installed()
    found = {}
    for app in installed:
        low = (app["name"] or "").lower()
        for frag, friendly in _RAT_TOOLS.items():
            if frag in low:
                found.setdefault(friendly, {"name": friendly, "installed": True,
                                            "running": False, "detail": app["name"]})
    running = {}
    for p in psutil.process_iter(["name"]):
        try:
            n = (p.info["name"] or "").lower()
        except Exception:
            continue
        if n in _RAT_PROC:
            running[n] = True
            label = next((v for k, v in _RAT_TOOLS.items() if k.replace(" ", "") in n.replace(" ", "")), n)
            entry = found.get(label) or {"name": label, "installed": False, "detail": p.info["name"]}
            entry["running"] = True
            found[label] = entry

    # local administrators + recently created accounts
    admins = as_list(ps_json(
        "Get-LocalGroupMember -Group Administrators -ErrorAction SilentlyContinue | "
        "Select-Object Name,ObjectClass", timeout=30))
    admin_list = [{"name": a.get("Name"), "class": a.get("ObjectClass")} for a in admins]

    new_accounts = as_list(ps_json(
        "Get-LocalUser -ErrorAction SilentlyContinue | Where-Object { $_.Enabled } | "
        "Select-Object Name,@{n='Created';e={ if ($_.PasswordLastSet) { $_.PasswordLastSet.ToString('yyyy-MM-dd') } else { '' } }},Description", timeout=30))
    accounts = [{"name": a.get("Name"), "created": a.get("Created"), "desc": a.get("Description") or ""}
                for a in new_accounts]

    return {
        "tools": sorted(found.values(), key=lambda x: (not x["running"], x["name"])),
        "admins": admin_list,
        "accounts": accounts,
        "any_running": any(t["running"] for t in found.values()),
    }


def reset_proxy():
    """Clear a hijacked system proxy / PAC URL (a common adware redirect)."""
    import winreg
    path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    changed = []
    try:
        k = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.SetValueEx(k, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            changed.append("ProxyEnable=0")
            for name in ("ProxyServer", "AutoConfigURL"):
                try:
                    winreg.DeleteValue(k, name)
                    changed.append(f"cleared {name}")
                except OSError:
                    pass
        finally:
            winreg.CloseKey(k)
    except OSError as e:
        return {"ok": False, "error": str(e)}
    import subprocess
    from .ps import CREATE_NO_WINDOW
    try:
        subprocess.run(["netsh", "winhttp", "reset", "proxy"], capture_output=True,
                       timeout=15, creationflags=CREATE_NO_WINDOW)
        changed.append("netsh winhttp reset proxy")
    except Exception:
        pass
    return {"ok": True, "detail": "; ".join(changed),
            "where": r"HKCU\…\Internet Settings (ProxyEnable/ProxyServer/AutoConfigURL) + winhttp"}


def post_scam_check():
    """One guided pass after a suspected scam / remote-access incident."""
    from . import persistence, defender
    ra = remote_access_audit()
    per = persistence.map_persistence()
    dfn = defender.audit_defender()

    findings = []
    if ra["tools"]:
        running = [t["name"] for t in ra["tools"] if t["running"]]
        findings.append({"level": "warn" if running else "info",
                         "title": "Remote-access tools",
                         "detail": (("Running now: " + ", ".join(running) + ". ") if running else "")
                                   + "Installed: " + ", ".join(t["name"] for t in ra["tools"]) + "."})
    if per["total"]:
        bits = []
        if per["wmi"]:
            bits.append(f"{len(per['wmi'])} WMI subscription(s)")
        if per["services"]:
            bits.append(f"{len(per['services'])} odd service(s)")
        if per["tasks"]:
            bits.append(f"{len(per['tasks'])} odd task(s)")
        findings.append({"level": "warn", "title": "Persistence to review", "detail": ", ".join(bits) + "."})
    if dfn.get("defender") and dfn.get("flagged"):
        findings.append({"level": "warn", "title": "Defender exclusions",
                         "detail": f"{dfn['flagged']} risky exclusion(s) — an attacker may have told Defender to ignore a folder."})
    extra_admins = [a["name"] for a in ra["admins"]
                    if a.get("name") and not re.search(r"\\(administrator|domain admins)$", a["name"], re.I)]
    if len(ra["admins"]) > 1:
        findings.append({"level": "info", "title": "Administrator accounts",
                         "detail": "Members: " + ", ".join(a["name"] for a in ra["admins"]) + ". Remove any you don't recognise."})

    checklist = [
        "Disconnect from the internet if the attacker may still be connected.",
        "Close/uninstall any remote-access tool you didn't set up (see above).",
        "From a DIFFERENT, trusted device, change passwords for email and banking first.",
        "Turn on two-factor authentication where you can.",
        "Call your bank if you shared card details or they touched financial sites.",
        "Review the persistence, exclusions and accounts flagged above and remove anything you don't recognise.",
        "Run a full antivirus scan.",
    ]
    return {"ok": True, "findings": findings, "checklist": checklist,
            "clean": not any(f["level"] == "warn" for f in findings)}


# ---- browser hijack scan ---------------------------------------------------------

_CHROMIUM = [
    ("Chrome", os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data")),
    ("Edge", os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Edge", "User Data")),
    ("Brave", os.path.join(os.environ.get("LOCALAPPDATA", ""), "BraveSoftware", "Brave-Browser", "User Data")),
]
_KNOWN_SEARCH = ("google", "bing", "duckduckgo", "yahoo", "ecosia", "startpage", "brave", "qwant")


def hijack_scan():
    findings = []

    # 1) hosts file tampering
    hosts = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "drivers", "etc", "hosts")
    try:
        custom = []
        with open(hosts, encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if s and not s.startswith("#"):
                    parts = s.split()
                    if len(parts) >= 2:
                        loopback = parts[0] in ("127.0.0.1", "::1")
                        benign = parts[1].lower() in ("localhost", "localhost.localdomain")
                        if not (loopback and benign):
                            custom.append(s)
        if custom:
            findings.append({"kind": "Hosts file", "severity": "warn",
                             "detail": f"{len(custom)} custom hosts entry(ies) — can silently redirect sites.",
                             "items": custom[:12]})
    except OSError:
        pass

    # 2) system proxy (WinINET)
    proxy = ps_json(
        "Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings' "
        "-ErrorAction SilentlyContinue | Select-Object ProxyEnable,ProxyServer,AutoConfigURL", timeout=20)
    if proxy:
        if proxy.get("ProxyEnable") and proxy.get("ProxyServer"):
            findings.append({"kind": "System proxy", "severity": "warn",
                             "detail": f"A proxy is set: {proxy.get('ProxyServer')}. Unexpected proxies route all traffic through a third party.",
                             "items": []})
        if proxy.get("AutoConfigURL"):
            findings.append({"kind": "Proxy auto-config", "severity": "warn",
                             "detail": f"Auto-config script: {proxy.get('AutoConfigURL')}", "items": []})

    # 3) per-browser homepage / search engine
    for browser, root in _CHROMIUM:
        for prof in glob.glob(os.path.join(root, "*")):
            base = os.path.basename(prof)
            if base != "Default" and not base.startswith("Profile"):
                continue
            prefs = _load_prefs(prof)
            if not prefs:
                continue
            # default search engine
            tmpl = ((prefs.get("default_search_provider_data") or {})
                    .get("template_url_data") or {})
            keyword = (tmpl.get("keyword") or tmpl.get("short_name") or "").lower()
            url = (tmpl.get("url") or "").lower()
            if keyword and not any(k in keyword or k in url for k in _KNOWN_SEARCH):
                findings.append({"kind": f"{browser} search engine", "severity": "bad",
                                 "detail": f"Default search is '{tmpl.get('short_name') or keyword}' — an unfamiliar engine is the classic hijack.",
                                 "items": [url[:120]]})
            # startup/homepage URLs
            startup = (prefs.get("session") or {}).get("startup_urls") or []
            home = prefs.get("homepage")
            sus = [u for u in (startup + ([home] if home else []))
                   if u and not any(k in u.lower() for k in _KNOWN_SEARCH + ("newtab", "chrome://", "edge://"))]
            if sus:
                findings.append({"kind": f"{browser} startup pages", "severity": "warn",
                                 "detail": "Custom start/home pages set — check they're intended.",
                                 "items": sus[:6]})

    return {"findings": findings, "clean": not findings}


def _load_prefs(profile_dir):
    for name in ("Preferences", "Secure Preferences"):
        try:
            with open(os.path.join(profile_dir, name), encoding="utf-8", errors="replace") as f:
                data = json.load(f)
            if data:
                return data
        except (OSError, json.JSONDecodeError):
            continue
    return None
