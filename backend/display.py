"""\"Make it normal again\" — display sanity for the screen that's gone huge or tiny.

Reads the current resolution and the system text size, flags a screen that isn't at
its native resolution, and offers safe one-tap text-size presets (the usual cause of
"everything is suddenly enormous"). Text size is an instant, reversible change;
resolution is left to a guided jump into Windows Settings so a bad guess can't leave
someone unable to see.
"""

import ctypes
import winreg

from .ps import ps_json, as_list

_HKCU = winreg.HKEY_CURRENT_USER
_ACCESS = r"Software\Microsoft\Accessibility"


def _primary_resolution():
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception:
        return None, None


def _text_scale():
    try:
        k = winreg.OpenKey(_HKCU, _ACCESS)
        try:
            v, _ = winreg.QueryValueEx(k, "TextScaleFactor")
            return int(v)
        finally:
            winreg.CloseKey(k)
    except OSError:
        return 100


def detect_display():
    w, h = _primary_resolution()
    # native (max) modes per monitor via CIM video controller
    rows = as_list(ps_json(
        "Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue | "
        "Select-Object Name,CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate", timeout=20))
    monitors = []
    flags = []
    for r in rows:
        cw, ch = r.get("CurrentHorizontalResolution"), r.get("CurrentVerticalResolution")
        if not cw:
            continue
        monitors.append({"name": r.get("Name"), "width": cw, "height": ch,
                         "refresh": r.get("CurrentRefreshRate")})
    scale = _text_scale()
    if scale and scale != 100:
        flags.append({"level": "info", "text": f"Text size is set to {scale}% (100% is the standard)."})
    if not flags:
        flags.append({"level": "good", "text": "Display looks set up normally."})
    return {"ok": True, "primary": {"width": w, "height": h}, "monitors": monitors,
            "text_scale": scale, "flags": flags}


def set_text_scale(percent):
    try:
        percent = int(percent)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Bad value."}
    if not 100 <= percent <= 225:
        return {"ok": False, "error": "Text size must be 100–225%."}
    try:
        k = winreg.CreateKeyEx(_HKCU, _ACCESS, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.SetValueEx(k, "TextScaleFactor", 0, winreg.REG_DWORD, percent)
        finally:
            winreg.CloseKey(k)
        return {"ok": True, "where": f"HKCU\\{_ACCESS}\\TextScaleFactor = {percent}",
                "note": "Most apps update straight away; a few need to be reopened."}
    except OSError as e:
        return {"ok": False, "error": str(e)}
