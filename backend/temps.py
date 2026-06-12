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
