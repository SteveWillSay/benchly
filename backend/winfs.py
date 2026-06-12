"""Filesystem helpers — send to Recycle Bin so deletions stay reversible."""

import ctypes
import os
from ctypes import wintypes


class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", ctypes.c_uint16),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", wintypes.LPVOID),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


_FO_DELETE = 3
_FOF_ALLOWUNDO = 0x0040
_FOF_NOCONFIRMATION = 0x0010
_FOF_SILENT = 0x0004
_FOF_NOERRORUI = 0x0400


def recycle(paths):
    """Send paths to the Recycle Bin. Returns (ok_count, error)."""
    if isinstance(paths, str):
        paths = [paths]
    # SHFileOperation requires fully-qualified paths — a relative path would
    # resolve against the process CWD and delete the wrong thing.
    paths = [os.path.abspath(p) for p in paths if p]
    if not paths:
        return 0, None
    # double-null-terminated, null-separated list
    buf = "\0".join(paths) + "\0\0"
    op = _SHFILEOPSTRUCTW()
    op.wFunc = _FO_DELETE
    op.pFrom = buf
    op.fFlags = _FOF_ALLOWUNDO | _FOF_NOCONFIRMATION | _FOF_SILENT | _FOF_NOERRORUI
    try:
        rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        if rc != 0:
            return 0, f"Shell delete failed (code {rc})."
        return len(paths), None
    except Exception as e:
        return 0, str(e)
