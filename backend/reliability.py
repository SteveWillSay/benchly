"""Reliability timeline — 'when did this start going wrong?'

Correlates Reliability Monitor records, WHEA hardware-error events, and update
installs into one chronological view. Pure correlation of existing logs.
"""

from .ps import ps_json, as_list

_RELIABILITY_PS = r"""
$o = [ordered]@{}
$o.metrics = Get-CimInstance Win32_ReliabilityStabilityMetrics -ErrorAction SilentlyContinue |
    Select-Object @{n='Date';e={ $_.TimeGenerated.ToString('yyyy-MM-dd') }}, SystemStabilityIndex |
    Sort-Object Date | Select-Object -Last 30
$o.records = Get-CimInstance Win32_ReliabilityRecords -ErrorAction SilentlyContinue |
    Select-Object SourceName,EventIdentifier,ProductName,
                  @{n='Time';e={ $_.TimeGenerated.ToString('yyyy-MM-dd HH:mm') }},
                  @{n='Msg';e={ if ($_.Message) { $_.Message.Substring(0,[Math]::Min(160,$_.Message.Length)) } else { $_.ProductName } }} |
    Select-Object -First 80
$start = (Get-Date).AddDays(-90)
$o.whea = Get-WinEvent -FilterHashtable @{ LogName='System'; ProviderName='Microsoft-Windows-WHEA-Logger'; StartTime=$start } -MaxEvents 40 -ErrorAction SilentlyContinue |
    Select-Object @{n='Time';e={ $_.TimeCreated.ToString('yyyy-MM-dd HH:mm') }}, Id, LevelDisplayName,
                  @{n='Msg';e={ if ($_.Message) { $_.Message.Substring(0,[Math]::Min(160,$_.Message.Length)) } else { '' } }}
$o
"""


def get_reliability():
    raw = ps_json(_RELIABILITY_PS, timeout=90, depth=3) or {}

    metrics = [{"date": m.get("Date"), "index": round(m.get("SystemStabilityIndex") or 0, 1)}
               for m in as_list(raw.get("metrics")) if m.get("SystemStabilityIndex") is not None]

    timeline = []
    for r in as_list(raw.get("records")):
        src = r.get("SourceName") or r.get("ProductName") or "?"
        timeline.append({
            "time": r.get("Time"), "type": _classify(src), "source": src,
            "message": (r.get("Msg") or "").replace("\r", " ").replace("\n", " ").strip(),
        })
    for w in as_list(raw.get("whea")):
        timeline.append({
            "time": w.get("Time"), "type": "hardware", "source": "WHEA-Logger",
            "message": f"[{w.get('LevelDisplayName')}] " + (w.get("Msg") or "").replace("\n", " ").strip(),
        })
    timeline.sort(key=lambda x: x["time"] or "", reverse=True)

    return {
        "metrics": metrics,
        "timeline": timeline[:120],
        "whea_count": len(as_list(raw.get("whea"))),
        "current_index": metrics[-1]["index"] if metrics else None,
    }


def _classify(source):
    s = (source or "").lower()
    if "windows update" in s or "update" in s:
        return "update"
    if "application error" in s or "hang" in s or ".net" in s or "crash" in s:
        return "crash"
    if "whea" in s or "disk" in s or "ntfs" in s:
        return "hardware"
    if "install" in s:
        return "install"
    return "info"
