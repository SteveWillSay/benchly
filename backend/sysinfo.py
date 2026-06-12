"""Deep hardware / firmware inventory via CIM (single batched PowerShell call)."""

import socket
import threading

import psutil

from .ps import ps_json, as_list, cim_date as _cim_date

# One PS round-trip for everything static — spawning powershell.exe repeatedly
# costs ~1s each, so all classes are queried in a single script block.
_INVENTORY_PS = r"""
$o = [ordered]@{}
$o.cs    = Get-CimInstance Win32_ComputerSystem    | Select-Object Manufacturer,Model,SystemFamily,TotalPhysicalMemory,Domain,PartOfDomain,PCSystemType
$o.os    = Get-CimInstance Win32_OperatingSystem   | Select-Object Caption,Version,BuildNumber,OSArchitecture,InstallDate,LastBootUpTime,SerialNumber
$o.bios  = Get-CimInstance Win32_BIOS              | Select-Object Manufacturer,SMBIOSBIOSVersion,ReleaseDate,SerialNumber
$o.board = Get-CimInstance Win32_BaseBoard         | Select-Object Manufacturer,Product,Version,SerialNumber
$o.cpu   = Get-CimInstance Win32_Processor         | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,L2CacheSize,L3CacheSize,SocketDesignation,VirtualizationFirmwareEnabled
$o.ram   = Get-CimInstance Win32_PhysicalMemory    | Select-Object BankLabel,DeviceLocator,Capacity,Speed,ConfiguredClockSpeed,Manufacturer,PartNumber,SMBIOSMemoryType
$o.gpu   = Get-CimInstance Win32_VideoController   | Select-Object Name,AdapterRAM,DriverVersion,DriverDate,CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate,Status
$o.disp  = Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorID -ErrorAction SilentlyContinue | ForEach-Object {
    [pscustomobject]@{
        Name   = if ($_.UserFriendlyName) { [System.Text.Encoding]::ASCII.GetString($_.UserFriendlyName -ne 0) } else { 'Generic Monitor' }
        Serial = if ($_.SerialNumberID)   { [System.Text.Encoding]::ASCII.GetString($_.SerialNumberID -ne 0) } else { '' }
        Year   = $_.YearOfManufacture
    }
}
try { $tpm = Get-CimInstance -Namespace root/cimv2/Security/MicrosoftTpm -ClassName Win32_Tpm -ErrorAction Stop
      $o.tpm = $tpm | Select-Object IsEnabled_InitialValue,IsActivated_InitialValue,SpecVersion,ManufacturerVersion } catch { $o.tpm = $null }
try { $o.secureboot = Confirm-SecureBootUEFI } catch { $o.secureboot = $null }
$o
"""

_cache = None
_lock = threading.Lock()


def get_inventory(refresh: bool = False):
    global _cache
    with _lock:   # prewarm thread and UI threads must not both pay the PS cost
        if _cache is None or refresh:
            _cache = _build_inventory()
        return _cache


def _build_inventory():
    raw = ps_json(_INVENTORY_PS, timeout=60, depth=5) or {}

    cs = raw.get("cs") or {}
    osd = raw.get("os") or {}
    bios = raw.get("bios") or {}
    board = raw.get("board") or {}

    cpus = []
    for c in as_list(raw.get("cpu")):
        cpus.append({
            "name": (c.get("Name") or "").strip(),
            "cores": c.get("NumberOfCores"),
            "threads": c.get("NumberOfLogicalProcessors"),
            "max_mhz": c.get("MaxClockSpeed"),
            "l2_kb": c.get("L2CacheSize"),
            "l3_kb": c.get("L3CacheSize"),
            "socket": c.get("SocketDesignation"),
            "virtualization": c.get("VirtualizationFirmwareEnabled"),
        })

    ram_modules = []
    for m in as_list(raw.get("ram")):
        ram_modules.append({
            "slot": m.get("DeviceLocator") or m.get("BankLabel") or "?",
            "capacity": m.get("Capacity"),
            "speed": m.get("ConfiguredClockSpeed") or m.get("Speed"),
            "manufacturer": (m.get("Manufacturer") or "").strip(),
            "part": (m.get("PartNumber") or "").strip(),
            "type": _mem_type(m.get("SMBIOSMemoryType")),
        })

    gpus = []
    for g in as_list(raw.get("gpu")):
        res = None
        if g.get("CurrentHorizontalResolution"):
            res = f'{g["CurrentHorizontalResolution"]}×{g["CurrentVerticalResolution"]} @ {g.get("CurrentRefreshRate") or "?"} Hz'
        gpus.append({
            "name": g.get("Name"),
            "vram": g.get("AdapterRAM"),
            "driver": g.get("DriverVersion"),
            "driver_date": _cim_date(g.get("DriverDate")),
            "resolution": res,
            "status": g.get("Status"),
        })

    monitors = [{
        "name": (d.get("Name") or "").strip(),
        "serial": (d.get("Serial") or "").strip(),
        "year": d.get("Year"),
    } for d in as_list(raw.get("disp"))]

    tpm = raw.get("tpm")
    tpm_info = None
    if tpm:
        tpm_info = {
            "enabled": tpm.get("IsEnabled_InitialValue"),
            "activated": tpm.get("IsActivated_InitialValue"),
            "spec": tpm.get("SpecVersion"),
        }

    return {
        "hostname": socket.gethostname(),
        "system": {
            "manufacturer": cs.get("Manufacturer"),
            "model": cs.get("Model"),
            "family": cs.get("SystemFamily"),
            "type": _pc_type(cs.get("PCSystemType")),
            "domain": cs.get("Domain"),
            "domain_joined": cs.get("PartOfDomain"),
        },
        "os": {
            "name": osd.get("Caption"),
            "version": osd.get("Version"),
            "build": osd.get("BuildNumber"),
            "arch": osd.get("OSArchitecture"),
            "installed": _cim_date(osd.get("InstallDate")),
            "serial": osd.get("SerialNumber"),
        },
        "bios": {
            "vendor": bios.get("Manufacturer"),
            "version": bios.get("SMBIOSBIOSVersion"),
            "date": _cim_date(bios.get("ReleaseDate")),
            "serial": bios.get("SerialNumber"),
        },
        "board": {
            "manufacturer": board.get("Manufacturer"),
            "product": board.get("Product"),
            "version": board.get("Version"),
            "serial": board.get("SerialNumber"),
        },
        "cpus": cpus,
        "ram_modules": ram_modules,
        "ram_total": cs.get("TotalPhysicalMemory") or psutil.virtual_memory().total,
        "gpus": gpus,
        "monitors": monitors,
        "tpm": tpm_info,
        "secure_boot": raw.get("secureboot"),
    }


def _pc_type(code):
    return {1: "Desktop", 2: "Mobile / Laptop", 3: "Workstation", 4: "Enterprise Server",
            5: "SOHO Server", 6: "Appliance", 7: "Performance Server", 8: "Slate / Tablet"}.get(code)


def _mem_type(code):
    return {20: "DDR", 21: "DDR2", 24: "DDR3", 26: "DDR4", 34: "DDR5", 35: "LPDDR5"}.get(code)
