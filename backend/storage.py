"""Physical disk health (SMART), volumes, and a quick folder-size analyzer."""

import os
import string
import threading

import psutil

from .ps import ps_json, as_list, run_ps

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


# File-type categories — mirrors the UI's EXT_CATS so a folder can be tinted by the type
# of content that dominates it (the treemap's dominant-type colouring). Keys match the UI.
_EXT_CATEGORY = {}
for _cat, _exts in {
    "images": "jpg jpeg png gif bmp webp svg ico heic tif tiff raw psd",
    "video": "mp4 mkv avi mov wmv flv webm m4v mpg mpeg",
    "audio": "mp3 wav flac aac ogg m4a wma aiff",
    "documents": "pdf doc docx xls xlsx ppt pptx txt rtf csv md epub",
    "archives": "zip 7z rar tar gz bz2 xz iso cab msi",
    "code": "js ts py c cpp cs java go rs html css json xml sql sh ps1 bat yml yaml",
    "binaries": "exe dll sys bin dmp vhd vhdx dat db pak",
}.items():
    for _e in _exts.split():
        _EXT_CATEGORY[_e] = _cat


def _category(name: str) -> str:
    return _EXT_CATEGORY.get(os.path.splitext(name)[1].lower().lstrip("."), "other")


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
                                "size": child.stat(follow_symlinks=False).st_size,
                                "dominant": _category(child.name)})
            elif child.is_dir(follow_symlinks=False):
                size, cats = _dir_scan(child.path)
                dominant = max(cats, key=cats.get) if cats else None
                entries.append({"name": child.name, "kind": "dir",
                                "size": size, "dominant": dominant})
        except (PermissionError, OSError):
            continue

    entries.sort(key=lambda e: e["size"], reverse=True)
    total = sum(e["size"] for e in entries)
    return {"ok": True, "path": path, "total": total, "entries": entries[:top],
            "hidden_count": max(0, len(entries) - top)}


def folder_types(path: str, top: int = 14):
    """Aggregate file sizes by extension under `path` (one walk) — 'what type is eating
    the space'. Skips reparse points; tolerates access-denied. Read-only."""
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        return {"ok": False, "error": f"Not a directory: {path}"}

    buckets = {}   # ext -> [size, count]
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
                            sz = entry.stat(follow_symlinks=False).st_size
                            ext = (os.path.splitext(entry.name)[1].lower() or "(no ext)")
                            b = buckets.setdefault(ext, [0, 0])
                            b[0] += sz
                            b[1] += 1
                            total += sz
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            continue

    items = sorted(({"ext": e, "size": v[0], "count": v[1]} for e, v in buckets.items()),
                   key=lambda x: x["size"], reverse=True)
    other = sum(x["size"] for x in items[top:])
    other_count = sum(x["count"] for x in items[top:])
    return {"ok": True, "path": path, "total": total, "types": items[:top],
            "other": other, "other_count": other_count}


def _dir_scan(path: str):
    """Total bytes under `path` plus a per-category byte breakdown, in one walk.
    Skips reparse points; tolerates access-denied. Returns (total, {category: bytes})."""
    total = 0
    cats = {}
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
                            sz = entry.stat(follow_symlinks=False).st_size
                            total += sz
                            cat = _category(entry.name)
                            cats[cat] = cats.get(cat, 0) + sz
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            continue
    return total, cats


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


# --------------------------------------------------------------------------- #
# Raw vendor SMART attribute table (MSStorageDriver_FailurePredictData)
# --------------------------------------------------------------------------- #
# Well-known SMART attribute IDs → human names. This is the raw vendor table
# (read-only), complementing get_storage()/smart_predict() which trend the
# normalised reliability counters. We never write to the drive — we only decode
# the 512-byte VendorSpecific blob the driver already exposes.
_SMART_NAMES = {
    1: "Read Error Rate",
    5: "Reallocated Sectors Count",
    9: "Power-On Hours",
    10: "Spin Retry Count",
    12: "Power Cycle Count",
    184: "End-to-End Error",
    187: "Reported Uncorrectable Errors",
    188: "Command Timeout",
    190: "Temperature (airflow)",
    194: "Temperature",
    196: "Reallocation Event Count",
    197: "Current Pending Sector Count",
    198: "Offline Uncorrectable",
    199: "UltraDMA CRC Error Count",
    231: "SSD Life Left",
    233: "Media Wearout / SSD Life",
}

# The "predictive failure" attributes — any non-zero raw value is worth a flag.
_SMART_CONCERN_IDS = {5, 187, 197, 198, 199}


def _smart_to_bytes(value):
    """Normalise a VendorSpecific blob (JSON int array / list) → list of 0-255.

    PowerShell's ConvertTo-Json renders the byte[] as an int array; a single
    element collapses to a scalar. Return [] for anything we can't make sense
    of, so the caller degrades instead of raising.
    """
    items = as_list(value)
    out = []
    for n in items:
        try:
            b = int(n)
        except (TypeError, ValueError):
            return []
        out.append(b & 0xFF)
    return out


def _parse_smart_table(blob):
    """Decode the 512-byte VendorSpecific attribute table → list of attr dicts.

    Layout: attributes start at byte offset 2; each is a 12-byte record of
    [id(1), flags(2 LE), current(1), worst(1), raw(6 LE), reserved(1)].
    Stop at id==0 or when the buffer runs out. Only known ids are emitted.
    """
    attrs = []
    i = 2
    n = len(blob)
    while i + 12 <= n:
        attr_id = blob[i]
        if attr_id == 0:
            break
        name = _SMART_NAMES.get(attr_id)
        if name:
            current = blob[i + 3]
            worst = blob[i + 4]
            raw = 0
            for k in range(6):  # 6 raw bytes, little-endian
                raw |= blob[i + 5 + k] << (8 * k)
            concern = attr_id in _SMART_CONCERN_IDS and raw > 0
            attrs.append({
                "id": attr_id, "name": name,
                "current": current, "worst": worst,
                "raw": raw, "concern": concern,
            })
        i += 12
    return attrs


def smart_attributes():
    """Per-physical-disk decoded raw SMART attributes (read-only).

    Reads MSStorageDriver_FailurePredictData from root\\wmi and decodes the
    512-byte VendorSpecific blob into named attributes. This class typically
    needs admin and only ATA/SATA drives expose it — NVMe usually does not.
    When a disk has no data we mark available=False with a reason rather than
    raising; supported=False only when nothing at all is available.

    Returns:
        {"disks": [{"disk": str, "available": bool, "attributes": [...],
                    "reason"?: str}],
         "supported": bool, "note": str}
    """
    # Physical disks first, so we can label predict-data by its PNP/InstanceName.
    physical = as_list(ps_json(
        "Get-CimInstance -ClassName Win32_DiskDrive -ErrorAction SilentlyContinue | "
        "Select-Object Index,Model,PNPDeviceID,InterfaceType", timeout=30))

    # The failure-predict table (per ATA/SATA instance). NVMe drives are absent.
    predict = as_list(ps_json(
        "Get-CimInstance -Namespace root/wmi -ClassName MSStorageDriver_FailurePredictData "
        "-ErrorAction SilentlyContinue | Select-Object InstanceName,VendorSpecific",
        timeout=30, depth=3))

    # Index predict rows by a normalised InstanceName (PNP id + "_0" suffix).
    def _norm(s):
        return (s or "").strip().upper().replace("\\", "#")

    pred_by_inst = {}
    for p in predict:
        if isinstance(p, dict) and p.get("InstanceName"):
            pred_by_inst[_norm(p["InstanceName"])] = p

    def _match(pnp):
        """Find the predict row whose InstanceName embeds this PNPDeviceID."""
        key = _norm(pnp)
        if not key:
            return None
        for inst, row in pred_by_inst.items():
            # InstanceName is usually "<PNPDeviceID>_0"; match either direction.
            if key and (key in inst or inst.rstrip("_0").endswith(key)):
                return row
        return None

    disks = []
    any_available = False
    matched = set()

    for d in physical:
        if not isinstance(d, dict):
            continue
        label = (d.get("Model") or "").strip()
        if not label:
            idx = d.get("Index")
            label = f"Disk {idx}" if idx is not None else "Unknown disk"
        iface = (d.get("InterfaceType") or "").strip()

        row = _match(d.get("PNPDeviceID"))
        if row is None:
            reason = "no SMART predict data (NVMe or needs admin)" if \
                iface.upper() == "SCSI" or not iface else "no SMART predict data for this disk"
            disks.append({"disk": label, "available": False, "attributes": [],
                          "reason": reason})
            continue

        matched.add(id(row))
        blob = _smart_to_bytes(row.get("VendorSpecific"))
        attrs = _parse_smart_table(blob) if blob else []
        if attrs:
            any_available = True
            disks.append({"disk": label, "available": True, "attributes": attrs})
        else:
            disks.append({"disk": label, "available": False, "attributes": [],
                          "reason": "predict data present but no decodable attributes"})

    # Predict rows we couldn't tie to a Win32_DiskDrive — still surface them.
    for p in predict:
        if not isinstance(p, dict) or id(p) in matched:
            continue
        label = (p.get("InstanceName") or "Unknown disk").split("\\")[-1]
        blob = _smart_to_bytes(p.get("VendorSpecific"))
        attrs = _parse_smart_table(blob) if blob else []
        if attrs:
            any_available = True
            disks.append({"disk": label, "available": True, "attributes": attrs})
        else:
            disks.append({"disk": label, "available": False, "attributes": [],
                          "reason": "predict data present but no decodable attributes"})

    supported = any_available
    if supported:
        note = "Raw vendor SMART attributes decoded from the storage driver (read-only)."
    elif predict:
        note = "SMART predict data found but no attributes could be decoded."
    else:
        note = ("No SMART attribute data exposed — typically requires admin and "
                "an ATA/SATA drive (NVMe drives don't provide this table).")
    return {"disks": disks, "supported": supported, "note": note}


# --------------------------------------------------------------------------- #
# Deep storage health (H2): TRIM, Storage Spaces, reliability counters, VSS
# --------------------------------------------------------------------------- #
def storage_deep():
    from . import security
    admin = security.is_admin()

    # TRIM (SSD): DisableDeleteNotify 0 = enabled.
    trim_out = run_ps("fsutil behavior query DisableDeleteNotify 2>&1", timeout=15) or ""
    trim = None
    import re as _re
    m = _re.search(r"NTFS\s+DisableDeleteNotify\s*=\s*(\d)", trim_out) or \
        _re.search(r"DisableDeleteNotify\s*=\s*(\d)", trim_out)
    if m:
        trim = (m.group(1) == "0")

    # Storage Spaces (non-primordial pools + virtual disks).
    pools = as_list(ps_json(
        "Get-StoragePool -ErrorAction SilentlyContinue | Where-Object { -not $_.IsPrimordial } | "
        "Select-Object FriendlyName,@{n='Health';e={[string]$_.HealthStatus}},"
        "@{n='Size';e={[math]::Round($_.Size/1GB)}}", timeout=25))
    vdisks = as_list(ps_json(
        "Get-VirtualDisk -ErrorAction SilentlyContinue | Select-Object FriendlyName,"
        "@{n='Health';e={[string]$_.HealthStatus}},@{n='Resiliency';e={[string]$_.ResiliencySettingName}}",
        timeout=25))

    # Reliability counters (richer than basic SMART; some fields want admin).
    rel = as_list(ps_json(
        "Get-PhysicalDisk -ErrorAction SilentlyContinue | ForEach-Object { "
        "$r = $_ | Get-StorageReliabilityCounter -ErrorAction SilentlyContinue; "
        "[pscustomobject]@{ Name=$_.FriendlyName; Wear=$r.Wear; Temp=$r.Temperature; "
        "ReadErr=$r.ReadErrorsTotal; WriteErr=$r.WriteErrorsTotal } }", timeout=30, depth=3))
    reliability = []
    for r in rel:
        if isinstance(r, dict) and r.get("Name"):
            reliability.append({"name": r.get("Name"), "wear": r.get("Wear"),
                                "temp": r.get("Temp"), "read_err": r.get("ReadErr"),
                                "write_err": r.get("WriteErr")})

    # VSS shadow-copy storage (restore-point space) — needs admin.
    vss = []
    if admin:
        vtext = run_ps("vssadmin list shadowstorage 2>&1", timeout=20) or ""
        cur = {}
        for line in vtext.splitlines():
            s = line.strip()
            if s.lower().startswith("for volume"):
                if cur:
                    vss.append(cur)
                mm = _re.search(r"\(([A-Z]:)\)", s)
                cur = {"volume": mm.group(1) if mm else s}
            elif "used shadow copy storage space" in s.lower():
                cur["used"] = s.split(":", 1)[1].strip()
            elif "allocated shadow copy storage space" in s.lower():
                cur["allocated"] = s.split(":", 1)[1].strip()
            elif "maximum shadow copy storage space" in s.lower():
                cur["max"] = s.split(":", 1)[1].strip()
        if cur:
            vss.append(cur)

    # Filesystem dirty bit on C: (set = chkdsk wanted at next boot).
    dirty_out = run_ps("fsutil dirty query C: 2>&1", timeout=15) or ""
    c_dirty = "is dirty" in dirty_out.lower()

    return {
        "ok": True, "is_admin": admin,
        "trim_enabled": trim,
        "pools": [p for p in pools if isinstance(p, dict)],
        "vdisks": [v for v in vdisks if isinstance(v, dict)],
        "reliability": reliability,
        "vss": vss, "vss_needs_admin": not admin,
        "c_dirty": c_dirty,
    }
