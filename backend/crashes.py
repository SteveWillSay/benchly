"""Crash & BSOD summary — bugchecks, dirty shutdowns, grouped application crashes, minidumps."""

import os

from .ps import ps_json, as_list

# Properties[] indexes are locale-independent, unlike rendered messages.
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
$o.dirty = (Get-WinEvent -FilterHashtable @{ LogName='System'; Id=41;
        ProviderName='Microsoft-Windows-Kernel-Power'; StartTime=$start } -ErrorAction SilentlyContinue | Measure-Object).Count
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

    bugchecks = [{
        "time": b.get("Time"),
        "code": (b.get("Code") or "").strip(),
        "dump": (b.get("Dump") or "").strip(),
    } for b in as_list(raw.get("bugchecks"))]

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
        "dirty_shutdowns": raw.get("dirty") or 0,
        "app_crashes": app_crashes,
        "minidumps": minidumps,
        "dump_dir": dump_dir,
    }
