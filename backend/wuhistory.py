"""Windows Update history & error decoder — 'why is it stuck?'

Resetting the WU cache (Toolbox) treats the symptom; this shows the cause. It reads
the real update history through the Microsoft.Update.Session COM searcher, decodes
the cryptic 0x800f… / 0x80070… result codes into plain English, reports the last
successful scan/install, and checks the health of the services WU depends on.
All read-only.
"""

from .ps import ps_json, as_list, run_ps

# Common Windows Update HRESULTs → what they actually mean / what to do.
_HRESULT = {
    0x00000000: ("Succeeded", ""),
    0x80240034: ("Update failed to download",
                 "The download didn't complete — usually flaky connectivity or a metered link. Retry."),
    0x8024200D: ("Update must be downloaded again",
                 "The cached copy was incomplete. Resetting the WU cache (Toolbox) and retrying usually clears it."),
    0x80070020: ("A file was in use (sharing violation)",
                 "Another process was holding a file the update needed. A restart, then retry, normally fixes it."),
    0x800F0922: ("Install failed — often a too-small System Reserved partition or a .NET issue",
                 "Common on feature updates. Check free space and the System Reserved partition; SFC/DISM can help."),
    0x80073712: ("Component store is corrupt",
                 "A servicing file is missing/damaged. Run DISM /RestoreHealth then SFC (both in Toolbox), then retry."),
    0x80070BC9: ("A prior operation needs a restart first",
                 "An earlier update is mid-install. Restart to finish it (see the pending-reboot check), then retry."),
    0x80070643: ("Install error (MSI/.NET)",
                 "Frequently a .NET or security-update install fault. Repairing .NET or running the update standalone helps."),
    0x800705B4: ("Timed out", "The operation ran out of time — usually a slow/blocked connection to the update server."),
    0x8024401C: ("Timed out reaching the update server",
                 "WSUS/Windows Update didn't respond. Check connectivity or the WSUS server."),
    0x80244019: ("Update server returned 'not found' (404)",
                 "The requested file isn't on the server — common with a misconfigured WSUS."),
    0x80240438: ("Couldn't reach the Windows Update service",
                 "No route to the update endpoint — proxy, firewall, or a disabled WU service."),
    0x80246007: ("Update isn't downloaded yet",
                 "It tried to install something that never finished downloading."),
    0x80070002: ("A required file was not found", "Servicing data is missing — a WU cache reset (Toolbox) often fixes it."),
    0x80070005: ("Access denied", "A permissions problem on a servicing folder/key — usually needs elevation or a cache reset."),
    0x800F081F: ("Source files couldn't be found",
                 "DISM/servicing couldn't find the payload. Provide a source or repair the component store."),
    0x80D02002: ("Timed out during download", "The download stalled — connectivity or a metered/slow link."),
    0xC1900208: ("A program is blocking the feature update",
                 "An incompatible app was found. Windows usually names it — uninstall or update it, then retry."),
    0xC1900101: ("A driver caused the feature update to roll back",
                 "A device driver failed during upgrade. Update/uninstall the flagged driver, then retry."),
    0x80248007: ("Missing licence terms or a damaged WU datastore",
                 "Reset the WU components (Toolbox) and retry."),
    0x80242006: ("Invalid update metadata", "The update info was malformed — a cache reset and rescan usually clears it."),
}

_RESULT = {0: "Not started", 1: "In progress", 2: "Succeeded",
           3: "Succeeded with errors", 4: "Failed", 5: "Aborted"}
_OPERATION = {1: "Install", 2: "Uninstall", 3: "Other"}

# Services Windows Update relies on.
_WU_SERVICES = ["wuauserv", "bits", "usosvc", "dosvc", "cryptsvc", "trustedinstaller"]

# ServiceControllerStatus / ServiceStartMode enums serialise as ints over JSON.
_SVC_STATUS = {1: "Stopped", 2: "Starting", 3: "Stopping", 4: "Running",
               5: "Continuing", 6: "Pausing", 7: "Paused"}
_SVC_START = {0: "Boot", 1: "System", 2: "Automatic", 3: "Manual", 4: "Disabled"}


def _svc_text(value, table):
    try:
        return table.get(int(value), str(value))
    except (TypeError, ValueError):
        return str(value)


def _decode_hresult(h):
    if h is None:
        return None, None
    # PowerShell hands back a signed int32; normalise to unsigned 0xXXXXXXXX.
    code = h & 0xFFFFFFFF
    name, advice = _HRESULT.get(code, (None, None))
    hexs = f"0x{code:08X}"
    if name:
        return hexs, {"meaning": name, "advice": advice}
    if code == 0:
        return hexs, {"meaning": "Succeeded", "advice": ""}
    return hexs, {"meaning": "Unrecognised update error code", "advice":
                  "Search this code on Microsoft's site; a WU cache reset (Toolbox) clears many transient ones."}


def wu_history(limit=40):
    """Recent update history with decoded results, newest first."""
    cmd = (
        "$s = New-Object -ComObject Microsoft.Update.Session; "
        "$searcher = $s.CreateUpdateSearcher(); "
        "$count = [Math]::Min($searcher.GetTotalHistoryCount(), %d); "
        "if ($count -le 0) { '[]' } else { "
        "$searcher.QueryHistory(0, $count) | ForEach-Object { [pscustomobject]@{ "
        "Title=$_.Title; Date=$_.Date.ToString('yyyy-MM-dd HH:mm'); "
        "Operation=[int]$_.Operation; ResultCode=[int]$_.ResultCode; "
        "HResult=[int]$_.HResult } } }"
    ) % int(limit)
    rows = as_list(ps_json(cmd, timeout=40, depth=3))
    items = []
    fails = 0
    for r in rows:
        if not isinstance(r, dict):
            continue
        hexs, decoded = _decode_hresult(r.get("HResult"))
        result = _RESULT.get(r.get("ResultCode"), "Unknown")
        if r.get("ResultCode") in (3, 4, 5):
            fails += 1
        items.append({
            "title": r.get("Title") or "(untitled update)",
            "date": r.get("Date"),
            "operation": _OPERATION.get(r.get("Operation"), "Other"),
            "result": result,
            "ok": r.get("ResultCode") == 2,
            "hresult": hexs,
            "meaning": decoded["meaning"] if decoded else None,
            "advice": decoded["advice"] if decoded else None,
        })
    return {"ok": True, "items": items, "total": len(items), "failures": fails}


def wu_health():
    """Last successful scan/install + the state of WU's supporting services."""
    svc_filter = "','".join(_WU_SERVICES)
    cmd = (
        "$o = [ordered]@{}; "
        "try { $au = (New-Object -ComObject Microsoft.Update.AutoUpdate).Results; "
        "$o.last_search = if ($au.LastSearchSuccessDate) { $au.LastSearchSuccessDate.ToString('yyyy-MM-dd HH:mm') } else { $null }; "
        "$o.last_install = if ($au.LastInstallationSuccessDate) { $au.LastInstallationSuccessDate.ToString('yyyy-MM-dd HH:mm') } else { $null } } "
        "catch { $o.last_search = $null; $o.last_install = $null }; "
        f"$o.services = Get-Service -Name @('{svc_filter}') -ErrorAction SilentlyContinue | "
        "Select-Object Name,Status,StartType; $o"
    )
    d = ps_json(cmd, timeout=30, depth=3) or {}
    services = []
    for s in as_list(d.get("services")):
        if isinstance(s, dict):
            status = _svc_text(s.get("Status"), _SVC_STATUS)
            start = _svc_text(s.get("StartType"), _SVC_START)
            # A core WU service left Disabled is the red flag (the rest start on demand).
            bad = s.get("Name", "").lower() in ("wuauserv", "bits") and start == "Disabled"
            services.append({"name": s.get("Name"), "status": status,
                             "start": start, "concern": bad})
    return {"ok": True, "last_search": d.get("last_search"),
            "last_install": d.get("last_install"), "services": services}
