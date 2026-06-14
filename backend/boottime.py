"""Boot-time breakdown — 'why does it take four minutes to get to the desktop?'

Windows already times every boot in the Diagnostics-Performance log and even names
the specific apps, drivers and services that dragged it out. This reads that, charts
the trend over time, and reports Fast Startup state and uptime. Read-only (needs admin
to read the Diagnostics-Performance log).
"""

import winreg

from .ps import ps_json, as_list, run_ps
from . import security, history

HKLM = winreg.HKEY_LOCAL_MACHINE

_LOG = "Microsoft-Windows-Diagnostics-Performance/Operational"
# Degradation event IDs → the kind of thing that was slow.
_DEGRADE = {101: "App", 102: "Driver", 103: "Service", 106: "Background task",
            109: "Device", 110: "Driver"}


def _fast_startup():
    try:
        k = winreg.OpenKey(HKLM, r"SYSTEM\CurrentControlSet\Control\Session Manager\Power")
        try:
            v, _ = winreg.QueryValueEx(k, "HiberbootEnabled")
            return bool(v)
        finally:
            winreg.CloseKey(k)
    except OSError:
        return None


def _ms_to_s(value):
    try:
        return round(int(value) / 1000, 1)
    except (TypeError, ValueError):
        return None


def boot_performance(history_limit=20):
    admin = security.is_admin()

    # Uptime + last boot (works without admin).
    base = ps_json(
        "$os = Get-CimInstance Win32_OperatingSystem; [pscustomobject]@{ "
        "LastBoot=$os.LastBootUpTime.ToString('yyyy-MM-dd HH:mm'); "
        "UptimeHours=[math]::Round(((Get-Date) - $os.LastBootUpTime).TotalHours,1) }",
        timeout=20) or {}

    result = {
        "ok": True, "is_admin": admin,
        "fast_startup": _fast_startup(),
        "last_boot": base.get("LastBoot"),
        "uptime_hours": base.get("UptimeHours"),
        "boots": [], "degraders": [], "trend": [],
    }

    if not admin:
        result["needs_admin"] = True
        result["note"] = ("Reading the boot-performance log needs admin — use Run as admin "
                          "for the full breakdown. Uptime and Fast Startup are shown above.")
        return result

    # Event 100 = per-boot timing. Pull recent boots and parse the XML payload.
    boots_cmd = (
        f"Get-WinEvent -FilterHashtable @{{ LogName='{_LOG}'; Id=100 }} -MaxEvents {int(history_limit)} "
        "-ErrorAction SilentlyContinue | ForEach-Object { $x=[xml]$_.ToXml(); $d=@{}; "
        "foreach ($n in $x.Event.EventData.Data) { $d[$n.Name]=$n.'#text' }; "
        "[pscustomobject]@{ Time=$_.TimeCreated.ToString('yyyy-MM-dd HH:mm'); "
        "BootDuration=$d['BootDuration']; MainPath=$d['MainPathBootTime']; "
        "PostBoot=$d['BootPostBootTime']; Degradation=$d['BootIsDegradation'] } }"
    )
    for b in as_list(ps_json(boots_cmd, timeout=45, depth=3)):
        if isinstance(b, dict):
            result["boots"].append({
                "time": b.get("Time"),
                "total_s": _ms_to_s(b.get("BootDuration")),
                "to_desktop_s": _ms_to_s(b.get("MainPath")),
                "post_boot_s": _ms_to_s(b.get("PostBoot")),
                "degraded": str(b.get("Degradation")) in ("1", "True", "true"),
            })

    # Events 101/102/103/… = the specific slow apps/drivers/services.
    ids = ",".join(str(i) for i in _DEGRADE)
    slow_cmd = (
        f"Get-WinEvent -FilterHashtable @{{ LogName='{_LOG}'; Id={ids} }} -MaxEvents 60 "
        "-ErrorAction SilentlyContinue | ForEach-Object { $x=[xml]$_.ToXml(); $d=@{}; "
        "foreach ($n in $x.Event.EventData.Data) { $d[$n.Name]=$n.'#text' }; "
        "[pscustomobject]@{ Id=$_.Id; Time=$_.TimeCreated.ToString('yyyy-MM-dd HH:mm'); "
        "Name=$d['Name']; Friendly=$d['FriendlyName']; TotalTime=$d['TotalTime'] } }"
    )
    seen = set()
    for s in as_list(ps_json(slow_cmd, timeout=45, depth=3)):
        if not isinstance(s, dict):
            continue
        name = (s.get("Friendly") or s.get("Name") or "").strip()
        secs = _ms_to_s(s.get("TotalTime"))
        if not name or secs is None:
            continue
        key = (s.get("Id"), name.lower())
        if key in seen:
            continue
        seen.add(key)
        result["degraders"].append({
            "kind": _DEGRADE.get(s.get("Id"), "Other"),
            "name": name, "seconds": secs, "time": s.get("Time"),
        })
    # Worst offenders first.
    result["degraders"].sort(key=lambda d: d["seconds"], reverse=True)
    result["degraders"] = result["degraders"][:15]

    # Trend: log the most recent boot's total time, then hand back the series.
    if result["boots"] and result["boots"][0].get("total_s"):
        history.append("boot", {"total_s": result["boots"][0]["total_s"]})
    result["trend"] = history.read("boot", limit=60)

    return result
