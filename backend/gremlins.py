"""Gremlin hunters — the weird, intermittent Windows problems.

  * Disk/CPU idle culprit: what's actually hammering the machine when "nothing"
    is, by name and behaviour (not just %).
  * USB disconnect tracker: which device keeps dropping, and whether USB selective
    suspend is the cause.
  * Mark the freeze: stamp the moment it hiccuped and pull everything around it.

All read-only.
"""

import re
import time

import psutil

from .ps import ps_json, as_list

# Known background offenders → plain-English explanation
_KNOWN = {
    "searchindexer.exe": "Windows Search is re-indexing your files.",
    "searchprotocolhost.exe": "Windows Search indexer worker.",
    "msmpeng.exe": "Microsoft Defender is scanning files in real time.",
    "mousocoreworker.exe": "Windows Update is working in the background.",
    "usoclient.exe": "Windows Update orchestrator.",
    "tiworker.exe": "Windows is installing/servicing an update.",
    "compattelrunner.exe": "Windows compatibility telemetry is running.",
    "sysmain": "SysMain (Superfetch) is pre-loading apps — heavy on older disks.",
    "wuauclt.exe": "Windows Update client.",
    "trustedinstaller.exe": "Windows component servicing (TrustedInstaller).",
    "dosvc": "Delivery Optimization is downloading updates.",
}


def disk_cpu_culprit(window=8):
    """Sample for a few seconds and rank the real disk/CPU offenders."""
    try:
        window = max(3, min(int(window), 30))
    except (TypeError, ValueError):
        window = 8
    ncpu = psutil.cpu_count() or 1
    procs = {}
    for p in psutil.process_iter(["pid", "name"]):
        try:
            p.cpu_percent(None)
            io = p.io_counters() if hasattr(p, "io_counters") else None
            procs[p.pid] = {"proc": p, "name": p.info["name"] or "?",
                            "rb0": io.read_bytes if io else 0, "wb0": io.write_bytes if io else 0}
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    disk0 = psutil.disk_io_counters()
    time.sleep(window)
    disk1 = psutil.disk_io_counters()

    rows = []
    for pid, rec in procs.items():
        try:
            p = rec["proc"]
            with p.oneshot():
                cpu = p.cpu_percent(None) / ncpu
                io = p.io_counters() if hasattr(p, "io_counters") else None
            dio = ((io.read_bytes - rec["rb0"]) + (io.write_bytes - rec["wb0"])) if io else 0
            if cpu < 0.5 and dio < 1024:
                continue
            name = rec["name"]
            why = _KNOWN.get(name.lower(), "")
            rows.append({"pid": pid, "name": name, "cpu": round(cpu, 1),
                         "disk_kb_s": round(dio / window / 1024), "why": why})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    top_cpu = sorted(rows, key=lambda r: r["cpu"], reverse=True)[:6]
    top_disk = sorted([r for r in rows if r["disk_kb_s"] > 0],
                      key=lambda r: r["disk_kb_s"], reverse=True)[:6]
    secs = max(1, window)
    return {
        "ok": True,
        "window": window,
        "disk_read_mbs": round((disk1.read_bytes - disk0.read_bytes) / secs / 1e6, 1) if disk0 else 0,
        "disk_write_mbs": round((disk1.write_bytes - disk0.write_bytes) / secs / 1e6, 1) if disk0 else 0,
        "top_cpu": top_cpu,
        "top_disk": top_disk,
    }


def _usb_name_map():
    """InstanceId(upper) -> FriendlyName for USB devices, to translate PnP log entries."""
    rows = as_list(ps_json(
        "Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like 'USB*' } | "
        "Select-Object InstanceId,FriendlyName,Status,Present", timeout=30))
    name_map, inventory = {}, []
    for r in rows:
        inst = (r.get("InstanceId") or "").upper()
        fn = r.get("FriendlyName") or inst.split("\\")[-1]
        if inst:
            name_map[inst] = fn
        status = r.get("Status") or ""
        # only flag devices that are PRESENT and faulted (ghosts/not-present = noise)
        if r.get("Present") and status not in ("OK", "Unknown", ""):
            inventory.append({"name": fn, "status": status})
    return name_map, inventory


def usb_drop_history(days=7):
    """Surface USB devices that repeatedly reconnect, plus any in a problem state."""
    try:
        days = max(1, min(int(days), 30))
    except (TypeError, ValueError):
        days = 7
    name_map, inventory = _usb_name_map()
    cmd = (
        "Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Kernel-PnP/Configuration'; "
        "Id=410,411; StartTime=(Get-Date).AddDays(-__DAYS__)} -MaxEvents 600 -ErrorAction SilentlyContinue | "
        "Select-Object @{n='Msg';e={($_.Message -split \"`r?`n\")[0]}}"
    ).replace("__DAYS__", str(days))
    rows = as_list(ps_json(cmd, timeout=45, depth=2))
    counts = {}
    for r in rows:
        m = re.search(r"Device (\S+) was", r.get("Msg") or "")
        if not m:
            continue
        inst = m.group(1).upper()
        # only count entries we can resolve to a real USB device (filters out boot noise)
        fn = name_map.get(inst)
        if fn:
            counts[fn] = counts.get(fn, 0) + 1
    devices = [{"name": k, "events": v} for k, v in counts.items() if v >= 3]
    devices.sort(key=lambda d: d["events"], reverse=True)
    return {"ok": True, "devices": devices[:20], "problem": inventory,
            "total_events": sum(counts.values())}


_LOGS = ("System", "Application")


def mark_freeze(window_secs=90):
    """Correlate everything in the event logs around 'now' (the moment it hiccupped)."""
    try:
        window_secs = max(30, min(int(window_secs), 300))
    except (TypeError, ValueError):
        window_secs = 90
    cmd = (
        "$end=Get-Date; $start=$end.AddSeconds(-__W__); "
        "Get-WinEvent -FilterHashtable @{LogName='System','Application'; StartTime=$start; EndTime=$end; "
        "Level=1,2,3} -MaxEvents 60 -ErrorAction SilentlyContinue | "
        "Select-Object @{n='Time';e={$_.TimeCreated.ToString('HH:mm:ss')}},"
        "@{n='Level';e={$_.LevelDisplayName}},@{n='Provider';e={$_.ProviderName}},"
        "Id,@{n='Msg';e={($_.Message -split \"`r?`n\")[0]}}"
    ).replace("__W__", str(window_secs))
    rows = as_list(ps_json(cmd, timeout=40, depth=2))
    # also grab a one-shot vitals snapshot of the moment
    cpu = psutil.cpu_percent(interval=0.5)
    vm = psutil.virtual_memory()
    events = []
    for r in rows:
        events.append({
            "time": r.get("Time"), "level": r.get("Level"),
            "provider": (r.get("Provider") or "").replace("Microsoft-Windows-", ""),
            "id": r.get("Id"), "msg": (r.get("Msg") or "")[:200],
        })
    # suspicion ranking: errors first
    order = {"Error": 0, "Critical": 0, "Warning": 1}
    events.sort(key=lambda e: order.get(e["level"], 2))
    return {"ok": True, "window": window_secs, "events": events, "count": len(events),
            "cpu": round(cpu, 1), "mem_pct": vm.percent}
