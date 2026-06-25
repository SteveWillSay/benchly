"""Kernel minidump triage — pull the bug-check and likely third-party driver out of a BSOD.

`crashes.py` lists the minidumps and reads the System log's WER bugcheck events, but
a Stop code alone rarely names the culprit. The minidump itself carries the list of
modules that were loaded at crash time; the usual BSOD culprit is a third-party `.sys`
driver, not a Windows core component. This module parses the MINIDUMP binary directly
(no debugger, no symbols) to surface those non-Microsoft modules — the names a bench
tech actually acts on (update/roll back/remove that driver).

Pure standard library: we walk the documented MINIDUMP layout with `struct`, bounds-check
every offset against the file size, and degrade gracefully — this parses untrusted binary
that may be truncated or corrupt, so it must never raise. Read-only throughout.
"""

import os
import struct

from .crashes import _BUGCHECKS

_MDMP_SIGNATURE = 0x504D444D            # 'MDMP' little-endian
_MODULE_LIST_STREAM = 4
_EXCEPTION_STREAM = 6

_MODULE_RECORD_SIZE = 108               # sizeof(MINIDUMP_MODULE)
_MAX_READ = 8 * 1024 * 1024             # cap: real kernel minidumps are 256KB–2MB
_MAX_MODULES = 4096                     # sanity bound on a corrupt NumberOfModules
_MAX_SUSPECTS = 15

# Core Windows / Microsoft modules a bench tech can safely ignore — these are NOT the
# culprit worth flagging. Anything else loaded (third-party .sys) is a "suspect".
_MS_MODULES = {
    "ntoskrnl.exe", "ntkrnlmp.exe", "ntkrnlpa.exe", "ntkrpamp.exe",
    "hal.dll", "halmacpi.dll", "halacpi.dll",
    "kdcom.dll", "ci.dll", "clfs.sys", "cng.sys", "msrpc.sys",
    "pshed.dll", "bootvid.dll", "werkernel.sys", "tm.sys",
    "ndis.sys", "netio.sys", "tcpip.sys", "fwpkclnt.sys",
    "fltmgr.sys", "ksecdd.sys", "ksecpkg.sys", "wdf01000.sys",
    "wdfldr.sys", "wfplwfs.sys", "fileinfo.sys", "wcifs.sys",
    "ntfs.sys", "fastfat.sys", "volsnap.sys", "volmgr.sys",
    "volmgrx.sys", "partmgr.sys", "storport.sys", "storahci.sys",
    "disk.sys", "classpnp.sys", "mountmgr.sys", "pci.sys",
    "acpi.sys", "intelpep.sys", "msisadrv.sys", "pdc.sys",
    "win32k.sys", "win32kfull.sys", "win32kbase.sys", "dxgkrnl.sys",
    "dxgmms2.sys", "watchdog.sys", "cdd.dll", "usbhub.sys",
    "usbport.sys", "usbehci.sys", "usbxhci.sys", "usbccgp.sys",
    "hidclass.sys", "hidparse.sys", "kbdclass.sys", "mouclass.sys",
    "afd.sys", "http.sys", "srv2.sys", "srvnet.sys", "mup.sys",
    "rdyboost.sys", "mmcss.sys", "ntosext.sys", "spaceport.sys",
    "cdrom.sys", "null.sys", "beep.sys", "rdpdr.sys", "tdx.sys",
    "luafv.sys", "wof.sys", "bam.sys", "vmbus.sys", "winhvr.sys",
    "ahcache.sys", "pcw.sys", "fvevol.sys", "rdbss.sys", "csc.sys",
    "dfsc.sys", "nsiproxy.sys", "tbs.sys", "umbus.sys",
}

# Prefixes that strongly imply a Microsoft-shipped driver even if not in the set above.
_MS_PREFIXES = ("ms", "win32k", "windows", "microsoft")


def _u32(buf, off):
    """Read a little-endian uint32 at `off`, or None if out of bounds."""
    if off < 0 or off + 4 > len(buf):
        return None
    return struct.unpack_from("<I", buf, off)[0]


def _u64(buf, off):
    if off < 0 or off + 8 > len(buf):
        return None
    return struct.unpack_from("<Q", buf, off)[0]


def _read_minidump_string(buf, rva):
    """A MINIDUMP_STRING: uint32 byte-length, then UTF-16LE chars. → str or None."""
    length = _u32(buf, rva)
    if length is None or length <= 0 or length > 4096:   # names are short; cap it
        return None
    start = rva + 4
    end = start + length
    if end > len(buf):
        return None
    try:
        return buf[start:end].decode("utf-16-le", errors="replace").rstrip("\x00")
    except Exception:
        return None


def _is_suspect(name):
    """True if `name` looks like a third-party driver worth flagging."""
    low = name.lower()
    if low in _MS_MODULES:
        return False
    if low.startswith(_MS_PREFIXES):
        return False
    return True


def _parse_streams(buf):
    """Walk the stream directory → {stream_type: (rva, size)} for streams we want."""
    if len(buf) < 16:
        return None
    if _u32(buf, 0) != _MDMP_SIGNATURE:
        return None
    num_streams = _u32(buf, 8)
    dir_rva = _u32(buf, 12)
    if num_streams is None or dir_rva is None or num_streams > 256:
        return None
    streams = {}
    for i in range(num_streams):
        entry = dir_rva + i * 12
        stream_type = _u32(buf, entry)
        data_size = _u32(buf, entry + 4)
        rva = _u32(buf, entry + 8)
        if stream_type is None or data_size is None or rva is None:
            break
        if stream_type in (_MODULE_LIST_STREAM, _EXCEPTION_STREAM):
            streams[stream_type] = (rva, data_size)
    return streams


def _parse_modules(buf, rva):
    """MINIDUMP_MODULE_LIST → list of base module names.

    Layout walked (offsets within each 108-byte MINIDUMP_MODULE record):
      +0  BaseOfImage    uint64
      +8  SizeOfImage    uint32
      +12 CheckSum       uint32
      +16 TimeDateStamp  uint32
      +20 ModuleNameRva  uint32   <- points at a MINIDUMP_STRING elsewhere in the file
      (then VS_FIXEDFILEINFO + CvRecord/MiscRecord we don't need)
    The list itself is: uint32 NumberOfModules, then the records back to back.
    """
    count = _u32(buf, rva)
    if count is None or count <= 0 or count > _MAX_MODULES:
        return []
    names = []
    base = rva + 4
    for i in range(count):
        rec = base + i * _MODULE_RECORD_SIZE
        if rec + _MODULE_RECORD_SIZE > len(buf):
            break
        name_rva = _u32(buf, rec + 20)
        if name_rva is None:
            continue
        name = _read_minidump_string(buf, name_rva)
        if name:
            names.append(os.path.basename(name.replace("\\", "/")))
    return names


def _parse_bugcheck(buf, rva):
    """Best-effort bug-check code from the MINIDUMP_EXCEPTION_STREAM.

    MINIDUMP_EXCEPTION_STREAM: uint32 ThreadId, uint32 __alignment, then a
    MINIDUMP_EXCEPTION record at +8 whose first uint32 is ExceptionCode. For
    kernel bugcheck dumps the bug-check code is conventionally carried as the
    exception code. We only trust it if it maps to a known Stop code — otherwise
    return None rather than guess (the WER event in crashes.py is authoritative).
    """
    code = _u32(buf, rva + 8)
    if code is None:
        return None
    if (code & 0xFFFFFFFF) in _BUGCHECKS:
        return code & 0xFFFFFFFF
    return None


def analyze_file(path):
    """Parse one minidump → a dict (see `analyze_latest` for the per-dump schema).

    `path` must resolve inside the system Minidump folder — we refuse to read
    arbitrary files. Never raises; returns {'ok': False, 'note': ...} on trouble.
    """
    dump_dir = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Minidump")
    try:
        real = os.path.realpath(path)
        if os.path.commonpath([real, os.path.realpath(dump_dir)]) != os.path.realpath(dump_dir):
            return {"ok": False, "note": "refused: path is outside the Minidump folder"}
    except (ValueError, OSError):
        return {"ok": False, "note": "refused: unresolvable path"}

    try:
        size = os.path.getsize(real)
        with open(real, "rb") as fh:
            buf = fh.read(min(size, _MAX_READ))
    except OSError as e:
        return {"ok": False, "note": f"could not read dump: {e.__class__.__name__}"}

    import datetime
    entry = {
        "file": os.path.basename(real),
        "date": None,
        "bugcheck_hex": None,
        "bugcheck_name": None,
        "suspect_drivers": [],
        "module_count": 0,
    }
    try:
        entry["date"] = datetime.datetime.fromtimestamp(
            os.path.getmtime(real)).strftime("%Y-%m-%d %H:%M")
    except OSError:
        pass

    streams = _parse_streams(buf)
    if streams is None:
        entry["note"] = "not a recognised MINIDUMP file"
        return {"ok": False, "note": entry["note"], **entry}

    if _EXCEPTION_STREAM in streams:
        code = _parse_bugcheck(buf, streams[_EXCEPTION_STREAM][0])
        if code is not None:
            entry["bugcheck_hex"] = f"0x{code:08X}"
            entry["bugcheck_name"] = _BUGCHECKS.get(code)

    if _MODULE_LIST_STREAM in streams:
        modules = _parse_modules(buf, streams[_MODULE_LIST_STREAM][0])
        entry["module_count"] = len(modules)
        seen = set()
        suspects = []
        for name in modules:
            low = name.lower()
            if low in seen:
                continue
            seen.add(low)
            if _is_suspect(name):
                suspects.append(name)
            if len(suspects) >= _MAX_SUSPECTS:
                break
        entry["suspect_drivers"] = suspects

    return {"ok": True, "note": "parsed", **entry}


def analyze_latest(max_dumps=5):
    """Parse up to the newest `max_dumps` kernel minidumps in C:\\Windows\\Minidump.

    Returns:
        {
          "ok": bool,
          "dumps": [ {"file", "date", "bugcheck_hex"|None, "bugcheck_name"|None,
                      "suspect_drivers": [str, ...], "module_count": int}, ... ],
          "note": "<one-line>"
        }
    Never raises — a missing/locked folder or a bad dump yields ok=False / empty.
    """
    dump_dir = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Minidump")
    try:
        if not os.path.isdir(dump_dir):
            return {"ok": False, "dumps": [], "note": f"no Minidump folder at {dump_dir}"}
        files = [f for f in os.listdir(dump_dir) if f.lower().endswith(".dmp")]
    except OSError:
        return {"ok": False, "dumps": [],
                "note": "could not read Minidump folder (admin rights may be required)"}

    if not files:
        return {"ok": False, "dumps": [], "note": "no minidumps found"}

    try:
        files.sort(key=lambda f: os.path.getmtime(os.path.join(dump_dir, f)), reverse=True)
    except OSError:
        files.sort(reverse=True)

    dumps = []
    for f in files[:max_dumps]:
        try:
            result = analyze_file(os.path.join(dump_dir, f))
        except Exception:                                  # never let one dump kill the batch
            result = {"file": f, "date": None, "bugcheck_hex": None, "bugcheck_name": None,
                      "suspect_drivers": [], "module_count": 0, "ok": False}
        result.pop("ok", None)
        result.pop("note", None)
        dumps.append(result)

    parsed = sum(1 for d in dumps if d.get("module_count"))
    note = (f"parsed {parsed} of {len(dumps)} recent dump(s)"
            if parsed else f"found {len(dumps)} dump(s) but could not parse module lists")
    return {"ok": parsed > 0, "dumps": dumps, "note": note}
