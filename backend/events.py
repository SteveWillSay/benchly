"""Recent error/warning events from the System and Application logs."""

from .ps import ps_json, as_list

_EVENTS_PS = r"""
$start = (Get-Date).AddDays(-__DAYS__)
Get-WinEvent -FilterHashtable @{ LogName = 'System','Application'; Level = 1,2,3; StartTime = $start } `
    -MaxEvents __MAX__ -ErrorAction SilentlyContinue |
    Select-Object @{n='Time';e={$_.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')}},
                  LogName, LevelDisplayName, ProviderName, Id,
                  @{n='Msg';e={ if ($_.Message) { $_.Message.Substring(0, [Math]::Min(400, $_.Message.Length)) } else { '' } }}
"""


def get_events(days: int = 7, max_events: int = 300):
    script = _EVENTS_PS.replace("__DAYS__", str(int(days))).replace("__MAX__", str(int(max_events)))
    rows = as_list(ps_json(script, timeout=60, depth=3))
    events = []
    for r in rows:
        level = (r.get("LevelDisplayName") or "").lower()
        events.append({
            "time": r.get("Time"),
            "log": r.get("LogName"),
            "level": "critical" if level == "critical" else ("error" if level == "error" else "warning"),
            "source": r.get("ProviderName"),
            "id": r.get("Id"),
            "message": (r.get("Msg") or "").replace("\r\n", " ").replace("\n", " ").strip(),
        })

    # PowerShell ordering isn't guaranteed once as_list collapses results — sort
    # newest-first ourselves so "oldest"/truncation and report slicing are correct.
    events.sort(key=lambda e: e["time"] or "", reverse=True)

    counts = {"critical": 0, "error": 0, "warning": 0}
    for e in events:
        counts[e["level"]] = counts.get(e["level"], 0) + 1

    return {
        "events": events,
        "counts": counts,
        "days": days,
        # newest-first: if we hit the cap, the oldest row shown is later than the
        # requested window start — surface that so range changes aren't confusing
        "truncated": len(events) >= max_events,
        "oldest": events[-1]["time"] if events else None,
    }
