"""Error-code decoder — paste any hex/decimal Windows status code, get plain English.

Decodes against the OS itself (FormatMessage) rather than a shipped, staleable header
table, then adds the HRESULT structure breakdown (severity / facility / code) and
cross-references the Windows Update advice table and known bug-check names.
"""

import ctypes
import re

from . import wuhistory
from .crashes import _BUGCHECKS

# HRESULT/SCODE facility field (bits 16-26). The common ones a tech meets.
_FACILITIES = {
    0: "NULL (general)", 1: "RPC", 2: "DISPATCH", 3: "STORAGE", 4: "ITF (interface)",
    7: "WIN32", 8: "WINDOWS", 9: "SSPI/SECURITY", 10: "CONTROL", 11: "CERT",
    12: "INTERNET", 13: "MEDIASERVER", 14: "MSMQ", 15: "SETUPAPI", 16: "SCARD",
    17: "COMPLUS", 18: "AAF", 19: "URT", 20: "ACS", 21: "DPLAY", 22: "UMI",
    25: "WINDOWS_CE", 26: "HTTP", 31: "USERMODE_FILTER_MANAGER", 0x8: "WINDOWS",
}

_FORMAT_FROM_SYSTEM = 0x00001000
_FORMAT_FROM_HMODULE = 0x00000800
_FORMAT_IGNORE_INSERTS = 0x00000200

_k32 = ctypes.windll.kernel32
_k32.FormatMessageW.restype = ctypes.c_uint
_k32.FormatMessageW.argtypes = [ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint,
                                ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
_k32.GetModuleHandleW.restype = ctypes.c_void_p
_k32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]


def _to_int(raw):
    """Parse '0x80070005', '80070005', '-2147024891', or '2147942405' → unsigned int32."""
    if raw is None:
        return None
    s = str(raw).strip().replace(" ", "")
    try:
        if s.lower().startswith("0x"):
            v = int(s, 16)
        elif re.fullmatch(r"-?\d+", s):
            v = int(s, 10)
        elif re.fullmatch(r"[0-9a-fA-F]+", s):     # bare hex (no 0x)
            v = int(s, 16)
        else:
            return None
    except ValueError:
        return None
    return v & 0xFFFFFFFF


def _system_message(code, module=None):
    """FormatMessageW lookup. `module` = an HMODULE (e.g. ntdll) for NTSTATUS text."""
    flags = _FORMAT_FROM_SYSTEM | _FORMAT_IGNORE_INSERTS
    if module:
        flags |= _FORMAT_FROM_HMODULE
    buf = ctypes.create_unicode_buffer(4096)
    n = _k32.FormatMessageW(flags, module, code, 0, buf, len(buf), None)
    return buf.value.strip() if n else ""


def _ntdll_handle():
    return _k32.GetModuleHandleW("ntdll.dll")


def decode(raw):
    code = _to_int(raw)
    if code is None:
        return {"ok": False, "error": "Enter a status code — hex like 0x80070005, or a decimal."}

    severity = "Failure" if (code >> 31) & 1 else "Success"
    facility = (code >> 16) & 0x1FFF
    code_part = code & 0xFFFF
    interps = []   # [{source, text}]

    # As a plain Win32 error (and as the low word of a FACILITY_WIN32 HRESULT).
    win32 = _system_message(code)
    if win32:
        interps.append({"source": "Win32 / system", "text": win32})
    if facility == 7 and code_part and (code >> 31) & 1:
        low = _system_message(code_part)
        if low and low != win32:
            interps.append({"source": f"Win32 error {code_part} (from FACILITY_WIN32 HRESULT)", "text": low})

    # As NTSTATUS (0x8/0xA/0xC top nibble) — text lives in ntdll, not the system table.
    if (code >> 28) in (0x8, 0xA, 0xC):
        ntdll = _ntdll_handle()
        nt = _system_message(code, module=ntdll) if ntdll else ""
        if nt and not any(nt == i["text"] for i in interps):
            interps.append({"source": "NTSTATUS (ntdll)", "text": nt})

    # Windows Update advice — only on a real table hit, not the catch-all fallback.
    if code in wuhistory._HRESULT and code != 0:
        meaning, advice = wuhistory._HRESULT[code]
        interps.append({"source": "Windows Update", "text": meaning + (f" — {advice}" if advice else "")})

    # Bug-check number? (only meaningful for small codes, but harmless to note)
    bc = _BUGCHECKS.get(code)
    if bc:
        interps.append({"source": "Bug-check (Stop code)", "text": bc})

    return {
        "ok": True,
        "input": str(raw).strip(),
        "hex": f"0x{code:08X}",
        "decimal": code,
        "severity": severity,
        "facility": facility,
        "facility_name": _FACILITIES.get(facility, f"facility {facility}"),
        "code_part": code_part,
        "interpretations": interps,
    }
