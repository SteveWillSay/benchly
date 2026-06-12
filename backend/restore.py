"""System Restore — the 'safety net before I touch anything' feature.

Creating a checkpoint needs admin and System Protection enabled on C:. Windows
also rate-limits checkpoints to one per 24h unless a registry value relaxes it;
we set it just for our call so a tech can always make a fresh point.
"""

import subprocess

from .ps import ps_json, run_ps, as_list, cim_date, CREATE_NO_WINDOW
from . import security


def status():
    """Is System Protection on for C:, and what points exist?"""
    return {
        "points": list_points(),
        "protection_on": _protection_on(),
        "is_admin": security.is_admin(),
    }


def _protection_on():
    out = run_ps(
        "(Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SystemRestore' "
        "-Name RPSessionInterval -ErrorAction SilentlyContinue).RPSessionInterval")
    try:
        return int(out.strip()) >= 1
    except (ValueError, AttributeError):
        # Fall back to whether any restore points exist / the cmdlet works
        return None


def list_points():
    rows = as_list(ps_json(
        "Get-ComputerRestorePoint -ErrorAction SilentlyContinue | "
        "Select-Object SequenceNumber,Description,RestorePointType,CreationTime", timeout=45))
    pts = []
    types = {0: "Application install", 1: "Application uninstall", 10: "Device driver install",
             12: "Modify settings", 13: "Cancelled operation", 7: "Restore", 100: "Manual checkpoint"}
    for r in rows:
        pts.append({
            "seq": r.get("SequenceNumber"),
            "description": r.get("Description") or "",
            "type": types.get(r.get("RestorePointType"), str(r.get("RestorePointType"))),
            "created": cim_date(r.get("CreationTime")),
        })
    pts.sort(key=lambda x: x["seq"] or 0, reverse=True)
    return pts


def create_point(description="Benchly checkpoint"):
    if not security.is_admin():
        return {"ok": False, "error": "Creating a restore point needs elevation — use Run as admin."}
    safe = "".join(c for c in description if c.isalnum() or c in " -_")[:60] or "Benchly checkpoint"
    # Enable protection on C: if off, relax the 24h frequency limit for this call,
    # then checkpoint.
    script = (
        "$ErrorActionPreference='Stop'; "
        "try { Enable-ComputerRestore -Drive 'C:\\' } catch {} "
        "New-ItemProperty -Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SystemRestore' "
        "-Name SystemRestorePointCreationFrequency -Value 0 -PropertyType DWord -Force | Out-Null; "
        f"try {{ Checkpoint-Computer -Description '{safe}' -RestorePointType MODIFY_SETTINGS; 'OK' }} "
        "catch { 'ERR: ' + $_.Exception.Message }")
    out = run_ps(script, timeout=120)
    if "OK" in out:
        return {"ok": True}
    detail = out.split("ERR:", 1)[-1].strip() if "ERR:" in out else (out.strip() or "unknown error")
    if "disabled" in detail.lower() or "protection" in detail.lower():
        detail += " (System Protection may be disabled by policy on this machine)."
    return {"ok": False, "error": f"Checkpoint failed: {detail[:200]}"}


def open_restore_ui():
    try:
        subprocess.Popen(["rstrui.exe"], creationflags=CREATE_NO_WINDOW)
        return {"ok": True}
    except OSError as e:
        return {"ok": False, "error": str(e)}
