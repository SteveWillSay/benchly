"""App updates via winget — list what has updates and upgrade selected / all.

winget has no machine-readable output for `upgrade`, so the fixed-width table is
parsed by deriving column offsets from the header row. winget is also frequently
absent from PATH in elevated / non-interactive sessions, so the real executable
is resolved under WindowsApps when a bare `winget` isn't found.
"""

import glob
import os
import re
import shutil
import subprocess

from .ps import CREATE_NO_WINDOW
from .jobs import JobStore

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_jobs = JobStore()
_winget_path = None

# Common winget result codes (facility 0x8A15). Stored as unsigned ints.
_REBOOT_CODES = {0x8A150109, 0x8A15010A}
_NO_UPDATE_CODES = {0x8A15002B}  # UPDATE_NOT_APPLICABLE — treat as no-op success


def _resolve_winget():
    global _winget_path
    if _winget_path:
        return _winget_path
    found = shutil.which("winget")
    if found:
        _winget_path = found
        return found
    # Fall back to the packaged executable (elevated/SYSTEM sessions lack the alias)
    pattern = os.path.join(
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        "WindowsApps", "Microsoft.DesktopAppInstaller_*_x64__8wekyb3d8bbwe", "winget.exe")
    matches = sorted(glob.glob(pattern))
    if matches:
        _winget_path = matches[-1]
        return _winget_path
    return None


def available():
    return _resolve_winget() is not None


def _run(args, timeout=120):
    exe = _resolve_winget()
    if not exe:
        return None, "winget (App Installer) is not available on this PC."
    try:
        r = subprocess.run([exe] + args, capture_output=True, timeout=timeout,
                           creationflags=CREATE_NO_WINDOW, encoding="utf-8", errors="replace")
        return r, None
    except subprocess.TimeoutExpired:
        return None, f"winget timed out after {timeout}s."
    except Exception as e:
        return None, str(e)


def _clean(text):
    out = []
    for line in (text or "").splitlines():
        line = _ANSI.sub("", line)
        if "\r" in line:
            line = line.split("\r")[-1]
        out.append(line)
    return out


def _parse_table(lines):
    """Parse a winget table by column offsets taken from the header row."""
    header_i = None
    for i, line in enumerate(lines):
        low = line.lower()
        if "name" in low and "id" in low and "version" in low and "available" in low:
            header_i = i
            break
    if header_i is None:
        return []
    header = lines[header_i]
    cols = {}
    for col in ("Id", "Version", "Available", "Source"):
        idx = header.find(col)
        cols[col] = idx if idx >= 0 else None
    name_end = cols["Id"]
    rows = []
    for line in lines[header_i + 2:]:  # skip the --- separator row
        if not line.strip() or line.lstrip().startswith("-"):
            continue
        if re.match(r"^\s*\d+\s+(upgrade|package)", line.strip(), re.I):
            break  # summary footer
        if cols["Id"] is None or len(line) < cols["Id"]:
            continue
        name = line[:name_end].strip()
        pid = line[cols["Id"]:cols["Version"]].strip() if cols["Version"] else line[cols["Id"]:].strip()
        ver = line[cols["Version"]:cols["Available"]].strip() if cols["Available"] else ""
        avail = (line[cols["Available"]:cols["Source"]].strip()
                 if cols["Source"] else line[cols["Available"]:].strip()) if cols["Available"] else ""
        src = line[cols["Source"]:].strip() if cols["Source"] else ""
        if not pid or not name:
            continue
        rows.append({"name": name, "id": pid, "current": ver, "available": avail, "source": src})
    return rows


def list_updates():
    if not available():
        return {"ok": False, "error": "no_winget"}
    r, err = _run(["upgrade", "--include-unknown", "--accept-source-agreements",
                   "--disable-interactivity"], timeout=120)
    if err:
        return {"ok": False, "error": err}
    rows = _parse_table(_clean(r.stdout))
    return {"ok": True, "updates": rows, "count": len(rows)}


def _unsigned(code):
    return code & 0xFFFFFFFF if code is not None else None


def _result_for(code):
    u = _unsigned(code)
    if u == 0:
        return "ok", "Updated"
    if u in _REBOOT_CODES:
        return "reboot", "Updated — reboot required"
    if u in _NO_UPDATE_CODES:
        return "ok", "Already up to date"
    return "error", f"winget error 0x{u:08X}" if u is not None else "Failed"


_COMMON = ["--silent", "--accept-package-agreements", "--accept-source-agreements",
           "--disable-interactivity", "--include-unknown"]


def update_one(pkg_id):
    if not re.match(r"^[\w.+-]+$", str(pkg_id or "")):
        return {"ok": False, "error": "Invalid package id."}
    r, err = _run(["upgrade", "--id", pkg_id, "--exact"] + _COMMON, timeout=600)
    if err:
        return {"ok": False, "error": err}
    state, msg = _result_for(r.returncode)
    return {"ok": state != "error", "state": state, "message": msg, "id": pkg_id}


def _run_all(job):
    proc = None
    exe = _resolve_winget()
    if not exe:
        job["lines"].append("winget is not available.")
        job["state"] = "error"
        return
    job["lines"].append("Upgrading all packages via winget…")
    try:
        proc = subprocess.Popen(
            [exe, "upgrade", "--all"] + _COMMON,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=CREATE_NO_WINDOW, encoding="utf-8", errors="replace", bufsize=1)
        job["proc"] = proc
        for raw in proc.stdout:
            line = _ANSI.sub("", raw).rstrip()
            if "\r" in line:
                line = line.split("\r")[-1]
            if line.strip():
                job["lines"].append(line)
        proc.wait(timeout=1800)
        state, msg = _result_for(proc.returncode)
        job["lines"].append(msg + ".")
        job["state"] = state
    except Exception as e:
        job["lines"].append(f"Error: {e}")
        job["state"] = "error"
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


def update_all_job():
    if not available():
        return {"ok": False, "error": "winget is not available on this PC."}
    job_id = _jobs.start(_run_all, lines=[], state=None)
    if job_id is None:
        return {"ok": False, "error": "An update is already running."}
    return {"ok": True, "job": job_id}


def get_update_all_job(job_id, offset=0):
    job = _jobs.get(job_id)
    if not job:
        return {"ok": False, "error": "No such job."}
    lines = list(job["lines"])
    return {"ok": True, "lines": lines[int(offset):], "total": len(lines),
            "done": job["done"], "state": job.get("state")}
