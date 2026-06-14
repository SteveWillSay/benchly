"""Check for, download and apply Benchly updates.

Reads a GitHub "owner/repo" from settings (key `update_repo`, falling back to a
baked-in default) and asks the Releases API for the latest tag. If it's newer it
can download the right asset and apply it:

  * **Installed** build (set up via the Inno installer) → download the new
    Setup.exe and run it silently; Inno closes Benchly, updates it in place and
    relaunches it.
  * **Portable** build (single exe) → download the new exe and hand off to a small
    detached helper that waits for Benchly to exit, swaps the file and relaunches.

Downloads are verified against the release's SHA256SUMS.txt when present. Nothing
is downloaded or run without the user clicking "Download & install".
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import winreg

from . import settings
from .jobs import JobStore

_API = "https://api.github.com/repos/{repo}/releases/latest"

# Default release source; overridable via the `update_repo` setting.
_DEFAULT_REPO = "SteveWillSay/benchly"

# Inno Setup uninstall key for this AppId (see installer.iss)
_UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{B7E62A41-9C1D-4D2E-A9F3-BENCHLY100}_is1"

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000

_jobs = JobStore()
_staged = {}   # details of the last successful download, for apply_update()


# --------------------------------------------------------------------------- #
# version + release lookup
# --------------------------------------------------------------------------- #
def _parse_ver(s):
    nums = re.findall(r"\d+", s or "")
    return tuple(int(n) for n in nums[:3]) + (0,) * (3 - len(nums[:3]))


def _repo():
    return (settings.get("update_repo") or _DEFAULT_REPO).strip().strip("/")


def check_update(current_version):
    repo = _repo()
    if not repo or not re.match(r"^[\w.-]+/[\w.-]+$", repo):
        return {"ok": True, "configured": False,
                "message": "No update source set. Add a GitHub “owner/repo” in Settings to enable update checks.",
                "current": current_version}

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
    assets = {a.get("name", ""): a.get("browser_download_url") for a in data.get("assets", [])}
    portable = next((u for n, u in assets.items()
                     if n.lower().endswith(".exe") and "setup" not in n.lower()), None)
    installer = next((u for n, u in assets.items()
                      if n.lower().endswith(".exe") and "setup" in n.lower()), None)
    checksums = assets.get("SHA256SUMS.txt")

    mode = _install_mode()[0]
    # we always update by swapping the portable exe in place
    can_apply = bool(getattr(sys, "frozen", False)) and portable is not None

    return {
        "ok": True,
        "configured": True,
        "reachable": True,
        "current": current_version,
        "latest": tag or "unknown",
        "newer": _parse_ver(tag) > _parse_ver(current_version),
        "url": data.get("html_url"),
        "asset_portable": portable,
        "asset_installer": installer,
        "asset_checksums": checksums,
        "mode": mode,
        "can_apply": can_apply,
        "notes": (data.get("body") or "")[:1500],
        "published": (data.get("published_at") or "")[:10],
    }


# --------------------------------------------------------------------------- #
# install-type detection
# --------------------------------------------------------------------------- #
def _install_location():
    for root, extra in ((winreg.HKEY_CURRENT_USER, 0),
                        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY),
                        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY)):
        try:
            k = winreg.OpenKey(root, _UNINSTALL_KEY, 0, winreg.KEY_READ | extra)
            try:
                loc, _ = winreg.QueryValueEx(k, "InstallLocation")
                if loc:
                    return loc.rstrip("\\")
            finally:
                winreg.CloseKey(k)
        except OSError:
            continue
    return None


def _install_mode():
    """('installed'|'portable'|'source', exe_path, dir)."""
    if not getattr(sys, "frozen", False):
        return ("source", None, None)
    exe = sys.executable
    exedir = os.path.dirname(exe).rstrip("\\")
    loc = _install_location()
    if loc and os.path.normcase(loc) == os.path.normcase(exedir):
        return ("installed", exe, loc)
    return ("portable", exe, exedir)


# --------------------------------------------------------------------------- #
# download (background job) + verify
# --------------------------------------------------------------------------- #
def _expected_hash(checksums_url, filename):
    if not checksums_url:
        return None
    try:
        req = urllib.request.Request(checksums_url, headers={"User-Agent": "Benchly"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode("utf-8", "replace")
        for line in text.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == filename:
                return parts[0].lower()
    except Exception:
        return None
    return None


def _run_download(job):
    url = job["url"]
    filename = url.split("/")[-1].split("?")[0]
    dest = os.path.join(tempfile.gettempdir(), filename)
    job["stage"] = "downloading"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Benchly"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            job["total"] = total
            got = 0
            h = hashlib.sha256()
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    h.update(chunk)
                    got += len(chunk)
                    job["got"] = got
                    job["progress"] = int(got / total * 100) if total else 0
    except Exception as e:
        job["error"] = f"Download failed: {e}"
        return

    job["stage"] = "verifying"
    expected = _expected_hash(job.get("checksums"), filename)
    if expected and h.hexdigest().lower() != expected:
        try:
            os.remove(dest)
        except OSError:
            pass
        job["error"] = "Downloaded file failed its checksum — update cancelled."
        return

    _staged.clear()
    _staged.update({"path": dest, "mode": job["mode"], "target": job["target"], "verified": bool(expected)})
    job["stage"] = "ready"
    job["progress"] = 100
    job["ok"] = True


def download_update():
    mode, exe, _ = _install_mode()
    if mode == "source":
        return {"ok": False, "error": "Running from source — update the working tree with git instead."}
    info = check_update("0.0.0")  # just to fetch asset URLs
    if not info.get("ok") or not info.get("configured") or not info.get("reachable"):
        return {"ok": False, "error": info.get("message") or info.get("error") or "No release available."}
    # Always update by swapping the single exe in place — works the same for the
    # portable build and an installed one, and avoids the installer's unreliable
    # "close the running app" step.
    url = info["asset_portable"]
    if not url:
        return {"ok": False, "error": "The latest release has no portable download to update from."}
    job_id = _jobs.start(_run_download, url=url, mode=mode, target=exe,
                         checksums=info.get("asset_checksums"),
                         progress=0, stage="starting", ok=False, error=None,
                         got=0, total=0)
    if job_id is None:
        return {"ok": False, "error": "A download is already running."}
    return {"ok": True, "job": job_id, "mode": mode}


def update_status(job_id):
    job = _jobs.get(job_id)
    if not job:
        return {"ok": False, "error": "No such job."}
    return {"ok": True, "done": job["done"], "progress": job.get("progress", 0),
            "stage": job.get("stage"), "ready": bool(job.get("ok")), "error": job.get("error"),
            "got_mb": round(job.get("got", 0) / 1048576, 1),
            "total_mb": round(job.get("total", 0) / 1048576, 1)}


# --------------------------------------------------------------------------- #
# apply
# --------------------------------------------------------------------------- #
_SWAP_BAT = r"""@echo off
set n=0
:retry
set /a n+=1
move /y "__NEW__" "__TARGET__" >nul 2>&1 && goto done
if %n% geq 180 exit /b 1
timeout /t 1 /nobreak >nul
goto retry
:done
start "" "__TARGET__"
del "%~f0"
"""


def _needs_admin_to_write(target):
    """A target under Program Files needs elevation to overwrite; LocalAppData doesn't."""
    pf = [os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", ""),
          os.environ.get("ProgramW6432", "")]
    t = os.path.normcase(os.path.abspath(target))
    return any(p and t.startswith(os.path.normcase(p) + os.sep) for p in pf)


def apply_update():
    """Swap the new exe in over the running one, then quit so it can complete.

    The same helper handles the portable build and an installed one — it waits for
    Benchly to exit (the exe unlocks), moves the new file into place and relaunches.
    An installed copy under Program Files needs the helper elevated; the usual
    per-user install (under %LocalAppData%) does not.
    """
    if not _staged.get("path") or not os.path.isfile(_staged["path"]):
        return {"ok": False, "error": "No update has been downloaded."}
    new = _staged["path"]
    target = _staged["target"]
    if not target or not os.path.isfile(target):
        return {"ok": False, "error": "Couldn't find the running program to update."}
    try:
        bat = os.path.join(tempfile.gettempdir(), "benchly-update.cmd")
        with open(bat, "w", encoding="mbcs", errors="replace") as f:
            f.write(_SWAP_BAT.replace("__NEW__", new).replace("__TARGET__", target))
        elevate = _needs_admin_to_write(target) and not _is_elevated()
        if elevate:
            # relaunch the helper through UAC so it can write into Program Files
            ps = (f"Start-Process -FilePath cmd.exe -ArgumentList '/c',\"{bat}\" "
                  "-Verb RunAs -WindowStyle Hidden")
            subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                             creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP, close_fds=True)
        else:
            subprocess.Popen(["cmd", "/c", bat],
                             creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
                             close_fds=True)
        # Give the bridge a moment to return, then exit so the swap can happen.
        threading.Timer(1.0, lambda: os._exit(0)).start()
        return {"ok": True, "mode": "portable", "elevate": elevate}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _is_elevated():
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False
