"""Audio device doctor — the 'no sound / wrong output / can't pick a device' triage.

Lists the playback and recording endpoints and their state (active / disabled /
unplugged / error), and checks the two audio services everything depends on. The
quick read on why sound's gone or stuck on the wrong device. Reading is harmless;
restarting the audio services is optional and reversible.
"""

from .ps import ps_json, as_list, run_ps
from . import security

_STATE = {"OK": "active", "Error": "error", "Unknown": "unknown", "Degraded": "degraded"}


def audio_status():
    rows = as_list(ps_json(
        "Get-PnpDevice -Class AudioEndpoint -ErrorAction SilentlyContinue | "
        "Select-Object FriendlyName,@{n='St';e={[string]$_.Status}},"
        "@{n='Present';e={[bool]$_.Present}},InstanceId", timeout=25))
    endpoints = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        inst = str(r.get("InstanceId") or "")
        # endpoint instance ids start with SWD\MMDEVAPI\{0.0.0... (render) / {0.0.1... (capture)
        kind = "Recording" if ".0.1.00000000}" in inst else "Playback"
        status = _STATE.get(r.get("St"), str(r.get("St")))
        endpoints.append({
            "name": r.get("FriendlyName") or "(unnamed)",
            "kind": kind,
            "status": status,
            "present": r.get("Present") in (True, 1, "True"),
            "concern": status in ("error", "degraded"),
        })

    svc = ps_json("Get-Service Audiosrv,AudioEndpointBuilder -ErrorAction SilentlyContinue | "
                  "Select-Object Name,@{n='St';e={[string]$_.Status}}", timeout=15)
    services = []
    for s in as_list(svc):
        if isinstance(s, dict):
            running = str(s.get("St")).lower() == "running"
            services.append({"name": s.get("Name"), "status": s.get("St"),
                             "concern": not running})

    active_play = sum(1 for e in endpoints if e["kind"] == "Playback" and e["status"] == "active")
    notes = []
    if active_play == 0:
        notes.append("No active playback device — that's usually why there's no sound. "
                     "Plug in / enable a device, or check the cables.")
    if any(s["concern"] for s in services):
        notes.append("An audio service isn't running — restarting it often restores sound.")

    return {"ok": True, "endpoints": endpoints, "services": services,
            "active_playback": active_play, "notes": notes}


def restart_audio():
    """Restart the Windows audio services (reversible — they just start again)."""
    if not security.is_admin():
        return {"ok": False, "error": "Restarting the audio services needs elevation — use Run as admin."}
    out = run_ps("& { Restart-Service Audiosrv -Force -ErrorAction SilentlyContinue; 'OK' }", timeout=30)
    if "OK" in out:
        return {"ok": True, "where": "Restarted Audiosrv (and its dependency AudioEndpointBuilder)."}
    return {"ok": False, "error": "Couldn't restart the audio service."}
