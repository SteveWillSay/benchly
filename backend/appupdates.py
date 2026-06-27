"""Software update check — no winget, no package manager.

Reads what's installed from the registry (via ``software.get_installed``) and
cross-references a *curated* list of common apps against their **official**
sources — the vendor's own version endpoint, or that project's GitHub Releases.
For each match it compares the installed version against the latest and reports
the gap; nothing is ever downloaded or installed here. The UI offers to open the
vendor's official download page, and that's the only outbound action.

Why a curated catalog rather than "check everything": there's no universal,
non-winget web API that maps an arbitrary installed program to its latest
version. So coverage is deliberately the apps below — accurate and checked
against first-party sources — and it's easy to extend (add a CATALOG entry).

Only plain HTTPS GETs go out (the same kind the self-update check makes), so
there's no package-manager behaviour for endpoint protection to flag.
"""

import json
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import software
from .jobs import JobStore

_jobs = JobStore()

# Cache fetched "latest" versions for the session so a re-check (or a second app
# from the same source) doesn't re-hit the network or burn GitHub's rate limit.
_cache = {}                 # id -> (version|None, error|None, ts)
_TTL_OK = 6 * 3600          # a successful lookup is good for 6h
_TTL_ERR = 5 * 60           # retry a failed lookup sooner


# --------------------------------------------------------------------------- #
# fetch helpers
# --------------------------------------------------------------------------- #
def _get(url, timeout=8, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "Benchly"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def _get_json(url, timeout=8, headers=None):
    return json.loads(_get(url, timeout, headers))


def _gh(repo):
    """Latest non-prerelease tag from a GitHub project's Releases."""
    hdr = {"User-Agent": "Benchly", "Accept": "application/vnd.github+json"}

    def fetch():
        data = _get_json(f"https://api.github.com/repos/{repo}/releases/latest", headers=hdr)
        return data.get("tag_name") or data.get("name")
    return fetch


def _json_pick(url, *path):
    """GET JSON and walk a key/index path to the version string."""
    def fetch():
        d = _get_json(url)
        for key in path:
            d = d[key]
        return d
    return fetch


def _scrape(url, pattern):
    """GET a page/text endpoint and pull the version out with a regex (group 1)."""
    def fetch():
        m = re.search(pattern, _get(url))
        return m.group(1) if m else None
    return fetch


# --------------------------------------------------------------------------- #
# the catalog — official sources only
#   names : lowercase substrings to look for in the installed DisplayName
#   exact : full (lowercase) DisplayName matches, for names too short to substring
#   fetch : returns the latest version string from a first-party source
#   url   : the vendor's official download page (opened on request, never auto-run)
# --------------------------------------------------------------------------- #
CATALOG = [
    # --- GitHub Releases (first-party project repos) ---
    {"id": "notepadpp", "label": "Notepad++", "names": ["notepad++"],
     "fetch": _gh("notepad-plus-plus/notepad-plus-plus"), "url": "https://notepad-plus-plus.org/downloads/"},
    {"id": "vscode", "label": "Visual Studio Code", "names": ["visual studio code"],
     "fetch": _gh("microsoft/vscode"), "url": "https://code.visualstudio.com/Download"},
    {"id": "powertoys", "label": "PowerToys", "names": ["powertoys"],
     "fetch": _gh("microsoft/PowerToys"), "url": "https://github.com/microsoft/PowerToys/releases/latest"},
    {"id": "pwsh", "label": "PowerShell 7", "names": ["powershell 7"],
     "fetch": _gh("PowerShell/PowerShell"), "url": "https://github.com/PowerShell/PowerShell/releases/latest"},
    {"id": "git", "label": "Git for Windows", "exact": ["git"],
     "fetch": _gh("git-for-windows/git"), "url": "https://git-scm.com/download/win"},
    {"id": "obs", "label": "OBS Studio", "names": ["obs studio"],
     "fetch": _gh("obsproject/obs-studio"), "url": "https://obsproject.com/download"},
    {"id": "sharex", "label": "ShareX", "names": ["sharex"],
     "fetch": _gh("ShareX/ShareX"), "url": "https://getsharex.com/"},
    {"id": "greenshot", "label": "Greenshot", "names": ["greenshot"],
     "fetch": _gh("greenshot/greenshot"), "url": "https://getgreenshot.org/downloads/"},
    {"id": "handbrake", "label": "HandBrake", "names": ["handbrake"],
     "fetch": _gh("HandBrake/HandBrake"), "url": "https://handbrake.fr/downloads.php"},
    {"id": "audacity", "label": "Audacity", "names": ["audacity"],
     "fetch": _gh("audacity/audacity"), "url": "https://www.audacityteam.org/download/"},
    {"id": "keepassxc", "label": "KeePassXC", "names": ["keepassxc"],
     "fetch": _gh("keepassxreboot/keepassxc"), "url": "https://keepassxc.org/download/"},
    {"id": "veracrypt", "label": "VeraCrypt", "names": ["veracrypt"],
     "fetch": _gh("veracrypt/VeraCrypt"), "url": "https://www.veracrypt.fr/en/Downloads.html"},
    {"id": "qbittorrent", "label": "qBittorrent", "names": ["qbittorrent"],
     "fetch": _gh("qbittorrent/qBittorrent"), "url": "https://www.qbittorrent.org/download"},
    {"id": "rufus", "label": "Rufus", "names": ["rufus"],
     "fetch": _gh("pbatard/rufus"), "url": "https://rufus.ie/"},
    {"id": "sumatra", "label": "SumatraPDF", "names": ["sumatra"],
     "fetch": _gh("sumatrapdfreader/sumatrapdf"), "url": "https://www.sumatrapdfreader.org/download-free-pdf-viewer"},
    {"id": "signal", "label": "Signal", "names": ["signal"],
     "fetch": _gh("signalapp/Signal-Desktop"), "url": "https://signal.org/download/"},
    {"id": "calibre", "label": "calibre", "names": ["calibre"],
     "fetch": _gh("kovidgoyal/calibre"), "url": "https://calibre-ebook.com/download_windows"},
    {"id": "obsidian", "label": "Obsidian", "names": ["obsidian"],
     "fetch": _gh("obsidianmd/obsidian-releases"), "url": "https://obsidian.md/download"},
    {"id": "winmerge", "label": "WinMerge", "names": ["winmerge"],
     "fetch": _gh("WinMerge/winmerge"), "url": "https://winmerge.org/downloads/"},
    {"id": "joplin", "label": "Joplin", "names": ["joplin"],
     "fetch": _gh("laurent22/joplin"), "url": "https://joplinapp.org/help/install"},

    # --- vendor version endpoints (JSON) ---
    {"id": "chrome", "label": "Google Chrome", "names": ["google chrome"],
     "fetch": _json_pick(
         "https://versionhistory.googleapis.com/v1/chrome/platforms/win64/channels/stable/versions",
         "versions", 0, "version"),
     "url": "https://www.google.com/chrome/"},
    {"id": "firefox", "label": "Mozilla Firefox", "names": ["mozilla firefox"],
     "fetch": _json_pick("https://product-details.mozilla.org/1.0/firefox_versions.json",
                         "LATEST_FIREFOX_VERSION"),
     "url": "https://www.mozilla.org/firefox/new/"},
    {"id": "thunderbird", "label": "Mozilla Thunderbird", "names": ["thunderbird"],
     "fetch": _json_pick("https://product-details.mozilla.org/1.0/thunderbird_versions.json",
                         "LATEST_THUNDERBIRD_VERSION"),
     "url": "https://www.thunderbird.net/"},

    # --- vendor pages (regex) ---
    {"id": "7zip", "label": "7-Zip", "names": ["7-zip"],
     "fetch": _scrape("https://www.7-zip.org/", r"Download 7-Zip ([\d.]+)"),
     "url": "https://www.7-zip.org/download.html"},
    {"id": "vlc", "label": "VLC media player", "names": ["vlc media player"],
     "fetch": _scrape("https://update.videolan.org/vlc/status-win-x64", r"(\d+\.\d+\.\d+)"),
     "url": "https://www.videolan.org/vlc/"},
]


def catalog_size():
    return len(CATALOG)


# --------------------------------------------------------------------------- #
# version handling
# --------------------------------------------------------------------------- #
def _parse_ver(s):
    nums = re.findall(r"\d+", s or "")
    return tuple(int(n) for n in nums[:4]) + (0,) * (4 - len(nums[:4]))


def _norm(v):
    """Trim a tag like 'release-4.6.5' or 'v8.6.2' down to its version number."""
    m = re.search(r"\d[\d.]*", str(v or ""))
    return m.group(0).rstrip(".") if m else None


def _matches(app, entry):
    name = app["name"].lower()
    if any(x == name for x in entry.get("exact", [])):
        return True
    return any(x in name for x in entry.get("names", []))


def _latest(entry):
    """Cached fetch of an entry's latest version. Returns (version|None, error|None)."""
    now = time.time()
    hit = _cache.get(entry["id"])
    if hit:
        ver, err, ts = hit
        if now - ts < (_TTL_OK if ver else _TTL_ERR):
            return ver, err
    try:
        ver = _norm(entry["fetch"]())
        err = None if ver else "no version found"
    except urllib.error.HTTPError as e:
        ver, err = None, "rate-limited" if e.code in (403, 429) else f"HTTP {e.code}"
    except (urllib.error.URLError, TimeoutError, OSError):
        ver, err = None, "couldn't reach source"
    except Exception as e:
        ver, err = None, f"{type(e).__name__}"
    _cache[entry["id"]] = (ver, err, now)
    return ver, err


_STATUS_ORDER = {"update": 0, "unknown": 1, "current": 2}


def _row(entry, app, latest, err):
    cur = app.get("version") or ""
    if err:
        status, note = "unknown", err
    elif not cur:
        status, note = "unknown", "installed version unknown"
    elif latest and _parse_ver(latest) > _parse_ver(cur):
        status, note = "update", ""
    else:
        status, note = "current", ""
    return {
        "name": entry["label"],
        "publisher": app.get("publisher") or "",
        "installed": cur,
        "latest": latest or "",
        "status": status,
        "note": note,
        "url": entry["url"],
    }


# --------------------------------------------------------------------------- #
# job: read installed -> match -> fetch concurrently -> compare
# --------------------------------------------------------------------------- #
def _run_check(job):
    installed = software.get_installed()
    matched = []
    for entry in CATALOG:
        app = next((a for a in installed if _matches(a, entry)), None)
        if app:
            matched.append((entry, app))
    job["total"] = len(matched)
    if not matched:
        job["results"] = []
        return

    results = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(_latest, entry): (entry, app) for entry, app in matched}
        for fut in as_completed(futs):
            entry, app = futs[fut]
            latest, err = fut.result()
            results.append(_row(entry, app, latest, err))
            job["checked"] = len(results)

    results.sort(key=lambda r: (_STATUS_ORDER.get(r["status"], 1), r["name"].lower()))
    job["results"] = results


def start_check():
    job_id = _jobs.start(_run_check, results=None, total=0, checked=0)
    if job_id is None:
        return {"ok": False, "error": "A version check is already running."}
    return {"ok": True, "job": job_id, "catalog": len(CATALOG)}


def get_check(job_id):
    job = _jobs.get(job_id)
    if not job:
        return {"ok": False, "error": "No such job."}
    out = {"ok": True, "done": job["done"], "total": job.get("total", 0),
           "checked": job.get("checked", 0), "results": job.get("results")}
    if job["done"] and job.get("results") is not None:
        out["updates"] = sum(1 for r in job["results"] if r["status"] == "update")
    return out
