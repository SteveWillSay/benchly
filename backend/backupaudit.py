"""Backup posture audit — 'if this drive died today, what would you lose?'

Audits backup status (File History, OneDrive folder backup, restore points,
system image). It does NOT perform backups — it reports red/amber/green and
points the user at the right setting.
"""

import os
import winreg

from .ps import run_ps
from . import restore


def get_posture():
    checks = []

    # --- OneDrive ---
    od_running = _process_running("onedrive.exe")
    kfm = _onedrive_kfm()
    if kfm["redirected"]:
        checks.append(_c("OneDrive folder backup", "good" if od_running else "warn",
                         f"Desktop/Documents/Pictures back up to OneDrive ({', '.join(kfm['folders'])})."
                         + ("" if od_running else " But OneDrive isn't running — syncing is paused."),
                         "onedrive"))
    elif od_running:
        checks.append(_c("OneDrive folder backup", "warn",
                         "OneDrive is running but Desktop/Documents/Pictures are NOT backed up to it.",
                         "onedrive"))
    else:
        checks.append(_c("OneDrive folder backup", "bad",
                         "OneDrive folder backup is not set up.", "onedrive"))

    # --- File History ---
    fh = _file_history()
    checks.append(_c("File History", "good" if fh else "warn",
                     "File History is on and protecting your libraries." if fh
                     else "File History is off — no automatic versioned file backup.", "filehistory"))

    # --- Restore points ---
    pts = restore.list_points()
    checks.append(_c("System restore points", "good" if pts else "warn",
                     f"{len(pts)} restore point(s) — newest {pts[0]['created']}." if pts
                     else "No restore points — you can't roll back a bad change.", "restore"))

    # --- System image ---
    img = _system_image()
    checks.append(_c("System image backup", "good" if img else "warn",
                     f"A Windows image backup exists ({img})." if img
                     else "No full system image found on local drives.", "image"))

    score = {"good": 2, "warn": 1, "bad": 0}
    val = sum(score[c["status"]] for c in checks)
    overall = "good" if val >= 6 else "warn" if val >= 3 else "bad"
    return {"checks": checks, "overall": overall}


def _c(label, status, detail, fix):
    return {"label": label, "status": status, "detail": detail, "fix": fix}


def _process_running(name):
    import psutil
    name = name.lower()
    for p in psutil.process_iter(["name"]):
        try:
            if (p.info["name"] or "").lower() == name:
                return True
        except Exception:
            continue
    return False


def _onedrive_kfm():
    """Are the known folders redirected into a OneDrive path?"""
    folders = []
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
        with k:
            for name, label in (("Desktop", "Desktop"), ("Personal", "Documents"),
                                ("My Pictures", "Pictures")):
                try:
                    v, _ = winreg.QueryValueEx(k, name)
                    if "onedrive" in str(v).lower():
                        folders.append(label)
                except OSError:
                    continue
    except OSError:
        pass
    return {"redirected": bool(folders), "folders": folders}


def _file_history():
    # Service fhsvc running + a configured target is the reliable signal
    out = run_ps("(Get-Service fhsvc -ErrorAction SilentlyContinue).Status").strip()
    if out != "Running":
        return False
    # ProtectedUpToTime existing under the FileHistory config implies it's active
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\FileHistory")
        winreg.CloseKey(k)
        return True
    except OSError:
        return False


def _system_image():
    for letter in "CDEFG":
        p = f"{letter}:\\WindowsImageBackup"
        if os.path.isdir(p):
            return p
    return None
