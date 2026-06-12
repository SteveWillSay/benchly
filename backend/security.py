"""Health & security audit — a weighted checklist that rolls up into one score."""

import ctypes
import datetime
import os
import re
import tempfile
import threading
import time

import psutil

from .ps import ps_json, run_ps, as_list, cim_age_days, fmt_gb as _gb
from . import sysinfo, storage

_SEC_PS = r"""
$o = [ordered]@{}
try { $o.av_products = Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct -ErrorAction Stop |
      Select-Object displayName,productState,timestamp } catch { $o.av_products = $null }
try { $mp = Get-MpComputerStatus -ErrorAction Stop
      $o.defender = $mp | Select-Object AMServiceEnabled,RealTimeProtectionEnabled,AntivirusEnabled,AntispywareEnabled,AntivirusSignatureLastUpdated,QuickScanEndTime } catch { $o.defender = $null }
try { $o.firewall = Get-NetFirewallProfile | Select-Object Name,Enabled } catch { $o.firewall = $null }
try { $o.bitlocker = Get-BitLockerVolume -ErrorAction Stop | Select-Object MountPoint,VolumeStatus,ProtectionStatus,EncryptionPercentage } catch { $o.bitlocker = $null }
$o.uac = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System' -ErrorAction SilentlyContinue).EnableLUA
$o.qfe = Get-CimInstance Win32_QuickFixEngineering | Sort-Object { $_.InstalledOn } -Descending | Select-Object -First 1 HotFixID,InstalledOn
try { $au = (New-Object -ComObject Microsoft.Update.AutoUpdate).Results
      $o.wu_last = if ($au.LastInstallationSuccessDate) { $au.LastInstallationSuccessDate.ToString('yyyy-MM-dd') } else { $null } } catch { $o.wu_last = $null }
$o.reboot_cbs  = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
$o.reboot_wu   = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\WindowsUpdate\Auto Update\RebootRequired'
$o.reboot_file = $null -ne (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' -Name PendingFileRenameOperations -ErrorAction SilentlyContinue)
$o
"""


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


_cache = None
_lock = threading.Lock()
_battery_cache = {"done": False, "value": None}


def get_health(refresh: bool = False):
    global _cache
    with _lock:
        if _cache is None or refresh:
            _cache = _build_health(refresh)
        return _cache


def _build_health(refresh: bool):
    raw = ps_json(_SEC_PS, timeout=60) or {}
    inv = sysinfo.get_inventory(refresh=refresh)
    stor = storage.get_storage(refresh=refresh)
    admin = is_admin()
    if refresh:
        _battery_cache["done"] = False   # re-measure battery on explicit refresh
    checks = []

    def add(cid, label, status, detail, weight, category="Security"):
        checks.append({"id": cid, "label": label, "status": status,
                       "detail": detail, "weight": weight, "category": category})

    # --- Antivirus -----------------------------------------------------------
    # Security Center sees every registered product (Defender AND third-party);
    # Get-MpComputerStatus only sees Defender, so it alone misreports machines
    # running Bitdefender / ESET / etc.
    av_products = _decode_av_products(raw.get("av_products"))
    defender = raw.get("defender")
    active = [p for p in av_products if p["enabled"]]
    if active:
        names = ", ".join(p["name"] for p in active)
        add("av_rt", "Real-time antivirus protection", "good",
            f"{names} — real-time protection is on.", 15)
        outdated = [p for p in active if p["outdated"]]
        if outdated:
            add("av_sig", "Antivirus definitions", "warn",
                f"{', '.join(p['name'] for p in outdated)} reports definitions out of date.", 8)
        elif any(p["name"].lower() in ("windows defender", "microsoft defender antivirus") for p in active) and defender:
            sig_age = cim_age_days(defender.get("AntivirusSignatureLastUpdated"))
            if sig_age is not None and sig_age > 7:
                add("av_sig", "Antivirus definitions", "warn",
                    f"Defender definitions are {sig_age} days old.", 8)
            else:
                add("av_sig", "Antivirus definitions", "good",
                    "Definitions current." if sig_age is None else f"Definitions updated {sig_age} day(s) ago.", 8)
        else:
            add("av_sig", "Antivirus definitions", "good",
                "Security Center reports definitions up to date.", 8)
    elif av_products:
        names = ", ".join(p["name"] for p in av_products)
        add("av_rt", "Real-time antivirus protection", "bad",
            f"Installed ({names}) but real-time protection is OFF.", 15)
    elif defender:
        rt = defender.get("RealTimeProtectionEnabled")
        add("av_rt", "Real-time antivirus protection",
            "good" if rt else "bad",
            "Microsoft Defender real-time protection is ON." if rt
            else "Real-time protection is OFF — the machine is unprotected against new files.",
            15)
    else:
        add("av_rt", "Real-time antivirus protection", "unknown",
            "No antivirus product visible to Security Center.", 15)

    # --- Firewall ------------------------------------------------------------
    fw = as_list(raw.get("firewall"))
    if fw:
        off = [f.get("Name") for f in fw if not f.get("Enabled")]
        add("fw", "Windows Firewall (all profiles)",
            "good" if not off else "bad",
            "Domain, Private and Public profiles all enabled." if not off
            else f"Disabled profile(s): {', '.join(str(x) for x in off)}.",
            12)
    else:
        add("fw", "Windows Firewall", "unknown", "Could not query firewall profiles.", 12)

    # --- Disk encryption -----------------------------------------------------
    bl = as_list(raw.get("bitlocker"))
    if bl:
        sys_vol = next((v for v in bl if (v.get("MountPoint") or "").upper().startswith("C")), None)
        if sys_vol:
            protected = sys_vol.get("ProtectionStatus") in (1, "On")
            add("bitlocker", "BitLocker on system drive",
                "good" if protected else "warn",
                "System drive is encrypted and protection is on." if protected
                else "System drive is NOT BitLocker-protected — data is readable if the disk is removed.",
                10)
        else:
            add("bitlocker", "BitLocker on system drive", "unknown", "No C: volume reported.", 10)
    else:
        add("bitlocker", "BitLocker on system drive", "unknown",
            "BitLocker status requires Administrator." if not admin else "BitLocker not available on this edition.",
            10)

    # --- UAC -----------------------------------------------------------------
    uac = raw.get("uac")
    add("uac", "User Account Control",
        "good" if uac == 1 else ("bad" if uac == 0 else "unknown"),
        "UAC is enabled." if uac == 1 else
        ("UAC is DISABLED — all processes run unprompted at full privilege." if uac == 0
         else "Could not read UAC policy."),
        6)

    # --- Firmware security ---------------------------------------------------
    sb = inv.get("secure_boot")
    add("secureboot", "Secure Boot",
        "good" if sb is True else ("warn" if sb is False else "unknown"),
        "Secure Boot is enabled." if sb is True else
        ("Secure Boot is disabled." if sb is False
         else "Requires Administrator (or legacy BIOS) — could not confirm."),
        5)

    tpm = inv.get("tpm")
    if tpm and tpm.get("enabled"):
        spec = (tpm.get("spec") or "").split(",")[0].strip()
        add("tpm", "TPM security chip", "good", f"TPM present and enabled (spec {spec or '?'}).", 5)
    elif tpm:
        add("tpm", "TPM security chip", "warn", "TPM present but not enabled.", 5)
    else:
        add("tpm", "TPM security chip", "unknown",
            "TPM query requires Administrator." if not admin else "No TPM reported.", 5)

    # --- Updates -------------------------------------------------------------
    qfe = raw.get("qfe") or {}
    qfe_age = cim_age_days(qfe.get("InstalledOn"))
    wu_age = cim_age_days(raw.get("wu_last"))
    ages = [a for a in (qfe_age, wu_age) if a is not None]
    upd_age = min(ages) if ages else None
    upd_label = qfe.get("HotFixID") if qfe_age is not None and (wu_age is None or qfe_age <= wu_age) \
        else "Windows Update"
    if upd_age is None:
        add("updates", "Windows updates", "unknown", "No update history found.", 8, "Maintenance")
    elif upd_age <= 45:
        add("updates", "Windows updates", "good",
            f"Last update ({upd_label}) installed {upd_age} day(s) ago.", 8, "Maintenance")
    else:
        add("updates", "Windows updates", "warn",
            f"No updates installed for {upd_age} days (last: {upd_label}).", 8, "Maintenance")

    reboot = bool(raw.get("reboot_cbs") or raw.get("reboot_wu") or raw.get("reboot_file"))
    add("reboot", "Pending reboot",
        "warn" if reboot else "good",
        "A reboot is pending (servicing/updates/file renames)." if reboot
        else "No pending reboot.",
        4, "Maintenance")

    # --- Resources -----------------------------------------------------------
    try:
        du = psutil.disk_usage("C:\\")
        free_pct = 100 - du.percent
        status = "good" if free_pct >= 15 else ("warn" if free_pct >= 8 else "bad")
        add("diskfree", "System drive free space", status,
            f"{free_pct:.0f}% free ({_gb(du.free)} of {_gb(du.total)}).", 8, "Resources")
    except Exception:
        add("diskfree", "System drive free space", "unknown", "Could not read C: usage.", 8, "Resources")

    bad_disks = [d for d in stor["disks"] if d.get("health") and d["health"] != "Healthy"]
    if stor["disks"]:
        add("smart", "Physical disk health (SMART)",
            "bad" if bad_disks else "good",
            "All physical disks report Healthy." if not bad_disks
            else "Disk(s) reporting problems: " + ", ".join(f'{d["name"]} ({d["health"]})' for d in bad_disks),
            12, "Resources")
    else:
        add("smart", "Physical disk health (SMART)", "unknown", "Could not enumerate physical disks.", 12, "Resources")

    vm = psutil.virtual_memory()
    add("ram", "Memory pressure",
        "good" if vm.percent < 85 else ("warn" if vm.percent < 95 else "bad"),
        f"RAM at {vm.percent:.0f}% ({_gb(vm.total - vm.available)} of {_gb(vm.total)}).",
        5, "Resources")

    uptime_days = (time.time() - psutil.boot_time()) / 86400
    add("uptime", "Uptime",
        "good" if uptime_days < 14 else "warn",
        f"Up for {uptime_days:.1f} days." + ("" if uptime_days < 14 else " A restart is overdue."),
        3, "Maintenance")

    if not _battery_cache["done"]:
        _battery_cache["value"] = _battery_health()
        _battery_cache["done"] = True
    battery = _battery_cache["value"]
    if battery:
        pct = battery["health_pct"]
        status = "good" if pct >= 70 else ("warn" if pct >= 50 else "bad")
        add("battery", "Battery health", status,
            f'Full-charge capacity is {pct}% of design '
            f'({battery["full_mwh"]:,} / {battery["design_mwh"]:,} mWh).',
            5, "Resources")

    # --- Score ---------------------------------------------------------------
    scored = [c for c in checks if c["status"] != "unknown"]
    total_weight = sum(c["weight"] for c in scored) or 1
    value = {"good": 1.0, "warn": 0.5, "bad": 0.0}
    score = round(sum(value[c["status"]] * c["weight"] for c in scored) / total_weight * 100)

    return {
        "score": score,
        "grade": "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 40 else "F",
        "checks": checks,
        "is_admin": admin,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        # detail payloads reused by the Security hub page
        "av_products": av_products,
        "firewall_profiles": [{"name": f.get("Name"), "enabled": bool(f.get("Enabled"))} for f in fw],
        "bitlocker_volumes": [{"mount": v.get("MountPoint"), "status": v.get("VolumeStatus"),
                               "protection": "On" if v.get("ProtectionStatus") in (1, "On") else "Off",
                               "encrypted_pct": v.get("EncryptionPercentage")} for v in bl],
    }


def _decode_av_products(raw_products):
    """Decode SecurityCenter2 productState: bit 0x1000 = real-time on, 0x10 = definitions stale."""
    products = []
    for p in as_list(raw_products):
        state = p.get("productState") or 0
        products.append({
            "name": (p.get("displayName") or "Unknown product").strip(),
            "enabled": bool(state & 0x1000),
            "outdated": bool(state & 0x10),
            "timestamp": p.get("timestamp"),
        })
    # active products first
    products.sort(key=lambda x: (not x["enabled"], x["name"].lower()))
    return products


def _battery_health():
    """Parse design vs full-charge capacity out of `powercfg /batteryreport`."""
    if not psutil.sensors_battery():
        return None
    fd, xml_path = tempfile.mkstemp(prefix="benchly_bat_", suffix=".xml")  # O_EXCL, we own it
    os.close(fd)
    try:
        run_ps(f'powercfg /batteryreport /xml /output "{xml_path}"', timeout=30)
        if not os.path.exists(xml_path):
            return None
        with open(xml_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
        design = re.search(r"<DesignCapacity>(\d+)</DesignCapacity>", content)
        full = re.search(r"<FullChargeCapacity>(\d+)</FullChargeCapacity>", content)
        if design and full and int(design.group(1)) > 0:
            d, fl = int(design.group(1)), int(full.group(1))
            return {"design_mwh": d, "full_mwh": fl, "health_pct": round(fl / d * 100)}
    except Exception:
        pass
    finally:
        try:
            os.remove(xml_path)
        except OSError:
            pass
    return None
