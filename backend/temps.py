"""Live sensors — honest tiering.

NVIDIA GPUs report via nvidia-smi (free, fast). Disk temps come from the SMART
reliability counters (admin). ACPI thermal zones are best-effort (admin, often
one coarse zone). CPU core temps genuinely need a kernel driver on Windows —
if LibreHardwareMonitor's web server is running we read it, otherwise we say so
rather than pretend.
"""

import json
import os
import subprocess
import time
import urllib.request

from .ps import ps_json, as_list, CREATE_NO_WINDOW
from . import storage

_nvidia_smi = None
_acpi_cache = {"t": 0, "zones": []}


def _find_nvidia_smi():
    global _nvidia_smi
    if _nvidia_smi is not None:
        return _nvidia_smi
    candidates = [
        os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "nvidia-smi.exe"),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                     "NVIDIA Corporation", "NVSMI", "nvidia-smi.exe"),
        "nvidia-smi",
    ]
    for c in candidates:
        try:
            subprocess.run([c, "-L"], capture_output=True, timeout=10,
                           creationflags=CREATE_NO_WINDOW)
            _nvidia_smi = c
            return c
        except (OSError, subprocess.TimeoutExpired):
            continue
    _nvidia_smi = ""
    return ""


def _nvidia_gpus():
    smi = _find_nvidia_smi()
    if not smi:
        return []
    try:
        out = subprocess.run(
            [smi, "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw",
             "--format=csv,noheader,nounits"],
            capture_output=True, timeout=10, creationflags=CREATE_NO_WINDOW,
        ).stdout.decode("ascii", "replace")
        gpus = []
        for line in out.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 5:
                continue
            def num(v):
                try:
                    return float(v)
                except ValueError:
                    return None
            gpus.append({
                "name": parts[0],
                "temp_c": num(parts[1]),
                "util_pct": num(parts[2]),
                "vram_used_mb": num(parts[3]),
                "vram_total_mb": num(parts[4]),
                "power_w": num(parts[5]) if len(parts) > 5 else None,
            })
        return gpus
    except (OSError, subprocess.TimeoutExpired):
        return []


def gpu_forensics():
    """GPU clocks, throttle reasons, and a TDR/driver-reset history — the "is my OC stable" view."""
    smi = _find_nvidia_smi()
    gpus = []
    if smi:
        try:
            fields = ("name,temperature.gpu,clocks.gr,clocks.max.gr,power.draw,power.limit,"
                      "clocks_throttle_reasons.sw_power_cap,clocks_throttle_reasons.hw_thermal_slowdown,"
                      "clocks_throttle_reasons.sw_thermal_slowdown,clocks_throttle_reasons.hw_power_brake_slowdown")
            out = subprocess.run([smi, f"--query-gpu={fields}", "--format=csv,noheader,nounits"],
                                 capture_output=True, timeout=10,
                                 creationflags=CREATE_NO_WINDOW).stdout.decode("ascii", "replace")
            for line in out.strip().splitlines():
                p = [x.strip() for x in line.split(",")]
                if len(p) < 10:
                    continue
                def n(v):
                    try:
                        return float(v)
                    except ValueError:
                        return None
                active = lambda v: v.lower() == "active"
                reasons = []
                if active(p[6]):
                    reasons.append("power limit")
                if active(p[7]) or active(p[8]):
                    reasons.append("thermal")
                if active(p[9]):
                    reasons.append("power brake")
                gpus.append({"name": p[0], "temp_c": n(p[1]), "clock_mhz": n(p[2]),
                             "max_clock_mhz": n(p[3]), "power_w": n(p[4]), "power_limit_w": n(p[5]),
                             "throttle": reasons})
        except (OSError, subprocess.TimeoutExpired):
            pass

    # GPU driver-reset / TDR history (Display log, event 4101)
    tdr = as_list(ps_json(
        "Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Display'; Id=4101; "
        "StartTime=(Get-Date).AddDays(-30)} -MaxEvents 50 -ErrorAction SilentlyContinue | "
        "Select-Object @{n='Time';e={$_.TimeCreated.ToString('yyyy-MM-dd HH:mm')}}", timeout=30))
    tdr_times = [t.get("Time") for t in tdr if t.get("Time")]

    flags = []
    if not smi:
        flags.append({"level": "info", "text": "No NVIDIA GPU detected (nvidia-smi not found)."})
    else:
        for g in gpus:
            if g["throttle"]:
                flags.append({"level": "info", "text": f"{g['name']} is throttling ({', '.join(g['throttle'])}) right now."})
    if tdr_times:
        flags.append({"level": "warn", "text": f"{len(tdr_times)} GPU driver reset(s) (TDR / Event 4101) in the last 30 days — a sign of an unstable overclock, a marginal PSU, or a driver issue."})
    elif smi:
        flags.append({"level": "good", "text": "No GPU driver resets in the last 30 days."})
    return {"ok": True, "available": bool(smi), "gpus": gpus,
            "tdr_count": len(tdr_times), "tdr_times": tdr_times[:20], "flags": flags}


def _acpi_zones():
    """Best-effort ACPI thermal zones — cached for 60 s (each read spawns PS)."""
    now = time.monotonic()
    if now - _acpi_cache["t"] < 60:
        return _acpi_cache["zones"]
    rows = as_list(ps_json(
        "Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature "
        "-ErrorAction SilentlyContinue | Select-Object InstanceName,CurrentTemperature", timeout=20))
    zones = []
    for r in rows:
        raw = r.get("CurrentTemperature")
        if raw:
            zones.append({
                "name": (r.get("InstanceName") or "Zone").split("\\")[-1],
                "temp_c": round(raw / 10 - 273.15, 1),
            })
    _acpi_cache.update(t=now, zones=zones)
    return zones


def _lhm_cpu():
    """LibreHardwareMonitor bridge — only if the tech already runs its web server."""
    try:
        with urllib.request.urlopen("http://localhost:8085/data.json", timeout=1.0) as resp:
            tree = json.loads(resp.read().decode())
    except Exception:
        return None

    found = []

    def walk(node, in_cpu=False):
        text = node.get("Text", "")
        is_cpu = in_cpu or "cpu" in text.lower()
        if node.get("Type") == "Temperature" and in_cpu and "package" in text.lower():
            try:
                found.append(float(str(node.get("Value", "")).split()[0].replace(",", ".")))
            except (ValueError, IndexError):
                pass
        for child in node.get("Children", []):
            walk(child, is_cpu)

    walk(tree)
    return found[0] if found else None


def get_sensors():
    disks = [{"name": d["name"], "temp_c": d["temp_c"]}
             for d in storage.get_storage()["disks"] if d.get("temp_c")]
    return {
        "gpus": _nvidia_gpus(),
        "disks": disks,
        "acpi": _acpi_zones(),
        "cpu_lhm": _lhm_cpu(),
    }
