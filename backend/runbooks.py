"""Guided 'Fix Common Problems' runbooks — the deleted-troubleshooter replacement.

Each runbook is a sequence of steps. Diagnostic steps just report; fix steps run a
command and stream output. The frontend drives them one step at a time with a
confirm before anything that changes the system.
"""

import subprocess

from .ps import run_ps, CREATE_NO_WINDOW
from . import security, network

# Each runbook: id, title, symptom, steps[]. Each step: id, label, kind(diagnose|fix),
# admin(bool), destructive(bool), and a runner key resolved in run_step().
RUNBOOKS = [
    {
        "id": "internet", "title": "No internet connection", "icon": "network",
        "symptom": "Pages won't load, or Windows shows no connectivity.",
        "steps": [
            {"id": "adapter", "label": "Check network adapter & IP", "kind": "diagnose"},
            {"id": "gateway", "label": "Ping the default gateway (your router)", "kind": "diagnose"},
            {"id": "dns", "label": "Test DNS resolution", "kind": "diagnose"},
            {"id": "flushdns", "label": "Flush the DNS resolver cache", "kind": "fix"},
            {"id": "winsock", "label": "Reset Winsock & TCP/IP stack", "kind": "fix", "admin": True,
             "note": "A reboot is needed afterwards."},
        ],
    },
    {
        "id": "audio", "title": "No sound", "icon": "temp",
        "symptom": "No audio from speakers or headphones.",
        "steps": [
            {"id": "audiosvc_status", "label": "Check the Windows Audio service", "kind": "diagnose"},
            {"id": "default_device", "label": "List playback devices", "kind": "diagnose"},
            {"id": "restart_audio", "label": "Restart the audio services", "kind": "fix", "admin": True},
        ],
    },
    {
        "id": "update", "title": "Windows Update stuck", "icon": "download",
        "symptom": "Updates won't download, install, or are stuck at a percentage.",
        "steps": [
            {"id": "wu_status", "label": "Check update services", "kind": "diagnose"},
            {"id": "wu_reset", "label": "Reset the Windows Update cache", "kind": "fix", "admin": True,
             "note": "Stops update services, clears SoftwareDistribution, restarts them."},
        ],
    },
    {
        "id": "printing", "title": "Can't print", "icon": "printer",
        "symptom": "Print jobs stick in the queue or printers show offline.",
        "steps": [
            {"id": "spooler_status", "label": "Check the Print Spooler", "kind": "diagnose"},
            {"id": "purge_spooler", "label": "Clear stuck jobs & restart the spooler", "kind": "fix",
             "admin": True, "destructive": True, "note": "Deletes all queued print jobs."},
        ],
    },
    {
        "id": "performance", "title": "Running slow", "icon": "cpu2",
        "symptom": "The machine is sluggish or unresponsive.",
        "steps": [
            {"id": "top_cpu", "label": "Find what's using the CPU & memory", "kind": "diagnose"},
            {"id": "disk_space", "label": "Check free disk space", "kind": "diagnose"},
            {"id": "startup_count", "label": "Count startup programs", "kind": "diagnose"},
        ],
    },
]


def list_runbooks():
    return [{k: rb[k] for k in ("id", "title", "symptom", "icon", "steps")} for rb in RUNBOOKS]


def _ok(lines, status="good"):
    return {"ok": True, "status": status, "output": "\n".join(lines) if isinstance(lines, list) else lines}


def run_step(runbook_id, step_id):
    needs = next((s for rb in RUNBOOKS if rb["id"] == runbook_id
                  for s in rb["steps"] if s["id"] == step_id), None)
    if needs and needs.get("admin") and not security.is_admin():
        return {"ok": False, "error": "This step needs elevation — use Run as admin in the title bar."}

    try:
        return _DISPATCH[step_id]()
    except KeyError:
        return {"ok": False, "error": "Unknown step."}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---- diagnostics ----------------------------------------------------------------

def _d_adapter():
    net = network.get_network_info()
    up = [a for a in net["adapters"] if a.get("status") == "Up" and a.get("ipv4")]
    if not up:
        return {"ok": True, "status": "bad",
                "output": "No active adapter with an IP address. Check the cable/Wi-Fi, then re-run."}
    a = up[0]
    apipa = a["ipv4"].startswith("169.254")
    return {"ok": True, "status": "warn" if apipa else "good",
            "output": f"{a['alias']}: {a['ipv4']} (gateway {a['gateway'] or '—'})"
                      + ("\nAddress is APIPA (169.254.x) — DHCP failed; the router isn't handing out an IP." if apipa else "")}


def _d_gateway():
    net = network.get_network_info()
    gw = next((a["gateway"].split(",")[0].strip() for a in net["adapters"]
               if a.get("status") == "Up" and a.get("gateway")), None)
    if not gw:
        return {"ok": True, "status": "bad", "output": "No default gateway configured."}
    r = network.run_ping(gw, 3)
    loss = (r.get("summary") or {}).get("loss_pct")
    return {"ok": True, "status": "good" if loss == 0 else "bad",
            "output": r.get("output", "")}


def _d_dns():
    r = network.dns_lookup("microsoft.com")
    if r.get("ok"):
        return {"ok": True, "status": "good", "output": "DNS resolves: microsoft.com → "
                + ", ".join(x["value"] for x in r["records"][:3])}
    return {"ok": True, "status": "bad",
            "output": "DNS lookup failed — name resolution is broken. The flush step below may help."}


def _d_audiosvc():
    out = run_ps("Get-Service Audiosrv,AudioEndpointBuilder | Format-Table -AutoSize | Out-String")
    bad = "Stopped" in out
    return {"ok": True, "status": "bad" if bad else "good", "output": out.strip()}


def _d_playback():
    out = run_ps("Get-CimInstance Win32_SoundDevice | Select-Object Name,Status | "
                 "Format-Table -AutoSize | Out-String")
    return {"ok": True, "status": "good", "output": out.strip() or "No audio devices reported."}


def _d_wu_status():
    out = run_ps("Get-Service wuauserv,bits,cryptsvc | Format-Table -AutoSize | Out-String")
    return {"ok": True, "status": "good", "output": out.strip()}


def _d_spooler():
    out = run_ps("Get-Service Spooler | Format-Table -AutoSize | Out-String")
    return {"ok": True, "status": "bad" if "Stopped" in out else "good", "output": out.strip()}


def _d_top():
    from . import metrics
    procs = metrics.get_processes(limit=6)
    lines = [f"{p['name']:<28} CPU {p['cpu']:>5.1f}%  RAM {p['mem'] // (1024*1024)} MB" for p in procs]
    return {"ok": True, "status": "good", "output": "\n".join(lines)}


def _d_diskspace():
    import psutil
    u = psutil.disk_usage("C:\\")
    free_pct = 100 - u.percent
    return {"ok": True, "status": "good" if free_pct >= 12 else "bad",
            "output": f"C: has {u.free // (1024**3)} GB free of {u.total // (1024**3)} GB ({free_pct:.0f}%)."
                      + ("" if free_pct >= 12 else "\nLow free space slows Windows — see the Cleanup page.")}


def _d_startupcount():
    from . import software
    items = software.get_startup()
    enabled = [s for s in items if s.get("enabled")]
    high = [s for s in enabled if s.get("impact") == "High"]
    return {"ok": True, "status": "warn" if len(enabled) > 12 else "good",
            "output": f"{len(enabled)} startup programs enabled ({len(high)} high-impact)."
                      + ("\nTrim them on the Software → Startup tab." if len(enabled) > 12 else "")}


# ---- fixes ----------------------------------------------------------------------

def _f_flushdns():
    return _ok(network.flush_dns().get("output", "Flushed."), "good")


def _f_winsock():
    out = []
    for cmd in (["netsh", "winsock", "reset"], ["netsh", "int", "ip", "reset"]):
        r = subprocess.run(cmd, capture_output=True, timeout=60, creationflags=CREATE_NO_WINDOW)
        out.append(f"$ {' '.join(cmd)} → exit {r.returncode}")
    out.append("Reboot to complete the reset.")
    return _ok(out, "good")


def _f_restart_audio():
    out = run_ps("Restart-Service Audiosrv -Force; Restart-Service AudioEndpointBuilder -Force; "
                 "Get-Service Audiosrv | Format-Table -AutoSize | Out-String", timeout=45)
    return _ok(out.strip() or "Audio services restarted.", "good")


def _f_wu_reset():
    # Run the same composite reset synchronously so the runbook step returns its
    # final output inline, like every other step (no detached job to chase).
    from .repair import _WU_RESET
    try:
        result = subprocess.run(["cmd", "/c", _WU_RESET], capture_output=True,
                                timeout=240, creationflags=CREATE_NO_WINDOW)
        out = result.stdout.decode("mbcs", errors="replace").strip()
        return _ok(out or "Windows Update cache reset complete.", "good")
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Reset timed out — try the Toolbox tool, which streams progress."}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _f_purge_spooler():
    from . import devices
    r = devices.purge_print_queue()
    return _ok(r.get("detail", "Queue purged."), "good") if r.get("ok") else {"ok": False, "error": r.get("error")}


_DISPATCH = {
    "adapter": _d_adapter, "gateway": _d_gateway, "dns": _d_dns,
    "flushdns": _f_flushdns, "winsock": _f_winsock,
    "audiosvc_status": _d_audiosvc, "default_device": _d_playback, "restart_audio": _f_restart_audio,
    "wu_status": _d_wu_status, "wu_reset": _f_wu_reset,
    "spooler_status": _d_spooler, "purge_spooler": _f_purge_spooler,
    "top_cpu": _d_top, "disk_space": _d_diskspace, "startup_count": _d_startupcount,
}
