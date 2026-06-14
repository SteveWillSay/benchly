"""Baseline snapshot & diff — answer "what changed since this machine last worked?"."""

import datetime
import json
import os
import socket
import winreg

from .settings import APP_DIR as _DIR
from . import software, security, sysinfo

_PATH = os.path.join(_DIR, "baseline.json")

# --- everyday user-facing settings (the "what changed?" detective) --------------
_HKCU = winreg.HKEY_CURRENT_USER
_ADV = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"

_PROGID = {
    "ChromeHTML": "Google Chrome", "MSEdgeHTM": "Microsoft Edge", "MSEdgeMHT": "Microsoft Edge",
    "MSEdgePDF": "Microsoft Edge", "FirefoxURL": "Firefox", "FirefoxHTML": "Firefox",
    "BraveHTML": "Brave", "OperaStable": "Opera", "IE.HTTP": "Internet Explorer",
    "AppXq0fevzme2pys62n3e0fbqa7peapykr8v": "Microsoft Edge",
    "AcroExch.Document.DC": "Adobe Acrobat", "Acrobat.Document.DC": "Adobe Acrobat",
}

# key -> (registry path, value name, friendly label)
_SETTINGS = {
    "ui_language": (r"Control Panel\International", "LocaleName", "Display / region language"),
    "default_browser": (r"Software\Microsoft\Windows\Shell\Associations\URLAssociations\https\UserChoice", "ProgId", "Default browser"),
    "default_pdf": (r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.pdf\UserChoice", "ProgId", "Default PDF app"),
    "taskbar_align": (_ADV, "TaskbarAl", "Taskbar alignment"),
    "dark_mode": (_ADV, "AppsUseLightTheme", "App theme"),
    "hide_ext": (_ADV, "HideFileExt", "File extensions"),
    "mouse_swap": (r"Control Panel\Mouse", "SwapMouseButtons", "Mouse buttons"),
    "text_scale": (r"Software\Microsoft\Accessibility", "TextScaleFactor", "Text size"),
}
# keys whose old value we can safely write straight back (simple toggles)
_REVERTABLE = {"taskbar_align": "dword", "dark_mode": "dword", "hide_ext": "dword",
               "mouse_swap": "sz", "text_scale": "dword"}


def _reg_get(path, name):
    try:
        k = winreg.OpenKey(_HKCU, path)
        try:
            v, _ = winreg.QueryValueEx(k, name)
            return v
        finally:
            winreg.CloseKey(k)
    except OSError:
        return None


def _settings_snapshot():
    return {key: _reg_get(path, name) for key, (path, name, _) in _SETTINGS.items()}


def _fmt_setting(key, val):
    if val is None:
        return "not set"
    if key in ("default_browser", "default_pdf"):
        return _PROGID.get(str(val), str(val))
    if key == "taskbar_align":
        return "Left" if val == 0 else "Centre"
    if key == "dark_mode":
        return "Dark" if val == 0 else "Light"
    if key == "hide_ext":
        return "Hidden" if val == 1 else "Shown"
    if key == "mouse_swap":
        return "Swapped (left-handed)" if str(val) == "1" else "Normal"
    if key == "text_scale":
        return f"{val}%"
    return str(val)


def _snapshot():
    inv = sysinfo.get_inventory()
    health = security.get_health()
    return {
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "host": socket.gethostname(),
        "os_build": inv["os"].get("build"),
        "score": health["score"],
        "apps": {a["name"]: a["version"] for a in software.get_installed()},
        "services": {s["name"]: {"start": s["start"], "status": s["status"]}
                     for s in software.get_services()},
        "startup": {s["name"]: s["command"] for s in software.get_startup()},
        "settings": _settings_snapshot(),
    }


def revert_setting(key, raw_value):
    """Write a previously-snapshotted setting value back (simple toggles only)."""
    kind = _REVERTABLE.get(key)
    if not kind:
        return {"ok": False, "error": "This change has to be undone manually in Settings."}
    path, name, label = _SETTINGS[key]
    try:
        k = winreg.CreateKeyEx(_HKCU, path, 0, winreg.KEY_SET_VALUE)
        try:
            if kind == "dword":
                winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, int(raw_value))
            else:
                winreg.SetValueEx(k, name, 0, winreg.REG_SZ, str(raw_value))
        finally:
            winreg.CloseKey(k)
        return {"ok": True, "restart": "explorer", "where": f"HKCU\\{path}\\{name}"}
    except (OSError, ValueError) as e:
        return {"ok": False, "error": str(e)}


def save_baseline():
    try:
        os.makedirs(_DIR, exist_ok=True)
        snap = _snapshot()
        with open(_PATH, "w", encoding="utf-8") as f:
            json.dump(snap, f)
        return {"ok": True, "time": snap["time"],
                "counts": {"apps": len(snap["apps"]), "services": len(snap["services"]),
                           "startup": len(snap["startup"])}}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_baseline_info():
    if not os.path.exists(_PATH):
        return {"exists": False}
    try:
        with open(_PATH, encoding="utf-8") as f:
            snap = json.load(f)
        return {"exists": True, "time": snap.get("time"), "host": snap.get("host"),
                "score": snap.get("score"),
                "counts": {"apps": len(snap.get("apps", {})), "services": len(snap.get("services", {})),
                           "startup": len(snap.get("startup", {}))}}
    except Exception:
        return {"exists": False}


def compare_baseline():
    if not os.path.exists(_PATH):
        return {"ok": False, "error": "No baseline saved yet."}
    try:
        with open(_PATH, encoding="utf-8") as f:
            base = json.load(f)
    except Exception as e:
        return {"ok": False, "error": f"Baseline unreadable: {e}"}

    now = _snapshot()

    def dict_diff(old, new):
        added = [{"name": k, "value": _short(new[k])} for k in new if k not in old]
        removed = [{"name": k, "value": _short(old[k])} for k in old if k not in new]
        changed = [{"name": k, "old": _short(old[k]), "new": _short(new[k])}
                   for k in new if k in old and old[k] != new[k]]
        for lst in (added, removed, changed):
            lst.sort(key=lambda x: x["name"].lower())
        return added, removed, changed

    apps_added, apps_removed, apps_changed = dict_diff(base.get("apps", {}), now["apps"])
    svc_added, svc_removed, svc_changed = dict_diff(base.get("services", {}), now["services"])
    su_added, su_removed, su_changed = dict_diff(base.get("startup", {}), now["startup"])

    # everyday-settings diff, rendered in plain English with one-click undo where safe
    base_set = base.get("settings", {})
    settings_changed = []
    for key, old_raw in base_set.items():
        new_raw = now["settings"].get(key)
        if old_raw != new_raw:
            settings_changed.append({
                "key": key, "label": _SETTINGS[key][2],
                "old": _fmt_setting(key, old_raw), "new": _fmt_setting(key, new_raw),
                "old_raw": old_raw, "revertable": key in _REVERTABLE,
            })
    settings_changed.sort(key=lambda x: x["label"].lower())

    return {
        "ok": True,
        "baseline_time": base.get("time"),
        "now_time": now["time"],
        "score": {"old": base.get("score"), "new": now["score"]},
        "os_build": {"old": base.get("os_build"), "new": now["os_build"]},
        "settings": settings_changed,
        "apps": {"added": apps_added, "removed": apps_removed, "changed": apps_changed},
        "services": {"added": svc_added, "removed": svc_removed, "changed": svc_changed},
        "startup": {"added": su_added, "removed": su_removed, "changed": su_changed},
        "clean": not any([settings_changed, apps_added, apps_removed, apps_changed, svc_added,
                          svc_removed, svc_changed, su_added, su_removed, su_changed,
                          base.get("os_build") != now["os_build"]]),
    }


def _short(v):
    s = v if isinstance(v, str) else json.dumps(v)
    return s if len(s) <= 120 else s[:117] + "…"
