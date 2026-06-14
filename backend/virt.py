"""Virtualization health — WSL, Hyper-V, Docker.

The lab gremlins: a `.wslconfig` that ate all your RAM and never gave it back, a
Docker/WSL `ext4.vhdx` quietly ballooning to tens of GB, a Hyper-V external switch
that hijacked your NIC, or VT-x simply turned off in firmware. Read-only; the one
optional write (compact a vhdx) is non-destructive and clearly flagged.
"""

import glob
import os

from .ps import ps_json, run_ps, as_list


def _wsl():
    out = run_ps("wsl.exe --status", timeout=20)
    if not out or "not recognized" in out.lower() or "no installed" in out.lower():
        return {"installed": False}
    distros = []
    listing = run_ps("wsl.exe --list --verbose", timeout=20)
    for line in (listing or "").splitlines():
        # the listing is UTF-16-ish; run_ps already decoded — strip NULs/markers
        s = line.replace("\x00", "").strip().lstrip("*").strip()
        if not s or s.lower().startswith("name") or s.lower().startswith("windows subsystem"):
            continue
        parts = s.split()
        if len(parts) >= 2 and parts[-1] in ("1", "2"):
            distros.append({"name": parts[0], "state": parts[-2], "version": parts[-1]})
    # .wslconfig memory cap
    cfg = os.path.join(os.path.expanduser("~"), ".wslconfig")
    mem_cap = None
    if os.path.isfile(cfg):
        try:
            with open(cfg, encoding="utf-8", errors="replace") as f:
                for ln in f:
                    if ln.strip().lower().startswith("memory"):
                        mem_cap = ln.split("=", 1)[-1].strip()
        except OSError:
            pass
    # ext4.vhdx sizes
    vhdx = []
    base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Packages")
    for p in glob.glob(os.path.join(base, "*", "LocalState", "ext4.vhdx")) + \
             glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Docker", "wsl", "*", "*.vhdx")):
        try:
            vhdx.append({"path": p, "bytes": os.path.getsize(p)})
        except OSError:
            pass
    vhdx.sort(key=lambda v: v["bytes"], reverse=True)
    return {"installed": True, "distros": distros, "mem_cap": mem_cap, "vhdx": vhdx}


def virt_health():
    wsl = _wsl()
    # virtualization firmware flags + Hyper-V switches
    info = ps_json(
        "$cs = Get-CimInstance Win32_ComputerSystem; "
        "[pscustomobject]@{ "
        "VtEnabled = (Get-CimInstance Win32_Processor).VirtualizationFirmwareEnabled; "
        "HvPresent = $cs.HypervisorPresent; "
        "Switches = @(Get-VMSwitch -ErrorAction SilentlyContinue | Select-Object Name,SwitchType,NetAdapterInterfaceDescription) }",
        timeout=25, depth=3) or {}
    switches = []
    for s in as_list(info.get("Switches")):
        switches.append({"name": s.get("Name"), "type": s.get("SwitchType"),
                         "adapter": s.get("NetAdapterInterfaceDescription") or ""})

    flags = []
    if info.get("VtEnabled") is False and not info.get("HvPresent"):
        flags.append({"level": "warn", "text": "Hardware virtualization (VT-x/AMD-V) looks disabled in firmware — VMs and WSL2 need it."})
    if wsl.get("installed"):
        if not wsl.get("mem_cap"):
            flags.append({"level": "info", "text": "No memory cap in .wslconfig — WSL2 can grab up to ~50% of RAM and not give it back. Add a memory= limit if vmmem balloons."})
        big = [v for v in wsl.get("vhdx", []) if v["bytes"] > 20 * 1024**3]
        if big:
            flags.append({"level": "info", "text": f"A WSL/Docker virtual disk is over 20 GB and won't shrink on its own — you can compact it to reclaim space."})
    if any(s["type"] == "External" or s.get("adapter") for s in switches):
        flags.append({"level": "info", "text": "An external Hyper-V switch is bound to a physical NIC — if host networking acts up, this is a common cause."})
    if not flags:
        flags.append({"level": "good", "text": "Virtualization looks healthy."})

    return {"ok": True, "wsl": wsl, "switches": switches,
            "vt_enabled": info.get("VtEnabled"), "hyperv": bool(info.get("HvPresent")),
            "flags": flags}


def compact_vhdx(path):
    """Non-destructively shrink a WSL/Docker virtual disk via diskpart compact."""
    from . import security
    if not security.is_admin():
        return {"ok": False, "error": "Compacting a virtual disk needs elevation — use Run as admin."}
    if not path or not os.path.isfile(path) or not path.lower().endswith(".vhdx"):
        return {"ok": False, "error": "Pick an existing .vhdx file."}
    script = f"select vdisk file=\"{path}\"\nattach vdisk readonly\ncompact vdisk\ndetach vdisk\n"
    import subprocess
    import tempfile
    from .ps import CREATE_NO_WINDOW
    tmp = os.path.join(tempfile.gettempdir(), "benchly-compact.txt")
    try:
        with open(tmp, "w", encoding="ascii") as f:
            f.write(script)
        r = subprocess.run(["diskpart", "/s", tmp], capture_output=True, timeout=600,
                           creationflags=CREATE_NO_WINDOW)
        os.remove(tmp)
        out = r.stdout.decode("mbcs", errors="replace")
        if "DiskPart successfully" in out or r.returncode == 0:
            return {"ok": True, "detail": "Compacted. WSL must be shut down (wsl --shutdown) for it to free much."}
        return {"ok": False, "error": "diskpart couldn't compact it (make sure WSL is shut down first)."}
    except Exception as e:
        return {"ok": False, "error": str(e)}
