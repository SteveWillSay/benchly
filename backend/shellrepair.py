"""Cache & shell repair — the "it just looks broken" fixes.

Rebuilds the user-facing caches that rot after bad shutdowns or updates (blank
icons, broken thumbnails, garbled fonts, dead Start search). Nothing here touches
user data — every cache regenerates itself. Most need a one-off Explorer restart,
which the UI offers at the end.
"""

import glob
import os
import subprocess

from .ps import CREATE_NO_WINDOW, run_ps

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
    "appx": {
        "label": "Re-register all built-in apps",
        "fixes": "Fixes a broken Start menu, missing/crashing built-in apps, or a dead Store after an update.",
        "where": ("Re-registers every built-in app package for the current user with "
                  "Add-AppxPackage -Register against each package's AppXManifest.xml. "
                  "Per-user, no admin needed; nothing is uninstalled or removed, so it's "
                  "safe to re-run. Per-package errors are ignored as expected."),
        "restart": True,
    },
    "appxstore": {
        "label": "Re-register Store & Start menu",
        "fixes": "Fixes just the Microsoft Store, Start menu and shell experience without touching other apps.",
        "where": ("Re-registers only the Microsoft Store, Start menu and shell-experience "
                  "packages (Microsoft.WindowsStore, Microsoft.Windows.ShellExperienceHost, "
                  "Microsoft.Windows.StartMenuExperienceHost) with Add-AppxPackage -Register. "
                  "Per-user, no admin needed; nothing is uninstalled, so it's safe to re-run."),
        "restart": True,
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
        if key == "appx":
            run_ps(
                "Get-AppxPackage -AllUsers | ForEach-Object { "
                "Add-AppxPackage -DisableDevelopmentMode -Register "
                "\"$($_.InstallLocation)\\AppXManifest.xml\" -ErrorAction SilentlyContinue }",
                timeout=300)
            return {"ok": True, "message": "Re-registered built-in apps for this user. Restart Explorer to finish.",
                    "restart": True}
        if key == "appxstore":
            run_ps(
                "Get-AppxPackage -AllUsers | "
                "Where-Object { $_.Name -in @('Microsoft.WindowsStore',"
                "'Microsoft.Windows.ShellExperienceHost',"
                "'Microsoft.Windows.StartMenuExperienceHost') } | ForEach-Object { "
                "Add-AppxPackage -DisableDevelopmentMode -Register "
                "\"$($_.InstallLocation)\\AppXManifest.xml\" -ErrorAction SilentlyContinue }",
                timeout=120)
            return {"ok": True, "message": "Re-registered the Store and Start menu. Restart Explorer to finish.",
                    "restart": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "Unknown repair."}
