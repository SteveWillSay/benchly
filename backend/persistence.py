"""Persistence deep-map — the spots autoruns flattens or misses.

  * WMI event subscriptions (__EventFilter / __EventConsumer / binding) — fileless
    persistence that survives reboots and triggers on events. Autoruns doesn't
    surface these clearly.
  * Services and scheduled tasks scored on the real tells: binaries in
    user-writable/temp paths, unquoted service paths, encoded PowerShell.

Read-only. Findings are ranked context, not verdicts — legit software trips some
of these, so review before acting.
"""

import re

from .ps import ps_json, as_list

_WMI_PS = r"""
$o = [ordered]@{}
$o.consumers = Get-CimInstance -Namespace root\subscription -ClassName __EventConsumer -ErrorAction SilentlyContinue |
    ForEach-Object { [pscustomobject]@{
        Name=$_.Name; Type=$_.CimClass.CimClassName
        Cmd=$_.CommandLineTemplate; Exe=$_.ExecutablePath; Script=$_.ScriptText } }
$o.filters = Get-CimInstance -Namespace root\subscription -ClassName __EventFilter -ErrorAction SilentlyContinue |
    ForEach-Object { [pscustomobject]@{ Name=$_.Name; Query=$_.Query } }
$o.bindings = @(Get-CimInstance -Namespace root\subscription -ClassName __FilterToConsumerBinding -ErrorAction SilentlyContinue).Count
$o
"""

_BENIGN_CONSUMER = ("scm event log", "bvtconsumer", "bvtfilter")
# genuinely user-writable spots (deliberately NOT ProgramData/Program Files — too
# many legit AV/vendor services live there and would be false positives)
_USER_WRITABLE = re.compile(r"\\(appdata\\|local\\temp\\|\\temp\\|downloads\\|users\\public\\|\$recycle)", re.I)
_ENCODED = re.compile(r"-e(nc|ncodedcommand)?\s+[A-Za-z0-9+/=]{20,}|frombase64string|downloadstring|iex\b|invoke-expression", re.I)


def _wmi_subscriptions():
    d = ps_json(_WMI_PS, timeout=40, depth=4) or {}
    out = []
    for c in as_list(d.get("consumers")):
        name = (c.get("Name") or "")
        if any(b in name.lower() for b in _BENIGN_CONSUMER):
            continue
        payload = c.get("Cmd") or c.get("Exe") or c.get("Script") or ""
        reasons = []
        if _ENCODED.search(payload):
            reasons.append("runs encoded / downloaded code")
        if _USER_WRITABLE.search(payload):
            reasons.append("runs from a user-writable path")
        out.append({
            "name": name,
            "type": (c.get("Type") or "").replace("EventConsumer", ""),
            "payload": payload[:240],
            "reasons": reasons,
        })
    return out, d.get("bindings") or 0


_SVC_PS = (
    "Get-CimInstance Win32_Service -ErrorAction SilentlyContinue | "
    "Select-Object Name,DisplayName,PathName,StartMode,State,StartName")


def _suspicious_services():
    rows = as_list(ps_json(_SVC_PS, timeout=40))
    out = []
    for s in rows:
        path = s.get("PathName") or ""
        # strip args to get the exe
        exe = path
        m = re.match(r'^\s*"([^"]+)"', path) or re.match(r"^\s*(\S+\.exe)", path, re.I)
        if m:
            exe = m.group(1)
        reasons = []
        if _USER_WRITABLE.search(exe):
            reasons.append("binary in a user-writable path")
        if " " in exe.strip() and not path.strip().startswith('"'):
            reasons.append("unquoted path with spaces")
        if not reasons:
            continue
        out.append({"name": s.get("Name"), "display": s.get("DisplayName"),
                    "path": path[:200], "start": s.get("StartMode"),
                    "state": s.get("State"), "reasons": reasons})
    return out


_TASK_PS = (
    "Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.State -ne 'Disabled' } | "
    "ForEach-Object { [pscustomobject]@{ Name=$_.TaskName; Path=$_.TaskPath; "
    "Author=$_.Author; Exec=(($_.Actions | Where-Object {$_.Execute}) | ForEach-Object { $_.Execute + ' ' + $_.Arguments }) -join ' | ' } }")


def _suspicious_tasks():
    rows = as_list(ps_json(_TASK_PS, timeout=60, depth=3))
    out = []
    for t in rows:
        exec_str = t.get("Exec") or ""
        reasons = []
        if _ENCODED.search(exec_str):
            reasons.append("runs encoded / downloaded code")
        if _USER_WRITABLE.search(exec_str):
            reasons.append("runs from a user-writable path")
        if not reasons:
            continue
        out.append({"name": t.get("Name"), "path": t.get("Path"),
                    "author": t.get("Author") or "", "exec": exec_str[:240], "reasons": reasons})
    return out


def map_persistence():
    wmi, bindings = _wmi_subscriptions()
    services = _suspicious_services()
    tasks = _suspicious_tasks()
    total = len(wmi) + len(services) + len(tasks)
    flags = []
    if wmi:
        flags.append({"level": "warn", "text": f"{len(wmi)} WMI event subscription(s) present — fileless persistence that autoruns won't show. Review carefully."})
    if services:
        flags.append({"level": "warn", "text": f"{len(services)} service(s) with a risky path shape."})
    if tasks:
        flags.append({"level": "warn", "text": f"{len(tasks)} scheduled task(s) running encoded code or from a user-writable path."})
    if not total:
        flags.append({"level": "good", "text": "No WMI subscriptions and nothing odd in services or tasks."})
    return {"ok": True, "wmi": wmi, "wmi_bindings": bindings, "services": services,
            "tasks": tasks, "total": total, "flags": flags}
