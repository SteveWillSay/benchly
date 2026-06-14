"""Cache & shell repair — the "it just looks broken" fixes.

Rebuilds the user-facing caches that rot after bad shutdowns or updates (blank
icons, broken thumbnails, garbled fonts, dead Start search). Nothing here touches
user data — every cache regenerates itself. Most need a one-off Explorer restart,
which the UI offers at the end.
"""

import glob
import os
import subprocess

from .ps import CREATE_NO_WINDOW

_LOCAL = os.environ.get("LOCALAPPDATA", "")
_WIN = os.environ.get("SystemRoot", r"C:\Windows")

REPAIRS = {
    "icon": {
        "label": "Rebuild icon cache",
        "fixes": "Fixes blank, white or wrong icons on the desktop and in Explorer.",
        "where": r"Clears %LocalAppData%\IconCache.db and …\Explorer\iconcache_* — Windows rebuilds them.",
        "restart": True,
    },
    "thumbnail": {
        "label": "Rebuild thumbnail cache",
        "fixes": "Fixes missing or wrong photo/video thumbnails.",
        "where": r"Clears %LocalAppData%\Microsoft\Windows\Explorer\thumbcache_*.db.",
        "restart": True,
    },
    "font": {
        "label": "Rebuild font cache",
        "fixes": "Fixes garbled text, boxes/☐ instead of letters, or wrong fonts.",
        "where": r"Stops the Windows Font Cache service, clears FNTCACHE.DAT + the FontCache folder, restarts it.",
        "restart": False,
        "admin": True,
    },
    "store": {
        "label": "Reset Microsoft Store cache",
        "fixes": "Fixes a Store that won't open, load or download.",
        "where": "Runs wsreset.exe — clears the Store cache without removing apps.",
        "restart": False,
    },
    "search": {
        "label": "Rebuild Windows Search index",
        "fixes": "Fixes a Start-menu search box that returns nothing or is stuck rebuilding.",
        "where": r"Resets the Search index (HKLM\…\Windows Search\…\SetupCompletedSuccessfully); it re-indexes in the background.",
        "restart": False,
        "admin": True,
    },
}


def list_repairs():
    return [{"key": k, "label": v["label"], "fixes": v["fixes"], "where": v["where"],
             "restart": v["restart"], "admin": v.get("admin", False)} for k, v in REPAIRS.items()]


def _rm(patterns):
    removed = 0
    for pat in patterns:
        for p in glob.glob(pat):
            try:
                os.remove(p)
                removed += 1
            except OSError:
                pass
    return removed


def _run(args, timeout=60):
    try:
        subprocess.run(args, capture_output=True, timeout=timeout, creationflags=CREATE_NO_WINDOW)
        return True
    except Exception:
        return False


def run_repair(key):
    spec = REPAIRS.get(key)
    if not spec:
        return {"ok": False, "error": "Unknown repair."}
    if spec.get("admin"):
        from . import security
        if not security.is_admin():
            return {"ok": False, "error": f"'{spec['label']}' needs elevation — use Run as admin."}
    try:
        if key == "icon":
            _run([os.path.join(_WIN, "System32", "ie4uinit.exe"), "-show"], timeout=20)
            n = _rm([os.path.join(_LOCAL, "IconCache.db"),
                     os.path.join(_LOCAL, "Microsoft", "Windows", "Explorer", "iconcache_*.db")])
            return {"ok": True, "message": f"Cleared {n} icon cache file(s). Restart Explorer to finish.",
                    "restart": True}
        if key == "thumbnail":
            n = _rm([os.path.join(_LOCAL, "Microsoft", "Windows", "Explorer", "thumbcache_*.db")])
            return {"ok": True, "message": f"Cleared {n} thumbnail cache file(s).", "restart": True}
        if key == "font":
            _run(["net", "stop", "FontCache"], timeout=30)
            n = _rm([os.path.join(_WIN, "System32", "FNTCACHE.DAT"),
                     os.path.join(_WIN, "ServiceProfiles", "LocalService", "AppData", "Local",
                                  "FontCache", "*FontCache*")])
            _run(["net", "start", "FontCache"], timeout=30)
            return {"ok": True, "message": f"Rebuilt the font cache ({n} file(s) cleared).", "restart": False}
        if key == "store":
            _run(["wsreset.exe"], timeout=60)
            return {"ok": True, "message": "Store cache reset.", "restart": False}
        if key == "search":
            import winreg
            k = winreg.CreateKeyEx(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows Search", 0, winreg.KEY_SET_VALUE)
            try:
                winreg.SetValueEx(k, "SetupCompletedSuccessfully", 0, winreg.REG_DWORD, 0)
            finally:
                winreg.CloseKey(k)
            _run(["net", "stop", "WSearch"], timeout=30)
            _run(["net", "start", "WSearch"], timeout=30)
            return {"ok": True, "message": "Search index reset — it re-indexes in the background.", "restart": False}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "Unknown repair."}
