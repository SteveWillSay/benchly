"""Physical disk health (SMART), volumes, and a quick folder-size analyzer."""

import os
import string
import threading

import psutil

from .ps import ps_json, as_list

_DISKS_PS = r"""
$o = [ordered]@{}
$o.physical = Get-PhysicalDisk | Select-Object DeviceId,FriendlyName,MediaType,BusType,HealthStatus,OperationalStatus,Size,SpindleSpeed,FirmwareVersion,SerialNumber
$o.reliability = Get-PhysicalDisk | Get-StorageReliabilityCounter -ErrorAction SilentlyContinue | Select-Object DeviceId,Temperature,Wear,PowerOnHours,ReadErrorsTotal,WriteErrorsTotal,StartStopCycleCount
$o.volumes = Get-Volume | Where-Object { $_.DriveLetter } | Select-Object DriveLetter,FileSystemLabel,FileSystem,HealthStatus,Size,SizeRemaining,DriveType
$o
"""

_cache = None
_lock = threading.Lock()


def get_storage(refresh: bool = False):
    global _cache
    with _lock:
        if _cache is None or refresh:
            _cache = _build_storage()
        return _cache


def _build_storage():
    raw = ps_json(_DISKS_PS, timeout=60) or {}
    rel_by_id = {}
    for r in as_list(raw.get("reliability")):
        if r.get("DeviceId") is not None:
            rel_by_id[str(r["DeviceId"])] = r

    disks = []
    for d in as_list(raw.get("physical")):
        rel = rel_by_id.get(str(d.get("DeviceId")), {})
        disks.append({
            "id": d.get("DeviceId"),
            "name": (d.get("FriendlyName") or "").strip(),
            "media": d.get("MediaType"),
            "bus": d.get("BusType"),
            "health": d.get("HealthStatus"),
            "op_status": d.get("OperationalStatus"),
            "size": d.get("Size"),
            "rpm": d.get("SpindleSpeed") or None,
            "firmware": d.get("FirmwareVersion"),
            "serial": (d.get("SerialNumber") or "").strip(),
            "temp_c": rel.get("Temperature") or None,
            "wear_pct": rel.get("Wear"),
            "power_on_hours": rel.get("PowerOnHours"),
            "read_errors": rel.get("ReadErrorsTotal"),
            "write_errors": rel.get("WriteErrorsTotal"),
        })

    volumes = []
    for v in as_list(raw.get("volumes")):
        size = v.get("Size") or 0
        free = v.get("SizeRemaining") or 0
        volumes.append({
            "letter": v.get("DriveLetter"),
            "label": v.get("FileSystemLabel") or "",
            "fs": v.get("FileSystem"),
            "size": size,
            "free": free,
            "used": size - free,
            "percent": round((size - free) / size * 100, 1) if size else 0,
        })
    volumes.sort(key=lambda x: x["letter"] or "")

    # Fallback if the Storage module gave us nothing (rare / older systems)
    if not volumes:
        for part in psutil.disk_partitions(all=False):
            try:
                u = psutil.disk_usage(part.mountpoint)
                volumes.append({
                    "letter": (os.path.splitdrive(part.device)[0] or part.device).rstrip(":\\"),
                    "label": "", "fs": part.fstype,
                    "size": u.total, "free": u.free, "used": u.used, "percent": u.percent,
                })
            except Exception:
                continue

    return {"disks": disks, "volumes": volumes, "smart_available": bool(rel_by_id)}


def list_drives():
    drives = []
    for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        if os.path.exists(root):
            drives.append(letter)
    return drives


def analyze_folder(path: str, top: int = 20):
    """Sizes of the immediate children of `path` — a quick 'where did my disk go'.

    Walks each child fully but skips reparse points (junctions/symlinks) to
    avoid loops, and tolerates access-denied entries.
    """
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        return {"ok": False, "error": f"Not a directory: {path}"}

    entries = []
    try:
        children = list(os.scandir(path))
    except PermissionError:
        return {"ok": False, "error": f"Access denied: {path}"}

    for child in children:
        try:
            if child.is_symlink():
                continue
            if child.is_file(follow_symlinks=False):
                entries.append({"name": child.name, "kind": "file",
                                "size": child.stat(follow_symlinks=False).st_size})
            elif child.is_dir(follow_symlinks=False):
                entries.append({"name": child.name, "kind": "dir",
                                "size": _dir_size(child.path)})
        except (PermissionError, OSError):
            continue

    entries.sort(key=lambda e: e["size"], reverse=True)
    total = sum(e["size"] for e in entries)
    return {"ok": True, "path": path, "total": total, "entries": entries[:top],
            "hidden_count": max(0, len(entries) - top)}


def _dir_size(path: str) -> int:
    total = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            continue
    return total


def smart_predict():
    """Trend the scary SMART numbers over time and score each drive's risk."""
    import datetime
    from . import history
    disks = get_storage().get("disks", [])
    out = []
    for d in disks:
        key = (d.get("serial") or d.get("id") or d.get("name") or "").strip()
        if not key or d.get("wear_pct") is None and d.get("read_errors") is None:
            # still show drives, but trending needs reliability counters
            if not key:
                continue
        series = "smart_" + key
        hist = history.read(series)
        cur = {"wear": d.get("wear_pct"), "hours": d.get("power_on_hours"),
               "read_err": d.get("read_errors") or 0, "write_err": d.get("write_errors") or 0,
               "temp": d.get("temp_c")}
        # only record a new point if the last one is > 6h old (don't spam on every open)
        record = True
        if hist:
            try:
                last = datetime.datetime.fromisoformat(hist[-1]["t"])
                record = (datetime.datetime.now() - last).total_seconds() > 6 * 3600
            except (ValueError, KeyError):
                record = True
        if record:
            history.append(series, cur)

        baseline = hist[0] if hist else None
        reasons = []
        risk = 0
        wear = d.get("wear_pct")
        if wear is not None:
            if wear >= 90:
                risk += 3; reasons.append(f"SSD wear at {wear}% of rated endurance")
            elif wear >= 70:
                risk += 1; reasons.append(f"SSD wear at {wear}%")
        if baseline:
            d_read = cur["read_err"] - (baseline.get("read_err") or 0)
            d_write = cur["write_err"] - (baseline.get("write_err") or 0)
            if d_read > 0:
                risk += 2; reasons.append(f"read errors rose by {d_read} since {baseline['t'][:10]}")
            if d_write > 0:
                risk += 2; reasons.append(f"write errors rose by {d_write} since {baseline['t'][:10]}")
        if (d.get("health") or "").lower() not in ("healthy", ""):
            risk += 3; reasons.append(f"drive reports '{d.get('health')}'")
        if d.get("temp_c") and d["temp_c"] >= 60:
            risk += 1; reasons.append(f"running warm ({d['temp_c']}°C)")

        level = "alert" if risk >= 4 else "watch" if risk >= 2 else "ok"
        out.append({
            "name": d.get("name") or key, "media": d.get("media"), "bus": d.get("bus"),
            "size": d.get("size"), "health": d.get("health"),
            "wear_pct": wear, "power_on_hours": d.get("power_on_hours"),
            "temp_c": d.get("temp_c"), "read_errors": cur["read_err"], "write_errors": cur["write_err"],
            "samples": len(hist) + (1 if record else 0),
            "since": baseline["t"][:10] if baseline else None,
            "level": level, "reasons": reasons,
        })
    order = {"alert": 0, "watch": 1, "ok": 2}
    out.sort(key=lambda x: order[x["level"]])
    flags = []
    if any(x["level"] == "alert" for x in out):
        flags.append({"level": "warn", "text": "A drive is showing warning signs — back it up and plan a replacement."})
    elif any(x["level"] == "watch" for x in out):
        flags.append({"level": "info", "text": "A drive is worth keeping an eye on. Benchly trends these over time."})
    else:
        flags.append({"level": "good", "text": "All drives look healthy. Trends build up the more you check."})
    return {"ok": True, "disks": out, "flags": flags}
