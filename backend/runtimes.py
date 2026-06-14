"""Runtime inventory — the 'app won't start, missing runtime' diagnosis, in one place.

Lists the .NET Framework and .NET (Core/5+) runtimes, the Visual C++ redistributables,
and the DirectX version — the things a program quietly needs and complains about when
they're missing. All read-only.
"""

import os
import winreg

from .ps import run_ps, as_list, ps_json

HKLM = winreg.HKEY_LOCAL_MACHINE

# .NET Framework 4.x: the Release DWORD → friendly version.
_NDP_RELEASE = [
    (533320, "4.8.1 or later"), (528040, "4.8"), (461808, "4.7.2"),
    (461308, "4.7.1"), (460798, "4.7"), (394802, "4.6.2"), (394254, "4.6.1"),
    (393295, "4.6"), (379893, "4.5.2"), (378675, "4.5.1"), (378389, "4.5"),
]


def _reg_val(root, path, name):
    try:
        k = winreg.OpenKey(root, path)
        try:
            v, _ = winreg.QueryValueEx(k, name)
            return v
        finally:
            winreg.CloseKey(k)
    except OSError:
        return None


def _dotnet_framework():
    out = []
    rel = _reg_val(HKLM, r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full", "Release")
    if rel:
        ver = next((v for r, v in _NDP_RELEASE if rel >= r), f"4.x (release {rel})")
        out.append(f".NET Framework {ver}")
    if _reg_val(HKLM, r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v3.5", "Install") == 1:
        out.append(".NET Framework 3.5")
    return out


def _dotnet_core():
    """Modern .NET (Core/5+). Prefer `dotnet --list-runtimes`; fall back to the shared dir."""
    text = run_ps("dotnet --list-runtimes 2>$null", timeout=15) or ""
    runtimes = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Microsoft."):
            parts = line.split()
            if len(parts) >= 2:
                runtimes.append(f"{parts[0].replace('Microsoft.', '')} {parts[1]}")
    if not runtimes:
        shared = os.path.expandvars(r"%ProgramFiles%\dotnet\shared")
        if os.path.isdir(shared):
            for fam in os.listdir(shared):
                fam_dir = os.path.join(shared, fam)
                if os.path.isdir(fam_dir):
                    for ver in os.listdir(fam_dir):
                        runtimes.append(f"{fam.replace('Microsoft.', '')} {ver}")
    return runtimes


def _vcredist():
    """Visual C++ redistributables from the uninstall registry (both bitnesses)."""
    found = {}
    roots = [
        (HKLM, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (HKLM, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for root, base in roots:
        try:
            k = winreg.OpenKey(root, base)
        except OSError:
            continue
        try:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(k, i)
                except OSError:
                    break
                i += 1
                name = _reg_val(root, base + "\\" + sub, "DisplayName")
                if name and "visual c++" in name.lower() and "redistributable" in name.lower():
                    ver = _reg_val(root, base + "\\" + sub, "DisplayVersion") or ""
                    found[name] = ver
        finally:
            winreg.CloseKey(k)
    return [{"name": n, "version": v} for n, v in sorted(found.items())]


def _directx():
    v = _reg_val(HKLM, r"SOFTWARE\Microsoft\DirectX", "Version")
    # Win10/11 ship DirectX 12; report that plus the DDI version string if present.
    label = "DirectX 12 (Windows 10/11)"
    return {"label": label, "ddi": v}


def runtimes_inventory():
    return {
        "ok": True,
        "dotnet_framework": _dotnet_framework(),
        "dotnet_core": _dotnet_core(),
        "vcredist": _vcredist(),
        "directx": _directx(),
    }
