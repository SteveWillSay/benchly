"""Check for a newer Benchly release.

Reads a GitHub "owner/repo" from settings (key `update_repo`) and queries the
Releases API for the latest tag, comparing it against the running version. No
auto-download: it reports whether an update exists and links to the release page,
which is the honest, low-risk option until releases are actually published.
"""

import json
import re
import urllib.error
import urllib.request

from . import settings

_API = "https://api.github.com/repos/{repo}/releases/latest"

# Default release source; overridable via the `update_repo` setting.
_DEFAULT_REPO = "SteveWillSay/benchly"


def _parse_ver(s):
    """('1', '8', '0') tuple from a tag like 'v1.8.0' / '1.8'."""
    nums = re.findall(r"\d+", s or "")
    return tuple(int(n) for n in nums[:3]) + (0,) * (3 - len(nums[:3]))


def check_update(current_version):
    repo = (settings.get("update_repo") or _DEFAULT_REPO).strip().strip("/")
    if not repo or "/" not in repo:
        return {"ok": True, "configured": False,
                "message": "No update source set. Add a GitHub “owner/repo” in Settings to enable update checks.",
                "current": current_version}
    if not re.match(r"^[\w.-]+/[\w.-]+$", repo):
        return {"ok": False, "error": "Update repo must look like “owner/repo”."}

    req = urllib.request.Request(
        _API.format(repo=repo),
        headers={"User-Agent": "Benchly", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"ok": True, "configured": True, "reachable": False,
                    "message": f"No published releases found for {repo}.", "current": current_version}
        return {"ok": False, "error": f"GitHub returned HTTP {e.code}."}
    except Exception as e:
        return {"ok": False, "error": f"Couldn't reach the update server: {e}"}

    tag = data.get("tag_name") or ""
    latest = _parse_ver(tag)
    cur = _parse_ver(current_version)
    newer = latest > cur
    asset = None
    for a in data.get("assets", []):
        name = (a.get("name") or "").lower()
        if name.endswith(".exe"):
            asset = a.get("browser_download_url")
            break
    return {
        "ok": True,
        "configured": True,
        "reachable": True,
        "current": current_version,
        "latest": tag or "unknown",
        "newer": newer,
        "url": data.get("html_url"),
        "asset": asset,
        "notes": (data.get("body") or "")[:1500],
        "published": (data.get("published_at") or "")[:10],
    }
