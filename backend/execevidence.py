"""\"What ran recently\" — execution evidence from Prefetch.

Windows writes a Prefetch file the first time (and keeps updating it) each program
runs. The filename carries the executable name and the file's modified time is the
last time it ran — so even after malware deletes itself, the evidence it executed
remains. We read the names and timestamps (no fragile binary parsing) into a
timeline. Reading Prefetch needs administrator rights.
"""

import datetime
import os
import re

_PREFETCH = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Prefetch")
_PF_RE = re.compile(r"^(.+?)-[0-9A-F]{7,16}\.pf$", re.I)

# living-off-the-land binaries worth noticing in an execution timeline
_LOLBIN = {"mshta.exe", "wscript.exe", "cscript.exe", "regsvr32.exe", "rundll32.exe",
           "msbuild.exe", "installutil.exe", "regasm.exe", "regsvcs.exe", "certutil.exe",
           "bitsadmin.exe", "powershell.exe", "pwsh.exe"}


def recent_execution(days=14):
    try:
        days = max(1, min(int(days), 90))
    except (TypeError, ValueError):
        days = 14
    try:
        names = os.listdir(_PREFETCH)
    except PermissionError:
        return {"ok": False, "error": "no_admin",
                "message": "Reading Prefetch needs administrator rights — use Run as admin."}
    except FileNotFoundError:
        return {"ok": False, "error": "Prefetch is turned off or empty on this PC."}

    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    entries = []
    for fn in names:
        if not fn.lower().endswith(".pf"):
            continue
        full = os.path.join(_PREFETCH, fn)
        try:
            mt = datetime.datetime.fromtimestamp(os.path.getmtime(full))
        except OSError:
            continue
        m = _PF_RE.match(fn)
        exe = (m.group(1) if m else fn).strip()
        entries.append({
            "exe": exe,
            "last_run": mt.strftime("%Y-%m-%d %H:%M"),
            "ts": mt.timestamp(),
            "recent": mt >= cutoff,
            "lolbin": exe.lower() in _LOLBIN,
        })
    entries.sort(key=lambda e: e["ts"], reverse=True)
    recent = [e for e in entries if e["recent"]]
    lolbins = [e for e in recent if e["lolbin"]]
    flags = []
    if lolbins:
        flags.append({"level": "warn",
                      "text": f"{len(lolbins)} living-off-the-land tool(s) ran in the last {days} days "
                              "(mshta/rundll32/regsvr32/PowerShell…) — normal for some software, worth a glance."})
    flags.append({"level": "info", "text": f"{len(recent)} program(s) ran in the last {days} days · {len(entries)} in Prefetch overall."})
    return {"ok": True, "days": days, "total": len(entries),
            "entries": entries[:300], "recent_count": len(recent),
            "lolbin_count": len(lolbins), "flags": flags}
