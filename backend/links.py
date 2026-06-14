"""Negotiated-vs-capable — the silent performance losses.

Right now this covers the most common, most testable one: a display running below
its best refresh rate (the classic "I bought a 144 Hz monitor and Windows left it at
60"). It reads each monitor's current mode and the fastest mode available at that same
resolution, and flags the gap. Read-only.
"""

import ctypes
from ctypes import wintypes

_ENUM_CURRENT = -1


class _DEVMODE(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", ctypes.c_wchar * 32),
        ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD),
        ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD),
        ("dmFields", wintypes.DWORD),
        ("dmOrientation", ctypes.c_short),
        ("dmPaperSize", ctypes.c_short),
        ("dmPaperLength", ctypes.c_short),
        ("dmPaperWidth", ctypes.c_short),
        ("dmScale", ctypes.c_short),
        ("dmCopies", ctypes.c_short),
        ("dmDefaultSource", ctypes.c_short),
        ("dmPrintQuality", ctypes.c_short),
        ("dmColor", ctypes.c_short),
        ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", ctypes.c_wchar * 32),
        ("dmLogPixels", wintypes.WORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFlags", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),
        ("dmICMMethod", wintypes.DWORD),
        ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD),
        ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD),
        ("dmReserved2", wintypes.DWORD),
        ("dmPanningWidth", wintypes.DWORD),
        ("dmPanningHeight", wintypes.DWORD),
    ]


class _DISPLAY_DEVICE(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("DeviceName", ctypes.c_wchar * 32),
        ("DeviceString", ctypes.c_wchar * 128),
        ("StateFlags", wintypes.DWORD),
        ("DeviceID", ctypes.c_wchar * 128),
        ("DeviceKey", ctypes.c_wchar * 128),
    ]


def display_links():
    user32 = ctypes.windll.user32
    monitors = []
    flags = []
    i = 0
    while True:
        dd = _DISPLAY_DEVICE()
        dd.cb = ctypes.sizeof(dd)
        if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            break
        i += 1
        if not (dd.StateFlags & 0x1):       # DISPLAY_DEVICE_ACTIVE
            continue
        cur = _DEVMODE()
        cur.dmSize = ctypes.sizeof(cur)
        if not user32.EnumDisplaySettingsW(dd.DeviceName, _ENUM_CURRENT, ctypes.byref(cur)):
            continue
        w, h, hz = cur.dmPelsWidth, cur.dmPelsHeight, cur.dmDisplayFrequency
        # best refresh available at this same resolution
        best = hz
        j = 0
        while True:
            m = _DEVMODE()
            m.dmSize = ctypes.sizeof(m)
            if not user32.EnumDisplaySettingsW(dd.DeviceName, j, ctypes.byref(m)):
                break
            j += 1
            if m.dmPelsWidth == w and m.dmPelsHeight == h and m.dmDisplayFrequency > best:
                best = m.dmDisplayFrequency
        # friendly monitor name
        mon = _DISPLAY_DEVICE()
        mon.cb = ctypes.sizeof(mon)
        name = dd.DeviceString
        if user32.EnumDisplayDevicesW(dd.DeviceName, 0, ctypes.byref(mon), 0):
            name = mon.DeviceString or name
        under = best > hz + 1
        monitors.append({"name": name, "width": w, "height": h,
                         "refresh": hz, "max_refresh": best, "underclocked": under})
        if under:
            flags.append({"level": "warn",
                          "text": f"{name} is running at {hz} Hz but supports {best} Hz at {w}×{h} — set it higher in display settings."})
    if monitors and not flags:
        flags.append({"level": "good", "text": "Every monitor is at its best refresh rate."})
    if not monitors:
        flags.append({"level": "info", "text": "Couldn't read display modes."})
    return {"ok": True, "monitors": monitors, "flags": flags}
