"""\"Why is it slow right now\" — a short performance snapshot.

Samples for a window (default 30 s) and returns the top CPU / memory / disk
offenders plus system-wide pressure, so a technician can capture what's actually
hogging the machine into a shareable summary. Runs as a background job.
"""

import time

import psutil

from .jobs import JobStore
from .ps import ps_json

_store = JobStore()


def _fmt_mb(n):
    return round(n / (1024 * 1024))


def _perf_counters():
    """Disk queue + commit charge via Get-Counter (standard user, no admin)."""
    try:
        data = ps_json(
            "(Get-Counter '\\PhysicalDisk(_Total)\\Current Disk Queue Length',"
            "'\\Memory\\% Committed Bytes In Use' -ErrorAction SilentlyContinue)."
            "CounterSamples | Select-Object Path,CookedValue", timeout=10)
        out = {}
        for s in (data if isinstance(data, list) else [data] if data else []):
            path = (s.get("Path") or "").lower()
            val = s.get("CookedValue")
            if "disk queue" in path:
                out["disk_queue"] = round(val, 2) if val is not None else None
            elif "committed" in path:
                out["commit_pct"] = round(val, 1) if val is not None else None
        return out
    except Exception:
        return {}


def _run(job):
    window = job["window"]
    ncpu = psutil.cpu_count() or 1
    procs = {}
    for p in psutil.process_iter(["pid", "name"]):
        try:
            p.cpu_percent(None)
            io = p.io_counters() if hasattr(p, "io_counters") else None
            procs[p.pid] = {"proc": p, "name": p.info["name"],
                            "rb0": io.read_bytes if io else 0,
                            "wb0": io.write_bytes if io else 0}
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    disk0 = psutil.disk_io_counters()
    net0 = psutil.net_io_counters()
    psutil.cpu_percent(None)

    steps = max(1, int(window))
    for i in range(steps):
        time.sleep(1)
        job["progress"] = round((i + 1) / steps * 100)

    sys_cpu = psutil.cpu_percent(None)
    vm = psutil.virtual_memory()
    disk1 = psutil.disk_io_counters()
    net1 = psutil.net_io_counters()

    results = []
    for pid, rec in procs.items():
        try:
            p = rec["proc"]
            with p.oneshot():
                cpu = p.cpu_percent(None) / ncpu
                rss = p.memory_info().rss
                io = p.io_counters() if hasattr(p, "io_counters") else None
            d = ((io.read_bytes - rec["rb0"]) + (io.write_bytes - rec["wb0"])) if io else 0
            results.append({"pid": pid, "name": rec["name"], "cpu": round(cpu, 1),
                            "rss_mb": _fmt_mb(rss), "disk_kb": round(d / 1024)})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    top_cpu = sorted(results, key=lambda r: r["cpu"], reverse=True)[:6]
    top_mem = sorted(results, key=lambda r: r["rss_mb"], reverse=True)[:6]
    top_disk = sorted([r for r in results if r["disk_kb"] > 0],
                      key=lambda r: r["disk_kb"], reverse=True)[:6]

    secs = max(1, window)
    job["result"] = {
        "window": window,
        "sys_cpu": round(sys_cpu, 1),
        "mem_pct": vm.percent,
        "mem_avail_mb": _fmt_mb(vm.available),
        "disk_read_mbs": round((disk1.read_bytes - disk0.read_bytes) / secs / 1e6, 1) if disk0 else 0,
        "disk_write_mbs": round((disk1.write_bytes - disk0.write_bytes) / secs / 1e6, 1) if disk0 else 0,
        "net_recv_mbs": round((net1.bytes_recv - net0.bytes_recv) / secs / 1e6, 2) if net0 else 0,
        "net_sent_mbs": round((net1.bytes_sent - net0.bytes_sent) / secs / 1e6, 2) if net0 else 0,
        "top_cpu": top_cpu,
        "top_mem": top_mem,
        "top_disk": top_disk,
        "counters": _perf_counters(),
    }


def start_snapshot(window=30):
    try:
        window = max(5, min(int(window), 120))
    except (TypeError, ValueError):
        window = 30
    job_id = _store.start(_run, window=window, progress=0, result=None)
    if job_id is None:
        return {"ok": False, "error": "A snapshot is already running."}
    return {"ok": True, "job": job_id, "window": window}


def get_snapshot(job_id):
    job = _store.get(job_id)
    if not job:
        return {"ok": False, "error": "No such job."}
    return {"ok": True, "done": job["done"], "progress": job.get("progress", 0),
            "result": job.get("result")}
