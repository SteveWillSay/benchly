"""Installed software, startup entries, services, and hotfix history."""

import os
import re
import winreg

import psutil

from .ps import ps_json, as_list, cim_date as _cim_date

_UNINSTALL_KEYS = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
]

_RUN_KEYS = [
    ("HKLM", winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
    ("HKLM (32-bit)", winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"),
    ("HKCU", winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
]


def _reg_str(key, name):
    try:
        value, vtype = winreg.QueryValueEx(key, name)
        if vtype in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
            return str(value).strip()
        if vtype == winreg.REG_DWORD:
            return value
    except OSError:
        pass
    return None


def get_installed():
    apps, seen = [], set()
    for hive, path in _UNINSTALL_KEYS:
        try:
            root = winreg.OpenKey(hive, path)
        except OSError:
            continue
        with root:
            for i in range(winreg.QueryInfoKey(root)[0]):
                try:
                    sub = winreg.OpenKey(root, winreg.EnumKey(root, i))
                except OSError:
                    continue
                with sub:
                    name = _reg_str(sub, "DisplayName")
                    if not name:
                        continue
                    if _reg_str(sub, "SystemComponent") == 1:
                        continue
                    version = _reg_str(sub, "DisplayVersion") or ""
                    dedupe = (name.lower(), version)
                    if dedupe in seen:
                        continue
                    seen.add(dedupe)
                    size_kb = _reg_str(sub, "EstimatedSize")
                    apps.append({
                        "name": name,
                        "version": version,
                        "publisher": _reg_str(sub, "Publisher") or "",
                        "installed": _fmt_install_date(_reg_str(sub, "InstallDate")),
                        "size": size_kb * 1024 if isinstance(size_kb, int) else None,
                    })
    apps.sort(key=lambda a: a["name"].lower())
    return apps


def _fmt_install_date(raw):
    if raw and isinstance(raw, str) and len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return raw or ""


def _startup_approved():
    """Task-Manager enable/disable state: first byte 0x02 = enabled, 0x03 = disabled."""
    state = {}
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for sub in ("Run", "Run32", "StartupFolder"):
            path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\{sub}"
            try:
                key = winreg.OpenKey(hive, path)
            except OSError:
                continue
            with key:
                for i in range(winreg.QueryInfoKey(key)[1]):
                    try:
                        name, value, vtype = winreg.EnumValue(key, i)
                        if vtype == winreg.REG_BINARY and value:
                            state[name.lower()] = value[0] in (0x02, 0x06)
                    except OSError:
                        continue
    return state


_HEAVY = ("teams", "spotify", "discord", "steam", "epicgames", "adobe", "creative cloud",
          "onedrive", "dropbox", "googledrive", "skype", "slack", "zoom", "outlook",
          "nvidia", "armoury", "icue", "razer", "logi", "synapse", "wallpaper engine")


def _startup_impact(command):
    """Estimated boot impact — labelled 'est.' in the UI. Windows' own rating
    isn't reliably readable, so we approximate from the target's size + vendor."""
    path = None
    import re as _re
    m = _re.match(r'"([^"]+)"', command or "")
    if m:
        path = os.path.expandvars(m.group(1))
    elif command:
        path = os.path.expandvars(command.split(",")[0].split()[0])
    low = (command or "").lower()
    if any(h in low for h in _HEAVY):
        return "High"
    try:
        if path and os.path.isfile(path):
            mb = os.path.getsize(path) / (1024 * 1024)
            return "High" if mb > 40 else "Medium" if mb > 4 else "Low"
    except OSError:
        pass
    return "Low"


def get_startup():
    approved = _startup_approved()
    items = []
    for label, hive, path in _RUN_KEYS:
        try:
            key = winreg.OpenKey(hive, path)
        except OSError:
            continue
        with key:
            for i in range(winreg.QueryInfoKey(key)[1]):
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    items.append({"name": name, "command": str(value), "source": f"Registry {label}",
                                  "enabled": approved.get(name.lower(), True),
                                  "impact": _startup_impact(str(value))})
                except OSError:
                    continue

    for label, folder in [
        ("Startup folder (user)", os.path.join(os.environ.get("APPDATA", ""),
                                                r"Microsoft\Windows\Start Menu\Programs\Startup")),
        ("Startup folder (all users)", os.path.join(os.environ.get("PROGRAMDATA", ""),
                                                    r"Microsoft\Windows\Start Menu\Programs\StartUp")),
    ]:
        if os.path.isdir(folder):
            for entry in os.listdir(folder):
                if entry.lower() == "desktop.ini":
                    continue
                items.append({"name": entry, "command": os.path.join(folder, entry), "source": label,
                              "enabled": approved.get(entry.lower(), True), "impact": "Low"})

    items.sort(key=lambda x: x["name"].lower())
    return items


def get_services():
    services = []
    try:
        for s in psutil.win_service_iter():
            try:
                d = s.as_dict()
                services.append({
                    "name": d.get("name") or "",
                    "display": d.get("display_name") or "",
                    "status": d.get("status") or "",
                    "start": d.get("start_type") or "",
                    "pid": d.get("pid"),
                })
            except Exception:
                continue
    except Exception:
        pass
    # Running first, then automatic-but-stopped (the interesting ones), then rest
    services.sort(key=lambda x: (x["status"] != "running",
                                 not (x["start"] == "automatic" and x["status"] == "stopped"),
                                 x["display"].lower()))
    return services


_WU_HISTORY_PS = r"""
$session = New-Object -ComObject Microsoft.Update.Session
$searcher = $session.CreateUpdateSearcher()
$total = $searcher.GetTotalHistoryCount()
$n = [Math]::Min(80, $total)
if ($n -gt 0) {
    $searcher.QueryHistory(0, $n) | Where-Object { $_.ResultCode -eq 2 -and $_.Title } | ForEach-Object {
        [pscustomobject]@{ Title = $_.Title; Date = $_.Date.ToString('yyyy-MM-dd') }
    }
}
"""


def get_hotfixes():
    rows = as_list(ps_json(
        "Get-CimInstance Win32_QuickFixEngineering | "
        "Select-Object HotFixID,Description,InstalledOn,InstalledBy", timeout=30))
    fixes = []
    for r in rows:
        fixes.append({
            "id": r.get("HotFixID"),
            "desc": r.get("Description") or "",
            "installed": _cim_date(r.get("InstalledOn")),
        })

    # Win 11 cumulative updates often never appear in QFE — fall back to the
    # Windows Update history COM API so the tab isn't misleadingly empty.
    if not fixes:
        for r in as_list(ps_json(_WU_HISTORY_PS, timeout=120)):
            title = r.get("Title") or ""
            kb = re.search(r"KB\d{6,}", title)
            fixes.append({
                "id": kb.group(0) if kb else "—",
                "desc": title,
                "installed": r.get("Date"),
            })

    fixes.sort(key=lambda x: str(x["installed"] or ""), reverse=True)
    return fixes
