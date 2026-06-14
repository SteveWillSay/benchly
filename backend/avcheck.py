"""Camera & microphone doctor — \"works everywhere but Zoom\".

It's almost never the hardware. It's the Windows privacy permission, an app holding
the device, or the wrong default. This reads the camera/mic consent store: the
global toggle, per-app permission, and which app (if any) is using the device right
now. Flipping a permission back on is a one-click, documented registry write.
"""

import re
import winreg

_HKCU = winreg.HKEY_CURRENT_USER
_BASE = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore"


def _read_value(path, name="Value"):
    try:
        k = winreg.OpenKey(_HKCU, path)
        try:
            v, _ = winreg.QueryValueEx(k, name)
            return v
        finally:
            winreg.CloseKey(k)
    except OSError:
        return None


def _friendly(subkey):
    if subkey.startswith("C:") or "#" in subkey:           # NonPackaged exe path
        path = subkey.replace("#", "\\")
        return path.rsplit("\\", 1)[-1]
    m = re.match(r"^([\w.]+?)_[a-z0-9]+$", subkey)           # packaged PFN
    return m.group(1).split(".")[-1] if m else subkey


def _enumerate(cap):
    base = f"{_BASE}\\{cap}"
    global_val = _read_value(base)
    apps = []
    for sub in ("", r"\NonPackaged"):
        parent = base + sub
        try:
            k = winreg.OpenKey(_HKCU, parent)
        except OSError:
            continue
        try:
            i = 0
            while True:
                try:
                    name = winreg.EnumKey(k, i)
                except OSError:
                    break
                i += 1
                if name == "NonPackaged":
                    continue
                val = _read_value(f"{parent}\\{name}")
                if val is None:
                    continue
                stop = _read_value(f"{parent}\\{name}", "LastUsedTimeStop")
                apps.append({
                    "name": _friendly(name),
                    "allowed": val == "Allow",
                    "in_use": stop == 0,
                    "raw": name,
                    "nonpackaged": bool(sub),
                })
        finally:
            winreg.CloseKey(k)
    apps.sort(key=lambda a: (not a["in_use"], not a["allowed"], a["name"].lower()))
    return {"global": global_val, "apps": apps}


def av_check():
    cam = _enumerate("webcam")
    mic = _enumerate("microphone")
    flags = []
    for label, data in (("Camera", cam), ("Microphone", mic)):
        if data["global"] == "Deny":
            flags.append({"level": "warn", "text": f"{label} access is turned OFF for all apps — that's why nothing can use it."})
        denied = [a for a in data["apps"] if not a["allowed"]]
        in_use = [a for a in data["apps"] if a["in_use"]]
        if in_use:
            flags.append({"level": "info", "text": f"{label} is in use right now by {in_use[0]['name']}."})
        if denied and data["global"] != "Deny":
            flags.append({"level": "info", "text": f"{label} is blocked for {len(denied)} app(s) — e.g. {denied[0]['name']}."})
    if not flags:
        flags.append({"level": "good", "text": "Camera and microphone permissions look fine."})
    return {"ok": True, "camera": cam, "microphone": mic, "flags": flags}


def set_av_permission(cap, raw, nonpackaged, allow):
    """Flip an app's camera/mic permission (Allow/Deny)."""
    if cap not in ("webcam", "microphone"):
        return {"ok": False, "error": "Unknown capability."}
    if not raw or len(raw) > 260 or any(c in raw for c in "\"'"):
        return {"ok": False, "error": "Invalid app."}
    path = f"{_BASE}\\{cap}" + (r"\NonPackaged" if nonpackaged else "") + f"\\{raw}"
    try:
        k = winreg.CreateKeyEx(_HKCU, path, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.SetValueEx(k, "Value", 0, winreg.REG_SZ, "Allow" if allow else "Deny")
        finally:
            winreg.CloseKey(k)
        return {"ok": True, "where": f"HKCU\\…\\ConsentStore\\{cap}\\…\\Value = {'Allow' if allow else 'Deny'}"}
    except OSError as e:
        return {"ok": False, "error": str(e)}


def set_av_global(cap, allow):
    if cap not in ("webcam", "microphone"):
        return {"ok": False, "error": "Unknown capability."}
    try:
        k = winreg.CreateKeyEx(_HKCU, f"{_BASE}\\{cap}", 0, winreg.KEY_SET_VALUE)
        try:
            winreg.SetValueEx(k, "Value", 0, winreg.REG_SZ, "Allow" if allow else "Deny")
        finally:
            winreg.CloseKey(k)
        return {"ok": True}
    except OSError as e:
        return {"ok": False, "error": str(e)}
