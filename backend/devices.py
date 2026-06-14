"""Problem devices (yellow-bang audit) and printer triage."""

import os
import re
import socket
import subprocess

from .ps import ps_json, as_list, run_ps, CREATE_NO_WINDOW
from . import security

# Device Manager (CM) error codes a bench tech actually meets
_CM_CODES = {
    1: "Not configured correctly",
    3: "Driver corrupted or out of memory",
    9: "Invalid device ID reported by firmware",
    10: "Device cannot start",
    12: "Not enough free resources",
    14: "Restart required",
    18: "Reinstall the drivers",
    19: "Registry configuration damaged",
    21: "Windows is removing the device",
    22: "Device is disabled",
    24: "Device not present or drivers missing",
    28: "Drivers not installed",
    29: "Disabled in firmware / no resources",
    31: "Driver load failed",
    32: "Driver service disabled",
    33: "Resource translation failed",
    34: "Manual configuration required",
    35: "Firmware lacks resource info",
    36: "IRQ translation failed",
    37: "Driver initialisation failed",
    38: "Previous driver instance still in memory",
    39: "Driver corrupted or missing",
    40: "Service registry information invalid",
    41: "Driver loaded but device not found",
    42: "Duplicate device detected",
    43: "Device reported a failure",
    44: "Shut down by an application or service",
    45: "Device not connected",
    46: "Device not available during shutdown",
    47: "Safe-removal pending — unplug and replug",
    48: "Driver blocked (known incompatibility)",
    49: "Registry hive too large",
    52: "Driver signature problem",
}

_DEVICES_PS = r"""
$all = Get-CimInstance Win32_PnPEntity
$o = [ordered]@{}
$o.problems = $all | Where-Object { $_.ConfigManagerErrorCode -ne 0 } |
    Select-Object Name,DeviceID,ConfigManagerErrorCode,PNPClass
$o.total = ($all | Measure-Object).Count
$o
"""


def get_problem_devices():
    raw = ps_json(_DEVICES_PS, timeout=60) or {}
    problems = []
    for d in as_list(raw.get("problems")):
        code = d.get("ConfigManagerErrorCode")
        problems.append({
            "name": d.get("Name") or "(unnamed device)",
            "device_id": d.get("DeviceID") or "",
            "class": d.get("PNPClass") or "—",
            "code": code,
            "meaning": _CM_CODES.get(code, f"CM error {code}"),
        })
    problems.sort(key=lambda x: (x["class"], x["name"]))
    return {"problems": problems, "total_devices": raw.get("total")}


_PRINTERS_PS = r"""
$o = [ordered]@{}
$o.printers = Get-CimInstance Win32_Printer |
    Select-Object Name,Default,PrinterStatus,WorkOffline,PortName,DriverName
$o.jobs = Get-CimInstance Win32_PrintJob |
    Select-Object Name,Document,Owner,JobStatus,TotalPages,@{n='Submitted';e={$_.TimeSubmitted.ToString('yyyy-MM-dd HH:mm')}}
$o.spooler = [string](Get-Service -Name Spooler -ErrorAction SilentlyContinue).Status
$o
"""

_PRINTER_STATUS = {1: "Other", 2: "Unknown", 3: "Idle", 4: "Printing", 5: "Warming up",
                   6: "Stopped printing", 7: "Offline"}


def get_printers():
    raw = ps_json(_PRINTERS_PS, timeout=45) or {}
    printers = []
    for p in as_list(raw.get("printers")):
        printers.append({
            "name": p.get("Name"),
            "default": bool(p.get("Default")),
            "status": _PRINTER_STATUS.get(p.get("PrinterStatus"), "Unknown"),
            "offline": bool(p.get("WorkOffline")),
            "port": p.get("PortName"),
            "driver": p.get("DriverName"),
        })
    printers.sort(key=lambda x: (not x["default"], (x["name"] or "").lower()))
    jobs = []
    for j in as_list(raw.get("jobs")):
        name = j.get("Name") or ""
        jobs.append({
            "printer": name.split(",")[0],
            "document": j.get("Document") or "—",
            "owner": j.get("Owner") or "",
            "status": j.get("JobStatus") or "",
            "pages": j.get("TotalPages"),
            "submitted": j.get("Submitted"),
        })
    return {"printers": printers, "jobs": jobs, "spooler": raw.get("spooler") or "Unknown"}


def purge_print_queue():
    """Stop the spooler, delete stuck jobs, restart. Needs elevation."""
    if not security.is_admin():
        return {"ok": False, "error": "Purging the queue needs elevation — use Run as admin."}
    spool_dir = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "spool", "PRINTERS")
    steps = []
    try:
        r = subprocess.run(["net", "stop", "spooler"], capture_output=True, timeout=60,
                           creationflags=CREATE_NO_WINDOW)
        steps.append(f"net stop spooler → rc {r.returncode}")
        removed = 0
        if os.path.isdir(spool_dir):
            for f in os.listdir(spool_dir):
                try:
                    os.remove(os.path.join(spool_dir, f))
                    removed += 1
                except OSError:
                    pass
        steps.append(f"removed {removed} spool file(s)")
        r = subprocess.run(["net", "start", "spooler"], capture_output=True, timeout=60,
                           creationflags=CREATE_NO_WINDOW)
        steps.append(f"net start spooler → rc {r.returncode}")
        return {"ok": True, "detail": "; ".join(steps)}
    except Exception as e:
        return {"ok": False, "error": f"{e} ({'; '.join(steps)})"}


# --------------------------------------------------------------------------- #
# printer doctor — the "it says offline but it's right there" diagnosis
# --------------------------------------------------------------------------- #
_PRINTER_DOCTOR_PS = r"""
$o = [ordered]@{}
$o.printers = Get-CimInstance Win32_Printer |
    Select-Object Name,Default,PrinterStatus,WorkOffline,PortName,DriverName
$o.ports = Get-PrinterPort -ErrorAction SilentlyContinue |
    Select-Object Name,PrinterHostAddress,Description
$o.drivers = Get-PrinterDriver -ErrorAction SilentlyContinue | Select-Object Name
$o.jobs = @(Get-CimInstance Win32_PrintJob).Count
$o.spooler = [string](Get-Service -Name Spooler -ErrorAction SilentlyContinue).Status
$o
"""

_IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def _reachable(host, ports=(9100, 631, 515), timeout=1.2):
    for port in ports:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def printer_doctor():
    raw = ps_json(_PRINTER_DOCTOR_PS, timeout=45) or {}
    port_addr = {}
    for p in as_list(raw.get("ports")):
        host = p.get("PrinterHostAddress") or ""
        if host:
            port_addr[p.get("Name")] = host
    # driver name → count, to spot duplicate/conflicting drivers
    drv_counts = {}
    for d in as_list(raw.get("drivers")):
        base = re.sub(r"\s+(class\s+)?driver$|\s+v?\d+(\.\d+)*$", "", (d.get("Name") or ""), flags=re.I).strip()
        drv_counts[base] = drv_counts.get(base, 0) + 1

    printers = []
    flags = []
    for p in as_list(raw.get("printers")):
        name = p.get("Name") or ""
        port = p.get("PortName") or ""
        offline_flag = bool(p.get("WorkOffline"))
        status = _PRINTER_STATUS.get(p.get("PrinterStatus"), "Unknown")
        host = port_addr.get(port) or (port if _IP_RE.match(port) else None)
        issues = []
        reachable = None
        if offline_flag:
            issues.append("“Use Printer Offline” is ticked")
        if host:
            reachable = _reachable(host)
            if not reachable:
                issues.append(f"can't reach {host} — the printer may be off, or DHCP gave it a new IP")
        base = re.sub(r"\s+(class\s+)?driver$|\s+v?\d+(\.\d+)*$", "", (p.get("DriverName") or ""), flags=re.I).strip()
        if drv_counts.get(base, 0) > 1:
            issues.append("more than one version of this driver is installed")
        printers.append({
            "name": name, "default": bool(p.get("Default")), "status": status,
            "offline": offline_flag, "port": port, "host": host,
            "reachable": reachable, "driver": p.get("DriverName"), "issues": issues,
        })

    jobs = raw.get("jobs") or 0
    spooler = raw.get("spooler") or "Unknown"
    if spooler != "Running":
        flags.append({"level": "warn", "text": f"The Print Spooler service is {spooler}."})
    if jobs:
        flags.append({"level": "info", "text": f"{jobs} job(s) are sitting in the queue."})
    if not any(p["issues"] for p in printers) and spooler == "Running" and not flags:
        flags.append({"level": "good", "text": "Printers look healthy."})
    return {"ok": True, "printers": printers, "jobs": jobs, "spooler": spooler, "flags": flags}


def printer_clear_offline(name):
    """Untick 'Use Printer Offline' and nudge the spooler so it comes back online."""
    if not re.match(r"^[\w .,\-()#&]+$", str(name or "")):
        return {"ok": False, "error": "Invalid printer name."}
    safe = name.replace("'", "''")
    out = run_ps("& { $p = Get-CimInstance Win32_Printer -Filter \"Name='" + safe + "'\" -ErrorAction SilentlyContinue; "
                 "if ($p) { $p | Invoke-CimMethod -MethodName Resume -ErrorAction SilentlyContinue | Out-Null; "
                 "$p | Set-CimInstance -Property @{WorkOffline=$false} -ErrorAction SilentlyContinue; 'OK' } else { 'NF' } }",
                 timeout=30)
    if "OK" in out:
        return {"ok": True, "where": f"Win32_Printer '{name}': WorkOffline → false + Resume"}
    return {"ok": False, "error": "Printer not found, or Windows wouldn't clear the flag (try restarting the spooler)."}


def printer_testpage(name):
    if not re.match(r"^[\w .,\-()#&]+$", str(name or "")):
        return {"ok": False, "error": "Invalid printer name."}
    safe = name.replace("'", "''")
    out = run_ps("& { $p = Get-CimInstance Win32_Printer -Filter \"Name='" + safe + "'\" -ErrorAction SilentlyContinue; "
                 "if ($p) { $r = $p | Invoke-CimMethod -MethodName PrintTestPage; \"RC:$($r.ReturnValue)\" } else { 'NF' } }",
                 timeout=30)
    if "RC:0" in out:
        return {"ok": True, "message": "Test page sent."}
    return {"ok": False, "error": "Couldn't send a test page (printer not found or offline)."}
