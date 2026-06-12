"""Pending Windows Updates via the Microsoft.Update.Session COM searcher.

Listing is reliable without extra tooling; installing is not (USOClient verbs are
undocumented on Win 11), so we list + deep-link into Settings and stay honest.
"""

from .ps import ps_json, as_list

# Always emits a wrapper object: zero pending updates must produce JSON too,
# otherwise "fully patched" is indistinguishable from "search failed".
_PENDING_PS = r"""
$session = New-Object -ComObject Microsoft.Update.Session
$searcher = $session.CreateUpdateSearcher()
$result = $searcher.Search("IsInstalled=0 and IsHidden=0")
[pscustomobject]@{
    updates = @($result.Updates | ForEach-Object {
        [pscustomobject]@{
            Title      = $_.Title
            Severity   = [string]$_.MsrcSeverity
            Downloaded = $_.IsDownloaded
            SizeMB     = [math]::Round($_.MaxDownloadSize / 1MB, 1)
            Categories = (($_.Categories | ForEach-Object { $_.Name }) -join ', ')
        }
    })
}
"""


def get_pending_updates():
    """Slow (10–60 s) — the searcher talks to the WU service. Called on demand only."""
    result = ps_json(_PENDING_PS, timeout=180)
    if result is None:
        return {"ok": False,
                "error": "Windows Update search failed (service unavailable or no internet)."}
    updates = []
    for u in as_list(result.get("updates")):
        updates.append({
            "title": u.get("Title"),
            "severity": u.get("Severity") or "",
            "downloaded": bool(u.get("Downloaded")),
            "size_mb": u.get("SizeMB"),
            "categories": u.get("Categories") or "",
        })
    sev_rank = {"Critical": 0, "Important": 1, "Moderate": 2, "Low": 3, "": 4}
    updates.sort(key=lambda x: (sev_rank.get(x["severity"], 4), x["title"] or ""))
    return {"ok": True, "updates": updates}
