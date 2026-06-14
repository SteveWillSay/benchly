"""Repair toolbox — streamed SFC / DISM / chkdsk / winsock / Windows Update cache reset.

Jobs run in a background thread; the frontend polls get_job() for new lines.
All tools require elevation.
"""

import subprocess

from .jobs import JobStore
from .ps import CREATE_NO_WINDOW
from . import security

TOOLS = {
    "sfc": {
        "label": "System File Checker",
        "cmd": ["sfc", "/scannow"],
        "encoding": "utf-16-le",
        "note": "Scans and repairs protected system files (5–20 min).",
        "where": "Repairs protected OS files under C:\\Windows from the local component store. Read-only unless it finds damage.",
    },
    "dism_scan": {
        "label": "DISM component scan",
        "cmd": ["DISM", "/Online", "/Cleanup-Image", "/ScanHealth"],
        "encoding": "mbcs",
        "note": "Checks the component store for corruption (2–10 min).",
        "where": "Read-only health check of the component store (C:\\Windows\\WinSxS). Makes no changes.",
    },
    "dism_restore": {
        "label": "DISM component repair",
        "cmd": ["DISM", "/Online", "/Cleanup-Image", "/RestoreHealth"],
        "encoding": "mbcs",
        "note": "Repairs the component store from Windows Update (10–30 min).",
        "where": "Downloads and replaces damaged files in the component store (C:\\Windows\\WinSxS) via Windows Update.",
    },
    "chkdsk": {
        "label": "Disk check (read-only)",
        "cmd": ["chkdsk", "C:"],
        "encoding": "mbcs",
        "note": "Read-only NTFS consistency scan of C: — no reboot needed.",
        "where": "Read-only scan of the C: NTFS filesystem. Makes no changes (no /f or /r).",
    },
    "winsock": {
        "label": "Winsock reset",
        "cmd": ["netsh", "winsock", "reset"],
        "encoding": "mbcs",
        "note": "Resets the network socket catalog. A reboot completes it.",
        "where": "Resets the Winsock catalog in the registry (HKLM\\SYSTEM\\…\\WinSock2) to defaults. Removes layered providers from misbehaving software. Reboot to finish.",
    },
    "wu_reset": {
        "label": "Windows Update cache reset",
        "cmd": None,  # composite, see _WU_RESET
        "encoding": "mbcs",
        "note": "Stops update services, clears SoftwareDistribution, restarts them.",
        "where": "Stops the wuauserv & bits services, deletes C:\\Windows\\SoftwareDistribution, then restarts them. Windows rebuilds the cache on the next update check.",
    },
    "dism_analyze": {
        "label": "Analyze component store (WinSxS)",
        "cmd": ["DISM", "/Online", "/Cleanup-Image", "/AnalyzeComponentStore"],
        "encoding": "mbcs",
        "note": "Read-only — measures the WinSxS store and says whether a cleanup is worth it.",
        "where": "Read-only analysis of C:\\Windows\\WinSxS. Reports actual size, reclaimable space, and 'Cleanup Recommended: Yes/No'. Makes no changes.",
    },
    "dism_cleanup": {
        "label": "Clean up component store",
        "cmd": ["DISM", "/Online", "/Cleanup-Image", "/StartComponentCleanup"],
        "encoding": "mbcs",
        "note": "Removes superseded component versions to reclaim disk space (5–20 min).",
        "where": "Deletes superseded/old component versions from C:\\Windows\\WinSxS. Supported and safe; previously-installed updates can still be uninstalled afterwards.",
    },
    "dism_cleanup_resetbase": {
        "label": "Clean up component store (Reset Base)",
        "cmd": ["DISM", "/Online", "/Cleanup-Image", "/StartComponentCleanup", "/ResetBase"],
        "encoding": "mbcs",
        "note": "Deeper cleanup — but you can no longer uninstall updates installed so far.",
        "where": "Like the cleanup above, plus /ResetBase: it also removes the backups of superseded updates. Reclaims the most space, but already-installed updates become permanent (can't be uninstalled). Use when space matters more than rollback.",
    },
    "reserved_storage": {
        "label": "Reserved storage state",
        "cmd": ["DISM", "/Online", "/Get-ReservedStorageState"],
        "encoding": "mbcs",
        "note": "Read-only — shows whether Windows is holding space reserved for updates.",
        "where": "Read-only. Reports whether Reserved Storage is enabled (the ~7 GB Windows sets aside so updates don't fail for lack of space). Makes no changes.",
    },
}

_WU_RESET = (
    'net stop wuauserv & net stop bits & '
    'rd /s /q "%SystemRoot%\\SoftwareDistribution" & '
    'net start bits & net start wuauserv & echo Update cache reset complete.'
)

_store = JobStore()


def list_tools():
    return [{"id": k, "label": v["label"], "note": v["note"], "where": v["where"]}
            for k, v in TOOLS.items()]


def start_tool(tool_id: str):
    if tool_id not in TOOLS:
        return {"ok": False, "error": "Unknown tool."}
    if not security.is_admin():
        return {"ok": False, "error": "Repair tools need elevation — use Run as admin in the title bar."}
    job_id = _store.start(_run, lines=[], current="", rc=None, tool=tool_id)
    if job_id is None:
        return {"ok": False, "error": "Another repair job is already running."}
    return {"ok": True, "job": job_id, "label": TOOLS[tool_id]["label"]}


def _clean(line):
    return line.split("\r")[-1].strip("\x00").rstrip()


def _run(job):
    spec = TOOLS[job["tool"]]
    proc = None
    try:
        cmd = ["cmd", "/c", _WU_RESET] if spec["cmd"] is None else spec["cmd"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                creationflags=CREATE_NO_WINDOW)
        job["proc"] = proc
        # read1 streams as data arrives, so \r progress lines update live.
        # We keep the WHOLE raw byte buffer and re-decode it each pass rather than
        # re-encoding a carry-over — re-encoding splits UTF-16 (SFC) mid-code-unit.
        read = getattr(proc.stdout, "read1", proc.stdout.read)
        buf = b""

        def commit():
            parts = buf.decode(spec["encoding"], errors="replace").replace("\r\n", "\n").split("\n")
            job["lines"] = [c for ln in parts[:-1] if (c := _clean(ln))]
            job["current"] = _clean(parts[-1])

        while True:
            chunk = read(4096)
            if not chunk:
                break
            buf += chunk
            commit()
        proc.wait()
        parts = buf.decode(spec["encoding"], errors="replace").replace("\r\n", "\n").split("\n")
        job["lines"] = [c for ln in parts if (c := _clean(ln))]
        job["current"] = ""
        job["rc"] = proc.returncode
    except Exception as e:
        job["lines"] = list(job.get("lines") or []) + [f"Error: {e}"]
        job["rc"] = -1
    finally:
        if proc:
            if proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass
            try:
                proc.stdout.close()
            except Exception:
                pass


def get_job(job_id: str, offset: int = 0):
    job = _store.get(job_id)
    if not job:
        return {"ok": False, "error": "No such job."}
    lines = list(job["lines"])   # snapshot — the runner thread mutates this
    return {
        "ok": True,
        "lines": lines[int(offset):],
        "current": job.get("current", ""),
        "done": job["done"],
        "rc": job["rc"],
        "total": len(lines),
    }


def cancel_job(job_id: str):
    job = _store.get(job_id)
    if not job or job["done"]:
        return {"ok": False, "error": "Job is not running."}
    try:
        job["proc"].kill()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
