"""Power, sleep and wake doctor.

Wraps the powercfg dark arts into plain English: what's blocking sleep right now,
what woke the machine, which devices/timers are armed to wake it, and which sleep
states are even available. Read-first; the toggles (disarm a wake device / a
wake-capable scheduled task) are documented and reversible.
"""

import re
import subprocess

from .ps import ps_json, as_list, CREATE_NO_WINDOW
from . import security


def _run(args, timeout=20):
    """Run a console tool, decode with the OEM codepage (powercfg isn't UTF-8)."""
    try:
        r = subprocess.run(args, capture_output=True, timeout=timeout,
                           creationflags=CREATE_NO_WINDOW)
        out = r.stdout.decode("mbcs", errors="replace")
        err = r.stderr.decode("mbcs", errors="replace")
        return out + ("\n" + err if err.strip() else ""), r.returncode
    except Exception as e:
        return f"error: {e}", -1


def _needs_admin(text):
    return "requires administrator" in text.lower() or "elevated" in text.lower()


# --------------------------------------------------------------------------- #
# sleep states + what's blocking sleep
# --------------------------------------------------------------------------- #
def _sleep_states():
    out, _ = _run(["powercfg", "/a"])
    available, modern_standby = [], False
    grab = False
    for line in out.splitlines():
        s = line.strip()
        low = s.lower()
        if "are available" in low:
            grab = True
            continue
        if "are not available" in low or "is not available" in low:
            grab = False
            continue
        if grab and s:
            available.append(s)
            if "s0 low power idle" in low or "standby (s0" in low:
                modern_standby = True
    return {"available": available, "modern_standby": modern_standby}


def _requests():
    """powercfg /requests — live SYSTEM/DISPLAY/AWAYMODE/EXECUTION sleep blockers."""
    out, _ = _run(["powercfg", "/requests"])
    if _needs_admin(out):
        return {"admin": False, "blockers": []}
    blockers = []
    section = None
    for raw in out.splitlines():
        line = raw.rstrip()
        m = re.match(r"^([A-Z]+):\s*$", line.strip())
        if m:
            section = m.group(1)
            continue
        s = line.strip()
        if not s or s.lower() == "none.":
            continue
        if section:
            # e.g. "[DRIVER] Realtek...  An audio stream is currently in use."
            mt = re.match(r"\[(\w+)\]\s+(.*)", s)
            who = mt.group(2) if mt else s
            kind = mt.group(1) if mt else ""
            blockers.append({"category": section, "kind": kind, "what": who[:200]})
    return {"admin": True, "blockers": blockers}


def _wake_timers():
    out, _ = _run(["powercfg", "/waketimers"])
    if _needs_admin(out):
        return {"admin": False, "timers": []}
    timers = []
    cur = None
    for raw in out.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("["):
            if cur:
                timers.append(cur)
            cur = {"owner": s[:200], "reason": ""}
        elif cur and s.lower().startswith("reason:"):
            cur["reason"] = s.split(":", 1)[1].strip()[:300]
    if cur:
        timers.append(cur)
    return {"admin": True, "timers": timers}


def _wake_armed_devices():
    out, _ = _run(["powercfg", "/devicequery", "wake_armed"])
    devices = [s.strip() for s in out.splitlines()
               if s.strip() and "NONE" not in s.strip().upper()]
    return devices


def _last_wake():
    out, _ = _run(["powercfg", "/lastwake"])
    src = None
    for s in out.splitlines():
        line = s.strip()
        if line.lower().startswith("type:"):
            src = line.split(":", 1)[1].strip()
        elif line.lower().startswith("owner:") and src:
            src += " — " + line.split(":", 1)[1].strip()
    return src


def power_overview():
    states = _sleep_states()
    req = _requests()
    timers = _wake_timers()
    flags = []
    if req["admin"]:
        if req["blockers"]:
            flags.append({"level": "info",
                          "text": f"{len(req['blockers'])} thing(s) are currently keeping this PC awake."})
        else:
            flags.append({"level": "good", "text": "Nothing is blocking sleep right now."})
    else:
        flags.append({"level": "warn", "text": "Run as admin to see what's blocking sleep and to read wake timers."})
    if timers["admin"] and timers["timers"]:
        if any("updateorchestrator" in t["reason"].lower() or "reboot" in t["reason"].lower()
               for t in timers["timers"]):
            flags.append({"level": "info", "text": "A Windows Update timer is set to wake this PC."})
    return {
        "ok": True,
        "is_admin": security.is_admin(),
        "sleep_states": states["available"],
        "modern_standby": states["modern_standby"],
        "requests": req,
        "wake_timers": timers,
        "wake_devices": _wake_armed_devices(),
        "last_wake": _last_wake(),
        "flags": flags,
    }


# --------------------------------------------------------------------------- #
# wake history (Kernel-Power, Event ID 1)
# --------------------------------------------------------------------------- #
def wake_history(days=7):
    try:
        days = max(1, min(int(days), 30))
    except (TypeError, ValueError):
        days = 7
    cmd = (
        "Get-WinEvent -FilterHashtable @{LogName='System'; "
        "ProviderName='Microsoft-Windows-Kernel-Power'; Id=1; "
        "StartTime=(Get-Date).AddDays(-__DAYS__)} -MaxEvents 60 -ErrorAction SilentlyContinue | "
        "Select-Object @{n='Time';e={$_.TimeCreated.ToString('yyyy-MM-dd HH:mm')}},"
        "@{n='Msg';e={$_.Message}}"
    ).replace("__DAYS__", str(days))
    rows = as_list(ps_json(cmd, timeout=40, depth=2))
    events = []
    for r in rows:
        msg = r.get("Msg") or ""
        m = re.search(r"Wake Source:\s*(.+)", msg)
        src = (m.group(1).strip() if m else "Unknown") or "Unknown"
        events.append({"time": r.get("Time"), "source": src[:160]})
    return {"ok": True, "events": events, "count": len(events)}


# --------------------------------------------------------------------------- #
# actions (reversible, documented)
# --------------------------------------------------------------------------- #
def set_device_wake(name, enable):
    if not security.is_admin():
        return {"ok": False, "error": "Changing device wake needs elevation — use Run as admin."}
    if not name or len(name) > 200:
        return {"ok": False, "error": "Invalid device."}
    verb = "/deviceenablewake" if enable else "/devicedisablewake"
    out, rc = _run(["powercfg", verb, name])
    if rc == 0:
        return {"ok": True, "where": f"powercfg {verb} \"{name}\""}
    return {"ok": False, "error": out.strip()[:200] or "powercfg failed."}


def disarm_wake_task(task_path):
    """Stop a scheduled task from waking the PC (clears its 'wake the computer' condition)."""
    if not security.is_admin():
        return {"ok": False, "error": "Changing a wake task needs elevation — use Run as admin."}
    if not task_path or not re.match(r"^[\\\w\s\-./()]+$", task_path):
        return {"ok": False, "error": "Invalid task path."}
    # Set WakeToRun off via Set-ScheduledTask settings
    safe = task_path.replace("'", "''")
    cmd = (
        f"$t = Get-ScheduledTask -TaskPath ([System.IO.Path]::GetDirectoryName('{safe}') + '\\') "
        f"-TaskName ([System.IO.Path]::GetFileName('{safe}')) -ErrorAction Stop; "
        "$t.Settings.WakeToRun = $false; Set-ScheduledTask -InputObject $t -ErrorAction Stop | Out-Null; 'OK'"
    )
    from .ps import run_ps
    out = run_ps("& { " + cmd + " }", timeout=30)
    if "OK" in out:
        return {"ok": True, "where": f"Scheduled task {task_path} → Conditions → Wake the computer (off)"}
    return {"ok": False, "error": "Could not change the task (it may not exist or need admin)."}


# --------------------------------------------------------------------------- #
# Power efficiency reports (H1)
# --------------------------------------------------------------------------- #
import os
import tempfile


def battery_report():
    """Battery wear & cycle count from powercfg's battery report (laptops)."""
    has_batt = ps_json("[bool](Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue)", timeout=15)
    if not has_batt:
        return {"ok": True, "has_battery": False,
                "message": "No battery — this looks like a desktop or a PC without one."}
    out = os.path.join(tempfile.gettempdir(), "benchly-battery.xml")
    from .ps import run_ps
    run_ps(f'powercfg /batteryreport /xml /output "{out}" 2>&1', timeout=30)
    design = full = cycles = None
    try:
        import xml.etree.ElementTree as ET
        txt = open(out, encoding="utf-8", errors="replace").read()
        txt = re.sub(r'\sxmlns="[^"]+"', "", txt, count=1)   # drop the default namespace
        root = ET.fromstring(txt)
        for b in root.iter("Battery"):
            d, f, c = b.findtext("DesignCapacity"), b.findtext("FullChargeCapacity"), b.findtext("CycleCount")
            design = int(d) if d and d.isdigit() else design
            full = int(f) if f and f.isdigit() else full
            cycles = int(c) if c and c.isdigit() else cycles
            break
    except Exception:
        pass
    wear = round((1 - full / design) * 100, 1) if (design and full and design > 0) else None
    return {"ok": True, "has_battery": True, "design_mwh": design, "full_mwh": full,
            "cycles": cycles, "wear_pct": wear}


def energy_report(duration=30):
    """A short powercfg /energy trace → the efficiency errors/warnings it found.

    Runs a live trace for `duration` seconds, so it's a deliberate on-demand check.
    """
    if not security.is_admin():
        return {"ok": True, "needs_admin": True,
                "note": "The energy efficiency trace needs admin — use Run as admin, then try again."}
    from .ps import run_ps
    out = os.path.join(tempfile.gettempdir(), "benchly-energy.html")
    txt = run_ps(f'powercfg /energy /output "{out}" /duration {int(duration)} 2>&1 | Out-String',
                 timeout=int(duration) + 30) or ""
    def _n(label):
        m = re.search(rf"(\d+)\s+{label}", txt)
        return int(m.group(1)) if m else None
    issues = []
    try:
        html = open(out, encoding="utf-8", errors="replace").read()
        for cls, level in (("errorName", "error"), ("warnName", "warning")):
            for mm in re.finditer(rf'class="{cls}">(.*?)</td>', html, re.S):
                t = re.sub("<[^>]+>", "", mm.group(1)).strip()
                if t:
                    issues.append({"level": level, "text": t[:160]})
    except Exception:
        pass
    return {"ok": True, "duration": int(duration),
            "errors": _n("Errors"), "warnings": _n("Warnings"), "info": _n("Informational"),
            "issues": issues[:25]}
