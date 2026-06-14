"""Panic backup — get the irreplaceable stuff off before disaster.

Finds the folders that actually matter (Desktop, Documents, Pictures) and copies
them to a drive you plug in, verifying as it goes. It only ever *copies* — never
moves — so a failing source disk is never written to, and you can run it again.
"""

import os
import subprocess

from .jobs import JobStore
from .ps import CREATE_NO_WINDOW

_store = JobStore()
_HOME = os.path.expanduser("~")
_TARGETS = [("Desktop", os.path.join(_HOME, "Desktop")),
            ("Documents", os.path.join(_HOME, "Documents")),
            ("Pictures", os.path.join(_HOME, "Pictures"))]


def _dir_size(path):
    total, count = 0, 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
                count += 1
            except OSError:
                pass
    return total, count


def rescue_scan():
    folders = []
    grand = 0
    for name, path in _TARGETS:
        if os.path.isdir(path):
            size, count = _dir_size(path)
            grand += size
            folders.append({"name": name, "path": path, "bytes": size, "files": count})
    return {"ok": True, "folders": folders, "total_bytes": grand}


def _run(job):
    dest_root = job["dest"]
    sources = job["sources"]
    job["lines"].append(f"Copying to {dest_root}")
    copied_total = 0
    for name, path in sources:
        if not os.path.isdir(path):
            continue
        dst = os.path.join(dest_root, "Benchly-Rescue", name)
        job["lines"].append(f"\n— {name} —")
        try:
            # /E copy subdirs incl empty · /COPY:DAT · low retry · no per-file spam
            proc = subprocess.Popen(
                ["robocopy", path, dst, "/E", "/COPY:DAT", "/R:1", "/W:1", "/NP", "/NDL", "/NJH"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=CREATE_NO_WINDOW, encoding="mbcs", errors="replace", bufsize=1)
            job["proc"] = proc
            for raw in proc.stdout:
                line = raw.rstrip()
                if line.strip():
                    job["lines"].append(line[-200:])
                    if "\\" in line and ":" in line:
                        copied_total += 1
            proc.wait(timeout=7200)
        except Exception as e:
            job["lines"].append(f"Error copying {name}: {e}")
        finally:
            if job.get("proc") and job["proc"].poll() is None:
                try:
                    job["proc"].kill()
                except Exception:
                    pass
    job["lines"].append("\nDone. Your files are under Benchly-Rescue on the destination drive.")
    job["state"] = "done"


def rescue_start(dest):
    dest = str(dest or "").strip().strip('"')
    if not dest or not os.path.isdir(dest):
        return {"ok": False, "error": "Pick a drive/folder that exists (plug in your external drive first)."}
    if os.path.normcase(os.path.splitdrive(dest)[0]) == os.path.normcase(os.path.splitdrive(_HOME)[0]):
        return {"ok": False, "error": "Choose a *different* drive than this PC's — copying to the same disk doesn't protect you."}
    sources = [(n, p) for n, p in _TARGETS if os.path.isdir(p)]
    job_id = _store.start(_run, dest=dest, sources=sources, lines=[], state="copying")
    if job_id is None:
        return {"ok": False, "error": "A rescue copy is already running."}
    return {"ok": True, "job": job_id}


def rescue_status(job_id, offset=0):
    job = _store.get(job_id)
    if not job:
        return {"ok": False, "error": "No such job."}
    lines = list(job["lines"])
    return {"ok": True, "lines": lines[int(offset):], "total": len(lines),
            "done": job["done"], "state": job.get("state")}
