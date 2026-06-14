"""Activation & licensing — 'is Windows actually activated, and on what kind of licence?'

Reads the Software Licensing service through CIM (no slmgr pop-ups): activation
status, the licence channel (OEM / Retail / Volume), how a machine is activated, and
the product key embedded in the firmware (the machine's own — handy when a reinstall
loses the sticker). All read-only.
"""

from .ps import ps_json

_WINDOWS_APP_ID = "55c92734-d682-4d71-983e-d6ec3f16059f"

_STATUS = {
    0: ("Not activated", "bad", "Windows is unlicensed — it needs activating."),
    1: ("Activated", "good", "Windows is fully activated."),
    2: ("In grace period", "warn", "Activated on a temporary grace period — it'll need a real licence before it runs out."),
    3: ("Out-of-tolerance grace", "warn", "Hardware changed enough that Windows wants re-activating."),
    4: ("Non-genuine grace", "bad", "Windows flagged the licence as non-genuine."),
    5: ("Notification mode", "bad", "Activation failed — Windows is nagging and will start limiting personalisation."),
    6: ("Extended grace", "warn", "On an extended grace period."),
}


def _channel(desc):
    """Pull the human channel name out of the SLP Description string."""
    if not desc:
        return None
    d = desc.upper()
    if "OEM" in d:
        return "OEM (tied to this PC)"
    if "RETAIL" in d:
        return "Retail (transferable)"
    if "VOLUME_KMSCLIENT" in d or "KMSCLIENT" in d:
        return "Volume — KMS (managed by an organisation)"
    if "VOLUME_MAK" in d or "MAK" in d:
        return "Volume — MAK"
    if "VOLUME" in d:
        return "Volume"
    if "EVALUATION" in d:
        return "Evaluation"
    return None


def licensing_status():
    d = ps_json(
        "$o=[ordered]@{}; "
        f"$p = Get-CimInstance SoftwareLicensingProduct -Filter \"ApplicationID='{_WINDOWS_APP_ID}' "
        "AND PartialProductKey IS NOT NULL\" -ErrorAction SilentlyContinue | Select-Object -First 1; "
        "$o.name=$p.Name; $o.desc=$p.Description; $o.status=[int]$p.LicenseStatus; "
        "$o.partial=$p.PartialProductKey; $o.grace_min=$p.GracePeriodRemaining; "
        "$svc = Get-CimInstance SoftwareLicensingService -ErrorAction SilentlyContinue; "
        "$o.oem_key=$svc.OA3xOriginalProductKey; $o.kms=$svc.KeyManagementServiceMachine; "
        "$o.edition=(Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue).Caption; $o",
        timeout=40)
    if not d:
        return {"ok": False, "error": "Couldn't read the licensing service."}

    status = d.get("status")
    label, level, detail = _STATUS.get(status, ("Unknown", "warn", "Activation state couldn't be read."))
    grace_min = d.get("grace_min")
    grace_days = round(grace_min / 1440) if grace_min else None

    return {
        "ok": True,
        "edition": (d.get("edition") or "").strip() or None,
        "status": label, "level": level, "detail": detail,
        "channel": _channel(d.get("desc")),
        "partial_key": d.get("partial"),       # last 5 of the active key (safe to show)
        "oem_key": d.get("oem_key") or None,    # firmware-embedded key — the machine's own
        "kms_host": d.get("kms") or None,
        "grace_days": grace_days,
    }
