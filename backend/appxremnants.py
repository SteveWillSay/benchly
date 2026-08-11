"""Find remnants of old Store / AppX (UWP) applications.

Read-first: reports the leftovers that uninstalled or half-removed packaged apps
leave behind, so a technician can reclaim the space or clear a broken registration.
It never removes anything on its own.

Two reliable kinds of remnant:
  * **Orphaned per-user data folders** — `%LOCALAPPDATA%\\Packages\\<PackageFamilyName>`
    directories whose package is no longer registered for the user (the classic
    space-eating leftover). Removable to the Recycle Bin (reversible).
  * **Broken package registrations** — `Get-AppxPackage` entries whose install files
    are gone, or whose Status is not "Ok": Windows still lists them as installed when
    they really aren't. Clearable with `Remove-AppxPackage` (admin for all-users).

(Orphaned `%ProgramFiles%\\WindowsApps` install dirs are deliberately out of scope:
they're protected, and resource/dependency sub-packages make orphan detection there
unreliable — so we don't guess.)
"""

import ctypes
import os
import re
from datetime import datetime

# A real AppX PackageFamilyName ends in "_<13-char publisher hash>" (e.g.
# "Microsoft.BingWeather_8wekyb3d8bbwe"). This distinguishes genuine Store-app
# data folders from the OTHER things that live in %LOCALAPPDATA%\Packages —
# browser AppContainer sandbox profiles (cr.sb.*), IE's "windows_ie_ac_001",
# and similar isolation folders that are NOT app remnants and must not be flagged.
_PFN_RE = re.compile(r"^.+_[a-z0-9]{13}$")

from .ps import ps_json, run_ps, as_list
from . import winfs

try:
    from .debloat import _BLOAT, _OPTIONAL   # reuse the friendly-name maps
except Exception:                             # pragma: no cover
    _BLOAT, _OPTIONAL = {}, {}


def _is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _dir_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def _fmt_ts(ts):
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except (OSError, ValueError, OverflowError):
        return ""


def _friendly(pfn):
    """A human name for a PackageFamilyName ('Microsoft.BingWeather_8we…' -> 'Weather')."""
    name = (pfn or "").split("_")[0]
    if name in _BLOAT:
        return _BLOAT[name]
    if name in _OPTIONAL:
        return _OPTIONAL[name]
    return name.split(".")[-1] if "." in name else (name or pfn)


def _pkg_roots():
    """The only directories a remnant folder is ever allowed to be removed from."""
    roots = []
    for var in ("LOCALAPPDATA", "ProgramData"):
        base = os.environ.get(var)
        if base:
            p = os.path.join(base, "Packages")
            if os.path.isdir(p):
                try:
                    roots.append(os.path.realpath(p))
                except OSError:
                    pass
    return roots


# --------------------------------------------------------------------------- #
# scan
# --------------------------------------------------------------------------- #
def scan():
    admin = _is_admin()
    scope = "-AllUsers " if admin else ""
    rows = as_list(ps_json(
        f"Get-AppxPackage {scope}-ErrorAction SilentlyContinue | "
        "Select-Object Name,PackageFamilyName,PackageFullName,InstallLocation,"
        "@{n='Status';e={[string]$_.Status}}", timeout=120))

    installed_pfn, installed_full, broken = set(), set(), []
    for r in rows:
        if not isinstance(r, dict):
            continue
        pfn = (r.get("PackageFamilyName") or "").strip()
        full = (r.get("PackageFullName") or "").strip()
        loc = (r.get("InstallLocation") or "").strip()
        status = (r.get("Status") or "").strip()
        if pfn:
            installed_pfn.add(pfn.lower())
        if full:
            installed_full.add(full.lower())
        loc_missing = (not loc) or (not os.path.isdir(loc))
        bad_status = bool(status) and status.lower() != "ok"
        if loc_missing or bad_status:
            reasons = []
            if loc_missing:
                reasons.append("install files missing")
            if bad_status:
                reasons.append(f"status: {status}")
            broken.append({
                "name": (r.get("Name") or _friendly(pfn)),
                "family": pfn,
                "full_name": full,
                "location": loc or "—",
                "status": status or "—",
                "reason": " · ".join(reasons),
            })

    # orphaned per-user data folders
    orphan_data = []
    la = os.environ.get("LOCALAPPDATA")
    pkg_dir = os.path.join(la, "Packages") if la else None
    if pkg_dir and os.path.isdir(pkg_dir):
        try:
            for e in os.scandir(pkg_dir):
                try:
                    if not e.is_dir() or e.name.lower() in installed_pfn:
                        continue
                    if not _PFN_RE.match(e.name):   # skip non-AppX AppContainer folders
                        continue
                    orphan_data.append({
                        "name": e.name,
                        "friendly": _friendly(e.name),
                        "path": e.path,
                        "size": _dir_size(e.path),
                        "modified": _fmt_ts(e.stat().st_mtime),
                    })
                except OSError:
                    continue
        except OSError:
            pass
    orphan_data.sort(key=lambda x: x["size"], reverse=True)
    broken.sort(key=lambda x: x["name"].lower())

    return {
        "ok": True,
        "is_admin": admin,
        "orphan_data": orphan_data,
        "broken": broken,
        "reclaimable": sum(x["size"] for x in orphan_data),
    }


# --------------------------------------------------------------------------- #
# guarded actions
# --------------------------------------------------------------------------- #
def _within(child, root):
    try:
        return os.path.commonpath([child, root]) == root and child != root
    except ValueError:   # different drive
        return False


def remove_folders(paths):
    """Recycle-Bin the given orphaned data folders — but ONLY if each resolves to a
    path strictly inside %LOCALAPPDATA%\\Packages (or %ProgramData%\\Packages).
    realpath() collapses junctions, so a reparse point can't escape the scope."""
    if isinstance(paths, str):
        paths = [paths]
    roots = _pkg_roots()
    ok_paths, blocked = [], []
    for p in (paths or []):
        if not p:
            continue
        try:
            rp = os.path.realpath(p)
        except OSError:
            blocked.append(p)
            continue
        if any(_within(rp, root) for root in roots):
            ok_paths.append(rp)
        else:
            blocked.append(p)
    if blocked:
        return {"ok": False,
                "error": "Refused: only orphaned Store-app data folders under Packages can be removed.",
                "blocked": blocked[:10]}
    n, err = winfs.recycle(ok_paths)
    return {"ok": err is None, "recycled": n, "error": err}


def remove_registration(full_names):
    """Clear a broken package registration via Remove-AppxPackage (all-users if elevated)."""
    if isinstance(full_names, str):
        full_names = [full_names]
    all_users = "-AllUsers " if _is_admin() else ""
    removed, errors = [], []
    for fn in (full_names or []):
        if not fn:
            continue
        safe = str(fn).replace("'", "''")   # single-quote escaping (invariant)
        out = run_ps(f"try {{ Remove-AppxPackage {all_users}-Package '{safe}' -ErrorAction Stop; 'OK' }} "
                     "catch { 'ERR: ' + $_.Exception.Message }", timeout=90) or ""
        if "OK" in out:
            removed.append(fn)
        else:
            errors.append(f"{fn.split('_')[0]}: {out.split('ERR:', 1)[-1].strip()[:100]}")
    return {"ok": True, "removed": len(removed), "errors": errors}
