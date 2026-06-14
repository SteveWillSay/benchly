"""Time sync health — the silent root cause of cert errors and sign-in failures.

A clock that's drifted by more than a few seconds quietly breaks HTTPS, Kerberos,
MFA and licensing. This reads where the machine gets its time, when it last synced,
and how far off it currently is, and offers a resync. Reading is harmless; resync is
a safe, standard operation.
"""

import re

from .ps import run_ps, ps_json


def _q(field, text):
    for ln in text.splitlines():
        if ln.strip().lower().startswith(field.lower()):
            return ln.split(":", 1)[1].strip() if ":" in ln else None
    return None


def _offset_seconds():
    """One stripchart sample against time.windows.com → current offset in seconds."""
    out = run_ps("w32tm /stripchart /computer:time.windows.com /samples:1 /dataonly 2>&1",
                 timeout=20) or ""
    # data lines look like '15:04:05, +00.0123456s' or 'error'
    m = re.search(r"([+-]?\d+\.\d+)\s*s", out)
    if m:
        try:
            return round(float(m.group(1)), 3)
        except ValueError:
            return None
    return None


_TYPE = {"NTP": "NTP (internet/manual server)",
         "NT5DS": "Domain hierarchy (NT5DS)",
         "AllSync": "All available sources",
         "NoSync": "Not syncing (NoSync)"}


def time_status():
    status = run_ps("w32tm /query /status 2>&1", timeout=20) or ""
    config = run_ps("w32tm /query /configuration 2>&1", timeout=20) or ""
    source = run_ps("w32tm /query /source 2>&1", timeout=15) or ""
    source = source.strip().splitlines()[0].strip() if source.strip() else None
    # When W32Time is stopped, /query returns an error string — treat as 'unknown'.
    if source and ("error" in source.lower() or "0x" in source.lower()):
        source = None

    svc = ps_json("Get-Service W32Time -ErrorAction SilentlyContinue | "
                  "Select-Object Status,StartType", timeout=15) or {}
    svc_status = {1: "Stopped", 4: "Running"}.get(svc.get("Status"), str(svc.get("Status")))
    svc_start = {2: "Automatic", 3: "Manual", 4: "Disabled"}.get(svc.get("StartType"),
                                                                 str(svc.get("StartType")))

    sync_type_raw = _q("Type", config)
    last_sync = _q("Last Successful Sync Time", status)
    stratum = _q("Stratum", status)

    offset = _offset_seconds()
    if offset is None:
        level, verdict = "warn", "Couldn't measure the current offset (no route to a time server, or W32Time is idle)."
    elif abs(offset) <= 2:
        level, verdict = "good", f"The clock is in sync (off by {offset:+.3f}s)."
    elif abs(offset) <= 30:
        level, verdict = "warn", f"The clock is off by {offset:+.3f}s — enough to start causing certificate and sign-in errors. A resync will fix it."
    else:
        level, verdict = "bad", f"The clock is off by {offset:+.1f}s — this will break HTTPS, Kerberos and sign-in. Resync now."

    return {
        "ok": True,
        "offset_s": offset, "level": level, "verdict": verdict,
        "source": source,
        "sync_type": _TYPE.get((sync_type_raw or "").strip(), sync_type_raw),
        "last_sync": last_sync,
        "stratum": stratum,
        "service": f"{svc_status} · {svc_start}",
        "service_concern": svc_start == "Disabled",
    }


def time_resync():
    """Force a resync now. Safe and standard; the service must be running."""
    out = run_ps("& { Start-Service W32Time -ErrorAction SilentlyContinue; "
                 "w32tm /resync /force 2>&1 } | Out-String", timeout=30) or ""
    ok = "successfully" in out.lower() or "completed" in out.lower()
    if ok:
        return {"ok": True, "message": "Time resynced."}
    return {"ok": False, "error": (out.strip().splitlines()[-1].strip()
                                   if out.strip() else "Resync didn't complete — the time service may be stopped.")}
