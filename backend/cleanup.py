"""Disk cleanup — safe junk, large files, and duplicate finder.

File-scoped only (no registry). Junk targets are well-understood caches/temp.
Large/duplicate deletions go to the Recycle Bin (reversible) via winfs.recycle.
"""

import ctypes
import glob
import hashlib
import os

from .jobs import JobStore
from . import winfs


_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def _is_reparse(entry):
    """True for junctions / symlinks / mount points. On Windows a directory
    junction is NOT reported by is_symlink(), so we must check the attribute —
    otherwise a cleanup walk could follow a junction OUT of the intended tree."""
    try:
        if entry.is_symlink():
            return True
        return bool(entry.stat(follow_symlinks=False).st_file_attributes & _FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        return True   # if we can't tell, treat as a reparse point and skip it


def _dir_size_and_files(path, exts=None):
    total, files = 0, []
    stack = [path]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for e in it:
                    try:
                        if _is_reparse(e):
                            continue
                        if e.is_file(follow_symlinks=False):
                            sz = e.stat(follow_symlinks=False).st_size
                            total += sz
                            files.append(e.path)
                        elif e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                    except OSError:
                        continue
        except OSError:
            continue
    return total, files


def _local(*parts):
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), *parts)


def scan_junk():
    """Reclaimable space per category — no deletion, just measurement."""
    win = os.environ.get("SystemRoot", r"C:\Windows")
    targets = [
        ("user_temp", "User temp files", os.environ.get("TEMP", "")),
        ("win_temp", "Windows temp files", os.path.join(win, "Temp")),
        ("wu_cache", "Windows Update cache", os.path.join(win, "SoftwareDistribution", "Download")),
        ("thumbs", "Thumbnail cache", _local("Microsoft", "Windows", "Explorer")),
        ("chrome_cache", "Chrome cache", _local("Google", "Chrome", "User Data", "Default", "Cache")),
        ("edge_cache", "Edge cache", _local("Microsoft", "Edge", "User Data", "Default", "Cache")),
        ("crash_dumps", "Crash dumps", _local("CrashDumps")),
        ("delivery_opt", "Delivery Optimization files", os.path.join(win, "SoftwareDistribution", "DeliveryOptimization")),
    ]
    cats = []
    for cid, label, path in targets:
        if path and os.path.isdir(path):
            size, _ = _dir_size_and_files(path)
            if size > 0:
                cats.append({"id": cid, "label": label, "path": path, "size": size})
    # Recycle Bin (measured via shell)
    rb = _recycle_bin_size()
    if rb > 0:
        cats.append({"id": "recycle_bin", "label": "Recycle Bin", "path": "", "size": rb})
    cats.sort(key=lambda c: c["size"], reverse=True)
    return {"categories": cats, "total": sum(c["size"] for c in cats)}


_CLEAN_PATHS = {
    "user_temp": lambda: [os.environ.get("TEMP", "")],
    "win_temp": lambda: [os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Temp")],
    "wu_cache": lambda: [os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "SoftwareDistribution", "Download")],
    "thumbs": lambda: glob.glob(_local("Microsoft", "Windows", "Explorer", "thumbcache_*.db")),
    "chrome_cache": lambda: [_local("Google", "Chrome", "User Data", "Default", "Cache")],
    "edge_cache": lambda: [_local("Microsoft", "Edge", "User Data", "Default", "Cache")],
    "crash_dumps": lambda: [_local("CrashDumps")],
    "delivery_opt": lambda: [os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "SoftwareDistribution", "DeliveryOptimization")],
}


def clean_junk(category_ids):
    """Delete the contents of the chosen junk categories. Temp/cache files are
    deleted directly (they are caches); the Recycle Bin is emptied via shell."""
    freed = 0
    errors = []
    for cid in category_ids:
        if cid == "recycle_bin":
            freed += _recycle_bin_size()
            _empty_recycle_bin()
            continue
        for root in _CLEAN_PATHS.get(cid, lambda: [])():
            if not root or not os.path.isdir(root):
                # could be a glob of files (thumbs)
                if root and os.path.isfile(root):
                    try:
                        freed += os.path.getsize(root); os.remove(root)
                    except OSError:
                        pass
                continue
            freed += _purge_dir_contents(root, errors)
    return {"ok": True, "freed": freed, "errors": errors[:8]}


def _safe_rmtree(path):
    """Recursively delete, refusing to descend THROUGH any reparse point — a
    junction planted inside a cache dir must never redirect the delete outside
    the tree (shutil.rmtree would walk into it)."""
    try:
        with os.scandir(path) as it:
            for e in it:
                try:
                    if _is_reparse(e):
                        # remove the link/junction itself, never its target's contents
                        if e.is_dir(follow_symlinks=False):
                            os.rmdir(e.path)
                        else:
                            os.remove(e.path)
                    elif e.is_dir(follow_symlinks=False):
                        _safe_rmtree(e.path)
                    else:
                        os.remove(e.path)
                except OSError:
                    pass
        os.rmdir(path)
    except OSError:
        pass


def _purge_dir_contents(root, errors):
    freed = 0
    for entry in list(os.scandir(root)) if os.path.isdir(root) else []:
        try:
            if _is_reparse(entry):
                continue   # never delete through a junction/symlink out of the tree
            if entry.is_file(follow_symlinks=False):
                sz = entry.stat(follow_symlinks=False).st_size
                os.remove(entry.path)
                freed += sz
            elif entry.is_dir(follow_symlinks=False):
                sz, _ = _dir_size_and_files(entry.path)
                _safe_rmtree(entry.path)
                freed += sz
        except OSError:
            errors.append(f"in use: {os.path.basename(entry.path)}")
    return freed


# ---- large files ----------------------------------------------------------------

def find_large_files(path, min_mb=100, top=40):
    if not os.path.isdir(path):
        return {"ok": False, "error": "Not a folder."}
    _remember_root(path)
    threshold = min_mb * 1024 * 1024
    _, files = _dir_size_and_files(path)
    sized = []
    for f in files:
        try:
            sz = os.path.getsize(f)
            if sz >= threshold:
                sized.append({"path": f, "size": sz})
        except OSError:
            continue
    sized.sort(key=lambda x: x["size"], reverse=True)
    return {"ok": True, "files": sized[:top], "count": len(sized)}


# ---- duplicate finder (background job: hashing is slow) -------------------------

_dup_store = JobStore()


def start_duplicate_scan(path):
    if not os.path.isdir(path):
        return {"ok": False, "error": "Not a folder."}
    _remember_root(path)
    job_id = _dup_store.start(_dup_run, path=path, groups=[], scanned=0, phase="listing")
    if job_id is None:
        return {"ok": False, "error": "A scan is already running."}
    return {"ok": True, "job": job_id}


def _dup_run(job):
    _, files = _dir_size_and_files(job["path"])
    by_size = {}
    for f in files:
        try:
            sz = os.path.getsize(f)
            if sz >= 1024 * 1024:           # ignore < 1MB
                by_size.setdefault(sz, []).append(f)
        except OSError:
            continue
    candidates = [grp for grp in by_size.values() if len(grp) > 1]
    job["phase"] = "hashing"
    by_hash = {}
    for grp in candidates:
        for f in grp:
            job["scanned"] += 1
            h = _hash(f)
            if h:
                by_hash.setdefault(h, []).append(f)
    groups = []
    for h, paths in by_hash.items():
        if len(paths) > 1:
            try:
                size = os.path.getsize(paths[0])
            except OSError:
                size = 0
            groups.append({"size": size, "count": len(paths),
                           "wasted": size * (len(paths) - 1),
                           "files": sorted(paths)})
    groups.sort(key=lambda g: g["wasted"], reverse=True)
    job["groups"] = groups[:80]


def get_duplicate_job(job_id):
    job = _dup_store.get(job_id)
    if not job:
        return {"ok": False, "error": "No such scan."}
    groups = list(job["groups"])   # snapshot — the runner thread mutates this
    return {"ok": True, "done": job["done"], "phase": job["phase"],
            "scanned": job["scanned"], "groups": groups,
            "wasted": sum(g["wasted"] for g in groups)}


def _hash(path, chunk=1 << 20):
    try:
        h = hashlib.sha1()
        with open(path, "rb") as f:
            while True:
                b = f.read(chunk)
                if not b:
                    break
                h.update(b)
        return h.hexdigest()
    except OSError:
        return None


# ---- delete scoping -------------------------------------------------------------
# recycle_files is a privileged delete primitive, so it is constrained to paths that
# descend from a folder the user actually scanned this session (the large-file or
# duplicate finders record their root below). System / Program Files locations are
# refused regardless. This bounds the blast radius if any future UI/logic bug were to
# reach the bridge — today the UI only ever passes back user-chosen scan results.
_scan_roots = set()


def _remember_root(path):
    try:
        _scan_roots.add(os.path.realpath(path))
    except OSError:
        pass


def _protected_roots():
    roots = []
    for var in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        v = os.environ.get(var)
        if v:
            try:
                roots.append(os.path.realpath(v))
            except OSError:
                pass
    return roots


def _within(child, root):
    try:
        return os.path.commonpath([child, root]) == root
    except ValueError:   # different drive — commonpath raises
        return False


def _deletable(p):
    """A path may be recycled only if it resolves inside a scanned root and is not a
    protected system location. realpath() collapses junctions/symlinks, so a reparse
    point pointing outside a scanned root can't slip through."""
    if not _scan_roots:
        return False
    try:
        rp = os.path.realpath(p)
    except OSError:
        return False
    if any(rp == pr or _within(rp, pr) for pr in _protected_roots()):
        return False
    return any(_within(rp, root) for root in _scan_roots)


def recycle_files(paths):
    if isinstance(paths, str):
        paths = [paths]
    paths = [p for p in (paths or []) if p]
    blocked = [p for p in paths if not _deletable(p)]
    if blocked:
        return {"ok": False,
                "error": "Refused: one or more paths are outside a folder you scanned this "
                         "session, or are protected system locations. Re-scan the folder first.",
                "blocked": blocked[:10]}
    n, err = winfs.recycle(paths)
    return {"ok": err is None, "recycled": n, "error": err}


# ---- recycle bin shell helpers --------------------------------------------------

class _SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint32), ("i64Size", ctypes.c_int64),
                ("i64NumItems", ctypes.c_int64)]


def _recycle_bin_size():
    try:
        info = _SHQUERYRBINFO()
        info.cbSize = ctypes.sizeof(info)
        if ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info)) == 0:
            return max(0, info.i64Size)
    except Exception:
        pass
    return 0


def _empty_recycle_bin():
    try:
        # SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x1 | 0x2 | 0x4)
    except Exception:
        pass
