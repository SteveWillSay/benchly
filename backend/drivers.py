"""Third-party driver audit via Win32_PnPSignedDriver (locale-independent)."""

import datetime

from .ps import ps_json, as_list, cim_date

_DRIVERS_PS = r"""
Get-CimInstance Win32_PnPSignedDriver -Filter "DriverProviderName IS NOT NULL" |
    Where-Object { $_.DriverProviderName -and $_.DriverProviderName -ne 'Microsoft' -and $_.DeviceName } |
    Select-Object DeviceName,DriverVersion,DriverDate,DriverProviderName,InfName,DeviceClass
"""


def get_driver_audit(old_years: int = 5):
    rows = as_list(ps_json(_DRIVERS_PS, timeout=120))
    cutoff = (datetime.date.today() - datetime.timedelta(days=old_years * 365)).isoformat()

    drivers, seen = [], {}
    for r in rows:
        name = (r.get("DeviceName") or "").strip()
        inf = (r.get("InfName") or "").lower()
        version = r.get("DriverVersion") or ""
        key = (name.lower(), inf, version)
        if key in seen:           # one device can enumerate several instances
            continue
        seen[key] = True
        date = cim_date(r.get("DriverDate"))
        drivers.append({
            "device": name,
            "provider": (r.get("DriverProviderName") or "").strip(),
            "version": version,
            "date": date,
            "inf": inf,
            "class": r.get("DeviceClass") or "",
            "old": bool(date and date < cutoff),
        })

    # duplicate detection: same device name shipping more than one driver version
    by_device = {}
    for d in drivers:
        by_device.setdefault(d["device"].lower(), set()).add(d["version"])
    for d in drivers:
        d["duplicate"] = len(by_device[d["device"].lower()]) > 1

    drivers.sort(key=lambda d: (not d["duplicate"], not d["old"],
                                d["provider"].lower(), d["device"].lower()))
    return {
        "drivers": drivers,
        "old_count": sum(1 for d in drivers if d["old"]),
        "dup_count": sum(1 for d in drivers if d["duplicate"]),
        "old_years": old_years,
    }
