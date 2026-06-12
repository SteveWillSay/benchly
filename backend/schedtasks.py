"""Scheduled-task audit — every non-Microsoft task with its action and last result."""

from .ps import ps_json, as_list

_TASKS_PS = r"""
Get-ScheduledTask | Where-Object { $_.TaskPath -notlike '\Microsoft\*' } | ForEach-Object {
    $info = $null
    try { $info = $_ | Get-ScheduledTaskInfo -ErrorAction Stop } catch {}
    [pscustomobject]@{
        Path    = $_.TaskPath
        Name    = $_.TaskName
        State   = [string]$_.State
        Author  = $_.Author
        Action  = (($_.Actions | ForEach-Object { ($_.Execute + ' ' + $_.Arguments).Trim() }) -join ' ; ')
        LastRun = if ($info -and $info.LastRunTime -and $info.LastRunTime.Year -gt 2000) { $info.LastRunTime.ToString('yyyy-MM-dd HH:mm') } else { $null }
        NextRun = if ($info -and $info.NextRunTime -and $info.NextRunTime.Year -gt 2000) { $info.NextRunTime.ToString('yyyy-MM-dd HH:mm') } else { $null }
        Result  = if ($info) { $info.LastTaskResult } else { $null }
    }
}
"""


def get_tasks():
    rows = as_list(ps_json(_TASKS_PS, timeout=90))
    tasks = []
    for t in rows:
        result = t.get("Result")
        if result == 0:
            result_text, result_ok = "Success", True
        elif result == 267011:          # 0x41303 — task has not yet run
            result_text, result_ok = "Never run", None
        elif result == 267009:          # 0x41301 — currently running
            result_text, result_ok = "Running", True
        elif result is None:
            result_text, result_ok = "—", None
        else:
            result_text, result_ok = f"0x{result & 0xFFFFFFFF:08X}", False
        tasks.append({
            "path": t.get("Path") or "\\",
            "name": t.get("Name") or "",
            "state": t.get("State") or "",
            "author": t.get("Author") or "",
            "action": t.get("Action") or "",
            "last_run": t.get("LastRun"),
            "next_run": t.get("NextRun"),
            "result": result_text,
            "result_ok": result_ok,
        })
    # failures first, then by path/name
    tasks.sort(key=lambda x: (x["result_ok"] is not False, x["path"].lower(), x["name"].lower()))
    return tasks
