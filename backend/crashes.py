"""Crash & BSOD summary — bugchecks, dirty shutdowns, grouped application crashes, minidumps."""

import os
import re

from .ps import ps_json, as_list

# The Stop codes a bench tech actually meets, code → symbolic name. Codes are the
# canonical 32-bit bugcheck numbers (e.g. 0xD1 = DRIVER_IRQL_NOT_LESS_OR_EQUAL).
_BUGCHECKS = {
    0x0000000A: "IRQL_NOT_LESS_OR_EQUAL",
    0x00000018: "REFERENCE_BY_POINTER",
    0x0000001A: "MEMORY_MANAGEMENT",
    0x0000001E: "KMODE_EXCEPTION_NOT_HANDLED",
    0x00000022: "FILE_SYSTEM",
    0x00000024: "NTFS_FILE_SYSTEM",
    0x0000003B: "SYSTEM_SERVICE_EXCEPTION",
    0x00000044: "MULTIPLE_IRP_COMPLETE_REQUESTS",
    0x0000004A: "IRQL_GT_ZERO_AT_SYSTEM_SERVICE",
    0x00000050: "PAGE_FAULT_IN_NONPAGED_AREA",
    0x0000007A: "KERNEL_DATA_INPAGE_ERROR",
    0x0000007B: "INACCESSIBLE_BOOT_DEVICE",
    0x0000007E: "SYSTEM_THREAD_EXCEPTION_NOT_HANDLED",
    0x0000007F: "UNEXPECTED_KERNEL_MODE_TRAP",
    0x0000009F: "DRIVER_POWER_STATE_FAILURE",
    0x000000BE: "ATTEMPTED_WRITE_TO_READONLY_MEMORY",
    0x000000C2: "BAD_POOL_CALLER",
    0x000000C4: "DRIVER_VERIFIER_DETECTED_VIOLATION",
    0x000000C5: "DRIVER_CORRUPTED_EXPOOL",
    0x000000CA: "PNP_DETECTED_FATAL_ERROR",
    0x000000D1: "DRIVER_IRQL_NOT_LESS_OR_EQUAL",
    0x000000E2: "MANUALLY_INITIATED_CRASH",
    0x000000ED: "UNMOUNTABLE_BOOT_VOLUME",
    0x000000EF: "CRITICAL_PROCESS_DIED",
    0x000000F4: "CRITICAL_OBJECT_TERMINATION",
    0x000000F5: "FLTMGR_FILE_SYSTEM",
    0x000000FC: "ATTEMPTED_EXECUTE_OF_NOEXECUTE_MEMORY",
    0x00000109: "CRITICAL_STRUCTURE_CORRUPTION",
    0x0000010E: "VIDEO_MEMORY_MANAGEMENT_INTERNAL",
    0x00000116: "VIDEO_TDR_FAILURE",
    0x00000117: "VIDEO_TDR_TIMEOUT_DETECTED",
    0x00000119: "VIDEO_SCHEDULER_INTERNAL_ERROR",
    0x00000124: "WHEA_UNCORRECTABLE_ERROR",
    0x00000133: "DPC_WATCHDOG_VIOLATION",
    0x00000139: "KERNEL_SECURITY_CHECK_FAILURE",
    0x0000013A: "KERNEL_MODE_HEAP_CORRUPTION",
    0x00000154: "UNEXPECTED_STORE_EXCEPTION",
    0x0000015D: "SOC_SUBSYSTEM_FAILURE",
    0x000001C8: "MISMATCHED_KE_CALLBACK",
}


def _parse_code(raw):
    """A bugcheck code reaches us as a hex string ('0x000000d1 (…)'), a bare hex
    string, or — from Kernel-Power Event 41 — a DECIMAL integer. Normalise to an int."""
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    s = str(raw).strip()
    m = re.search(r"0x([0-9a-fA-F]+)", s)
    if m:
        return int(m.group(1), 16)
    if s.isdigit():            # Event 41 stores BugcheckCode in decimal
        return int(s, 10)
    return None


def _decode_bugcheck(raw):
    """→ {'hex': '0x000000D1', 'name': 'DRIVER_IRQL_NOT_LESS_OR_EQUAL'} or None."""
    code = _parse_code(raw)
    if not code:                                   # 0 or unparseable → not a bugcheck
        return None
    return {"hex": f"0x{code & 0xFFFFFFFF:08X}", "name": _BUGCHECKS.get(code & 0xFFFFFFFF)}


# Properties[] indexes are locale-independent, unlike rendered messages.
# Kernel-Power 41 Properties[0] is BugcheckCode (decimal); >0 means a Stop error
# caused the unclean shutdown, 0 means a power-loss/hard-reset with no bugcheck.
_CRASH_PS = r"""
$o = [ordered]@{}
$start = (Get-Date).AddDays(-90)
$o.bugchecks = Get-WinEvent -FilterHashtable @{ LogName='System'; Id=1001;
        ProviderName='Microsoft-Windows-WER-SystemErrorReporting'; StartTime=$start } -MaxEvents 25 -ErrorAction SilentlyContinue |
    ForEach-Object { [pscustomobject]@{
        Time = $_.TimeCreated.ToString('yyyy-MM-dd HH:mm')
        Code = if ($_.Properties.Count -gt 0) { [string]$_.Properties[0].Value } else { '' }
        Dump = if ($_.Properties.Count -gt 1) { [string]$_.Properties[1].Value } else { '' }
    } }
$kp = Get-WinEvent -FilterHashtable @{ LogName='System'; Id=41;
        ProviderName='Microsoft-Windows-Kernel-Power'; StartTime=$start } -MaxEvents 60 -ErrorAction SilentlyContinue
$o.dirty = ($kp | Measure-Object).Count
$o.kpower = $kp | Select-Object -First 25 | ForEach-Object { [pscustomobject]@{
        Time = $_.TimeCreated.ToString('yyyy-MM-dd HH:mm')
        Bugcheck = if ($_.Properties.Count -gt 0) { [string]$_.Properties[0].Value } else { '0' }
    } }
$o.appcrashes = Get-WinEvent -FilterHashtable @{ LogName='Application'; Id=1000;
        ProviderName='Application Error'; StartTime=$start } -MaxEvents 200 -ErrorAction SilentlyContinue |
    ForEach-Object { [pscustomobject]@{
        Time   = $_.TimeCreated.ToString('yyyy-MM-dd HH:mm')
        App    = if ($_.Properties.Count -gt 0) { [string]$_.Properties[0].Value } else { '?' }
        Module = if ($_.Properties.Count -gt 3) { [string]$_.Properties[3].Value } else { '?' }
    } }
$o
"""


def get_crashes():
    raw = ps_json(_CRASH_PS, timeout=90) or {}

    bugchecks = []
    for b in as_list(raw.get("bugchecks")):
        decoded = _decode_bugcheck(b.get("Code"))
        bugchecks.append({
            "time": b.get("Time"),
            "code": (b.get("Code") or "").strip(),
            "dump": (b.get("Dump") or "").strip(),
            "hex": decoded["hex"] if decoded else "",
            "name": (decoded and decoded["name"]) or "",
        })

    # Kernel-Power 41 events whose BugcheckCode != 0 — an unclean shutdown that a
    # Stop error caused (vs a bare power-loss/hard-reset, which we leave out here).
    kernel_power = []
    for k in as_list(raw.get("kpower")):
        decoded = _decode_bugcheck(k.get("Bugcheck"))
        if decoded:
            kernel_power.append({"time": k.get("Time"), "hex": decoded["hex"],
                                 "name": decoded["name"] or ""})

    # group application crashes by (app, module)
    groups = {}
    for c in as_list(raw.get("appcrashes")):
        key = ((c.get("App") or "?").lower(), (c.get("Module") or "?").lower())
        g = groups.setdefault(key, {"app": c.get("App") or "?", "module": c.get("Module") or "?",
                                    "count": 0, "last": ""})
        g["count"] += 1
        if (c.get("Time") or "") > g["last"]:
            g["last"] = c.get("Time") or ""
    app_crashes = sorted(groups.values(), key=lambda g: g["count"], reverse=True)

    minidumps = []
    dump_dir = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Minidump")
    try:
        if os.path.isdir(dump_dir):
            import datetime
            for f in sorted(os.listdir(dump_dir), reverse=True)[:20]:
                full = os.path.join(dump_dir, f)
                st = os.stat(full)
                minidumps.append({
                    "file": f,
                    "date": datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    "size": st.st_size,
                })
    except OSError:
        pass

    return {
        "days": 90,
        "bugchecks": bugchecks,
        "kernel_power": kernel_power,
        "dirty_shutdowns": raw.get("dirty") or 0,
        "app_crashes": app_crashes,
        "minidumps": minidumps,
        "dump_dir": dump_dir,
    }
