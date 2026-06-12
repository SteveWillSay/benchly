"""Debloat — curated, reversible, conservative per-user AppX removal.

Removal is per-user AppX only (re-installable from the Store). Pre-checks only
uncontroversial consumer junk; never system packages. (Privacy/telemetry and
other registry toggles live in tweaks.py.)
"""

from .ps import ps_json, run_ps, as_list

# Conservative classification. "bloat" = safe to remove + pre-checked; "optional"
# = user's call; everything else is left unclassified (shown, not pre-checked).
_BLOAT = {
    "Microsoft.BingNews": "Microsoft News", "Microsoft.BingWeather": "Weather",
    "Microsoft.BingSearch": "Web Search", "Microsoft.GamingApp": "Xbox Gaming App",
    "Microsoft.XboxApp": "Xbox (legacy)", "Microsoft.ZuneMusic": "Groove Music",
    "Microsoft.ZuneVideo": "Movies & TV", "Microsoft.People": "People",
    "Microsoft.windowscommunicationsapps": "Mail & Calendar (legacy)",
    "Microsoft.YourPhone": "Phone Link", "Microsoft.Todos": "To Do",
    "Microsoft.PowerAutomateDesktop": "Power Automate", "Microsoft.Clipchamp": "Clipchamp",
    "Microsoft.MicrosoftSolitaireCollection": "Solitaire Collection",
    "Microsoft.549981C3F5F10": "Cortana", "MicrosoftTeams": "Teams (personal)",
    "Microsoft.MixedReality.Portal": "Mixed Reality Portal", "Microsoft.Getstarted": "Tips",
    "Microsoft.MicrosoftOfficeHub": "Office hub", "Microsoft.OutlookForWindows": "new Outlook",
    "Clipchamp.Clipchamp": "Clipchamp", "Microsoft.Copilot": "Copilot",
    # third-party consumer junk that ships preinstalled
    "SpotifyAB.SpotifyMusic": "Spotify (preinstalled)", "Disney.37853FC22B2CE": "Disney+",
    "5319275A.WhatsAppDesktop": "WhatsApp (preinstalled)", "king.com.CandyCrush": "Candy Crush",
    "BytedancePte.Ltd.TikTok": "TikTok", "Facebook.Facebook": "Facebook",
    "Microsoft.SkypeApp": "Skype", "AmazonVideo.PrimeVideo": "Prime Video",
}
_OPTIONAL = {
    "Microsoft.WindowsMaps": "Maps", "Microsoft.MicrosoftStickyNotes": "Sticky Notes",
    "Microsoft.Windows.Photos": "Photos", "Microsoft.WindowsSoundRecorder": "Sound Recorder",
    "Microsoft.WindowsFeedbackHub": "Feedback Hub", "Microsoft.WindowsAlarms": "Clock",
    "Microsoft.MSPaint": "Paint 3D", "Microsoft.ScreenSketch": "Snipping Tool",
}


def list_appx():
    rows = as_list(ps_json(
        "Get-AppxPackage -ErrorAction SilentlyContinue | Where-Object { -not $_.IsFramework -and -not $_.NonRemovable } | "
        "Select-Object Name,PackageFullName,@{n='Publisher';e={$_.PublisherDisplayName}}", timeout=90))
    apps = []
    for r in rows:
        name = r.get("Name") or ""
        cat = "bloat" if name in _BLOAT else "optional" if name in _OPTIONAL else "other"
        friendly = _BLOAT.get(name) or _OPTIONAL.get(name) or name.split(".")[-1]
        apps.append({
            "name": name,
            "friendly": friendly,
            "full_name": r.get("PackageFullName"),
            "publisher": r.get("Publisher") or "",
            "category": cat,
        })
    apps.sort(key=lambda a: ({"bloat": 0, "optional": 1, "other": 2}[a["category"]], a["friendly"].lower()))
    return apps


def remove_appx(full_names):
    if isinstance(full_names, str):
        full_names = [full_names]
    removed, errors = [], []
    for fn in full_names:
        safe = fn.replace("'", "''")   # PowerShell single-quote escaping
        out = run_ps(f"try {{ Remove-AppxPackage -Package '{safe}' -ErrorAction Stop; 'OK' }} "
                     "catch { 'ERR: ' + $_.Exception.Message }", timeout=60)
        if "OK" in out:
            removed.append(fn)
        else:
            errors.append(f"{fn.split('_')[0]}: {out.split('ERR:', 1)[-1].strip()[:80]}")
    return {"ok": True, "removed": len(removed), "errors": errors}
