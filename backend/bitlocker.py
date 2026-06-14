"""BitLocker recovery-key reminder & health.

People enable (or inherit) BitLocker and have no idea where the recovery key is —
then a firmware change or a botched repair demands a key they can't produce, and
the data is gone. This shows which drives are encrypted, whether a recovery key is
escrowed somewhere safe, and (on demand, admin) reveals the key so it can be saved.

The recovery key is the single most sensitive value in the app: it is fetched only
when explicitly requested, never logged, never cached, never sent anywhere.
"""

from .ps import ps_json, as_list, run_ps
from . import security

_STATUS_PS = r"""
Get-BitLockerVolume -ErrorAction SilentlyContinue | ForEach-Object {
    $kp = $_.KeyProtector
    [pscustomobject]@{
        Mount      = $_.MountPoint
        Protection = [string]$_.ProtectionStatus
        Volume     = [string]$_.VolumeStatus
        Encryption = $_.EncryptionPercentage
        HasRecovery = [bool]($kp | Where-Object { $_.KeyProtectorType -eq 'RecoveryPassword' })
        Protectors = ($kp | ForEach-Object { [string]$_.KeyProtectorType }) -join ', '
    }
}
"""


def bitlocker_status():
    rows = as_list(ps_json(_STATUS_PS, timeout=40, depth=3))
    if rows is None:
        rows = []
    volumes = []
    flags = []
    any_on = False
    for r in rows:
        on = r.get("Protection") == "On"
        any_on = any_on or on
        has_key = bool(r.get("HasRecovery"))
        volumes.append({
            "mount": r.get("Mount"),
            "on": on,
            "status": r.get("Volume"),
            "encryption": r.get("Encryption"),
            "has_recovery": has_key,
            "protectors": r.get("Protectors") or "",
        })
        if on and not has_key:
            flags.append({"level": "warn",
                          "text": f"{r.get('Mount')} is encrypted but has no recovery password protector — back up a key before any firmware/repair change."})
    if not rows:
        flags.append({"level": "info", "text": "Couldn't read BitLocker status (it may need admin, or BitLocker isn't available on this edition)."})
    elif any_on:
        if not any(f["level"] == "warn" for f in flags):
            flags.append({"level": "good", "text": "Encrypted drives have a recovery key. Make sure you've saved it somewhere safe (not only on this PC)."})
    else:
        flags.append({"level": "info", "text": "No drives are currently BitLocker-encrypted."})
    return {"ok": True, "volumes": volumes, "any_encrypted": any_on, "flags": flags}


def get_recovery_key(mount):
    """Reveal the recovery password for a volume — explicit, admin-gated, never stored."""
    if not security.is_admin():
        return {"ok": False, "error": "Reading the recovery key needs elevation — use Run as admin."}
    if not mount or len(str(mount)) > 4:
        return {"ok": False, "error": "Invalid drive."}
    safe = str(mount).replace("'", "")
    out = run_ps(
        "& { (Get-BitLockerVolume -MountPoint '" + safe + "' -ErrorAction SilentlyContinue).KeyProtector | "
        "Where-Object { $_.KeyProtectorType -eq 'RecoveryPassword' } | "
        "ForEach-Object { $_.KeyProtectorId.Trim('{','}') + '|' + $_.RecoveryPassword } }", timeout=30)
    line = (out or "").strip().splitlines()[0] if out.strip() else ""
    if "|" in line:
        kid, pw = line.split("|", 1)
        return {"ok": True, "id": kid.strip(), "key": pw.strip()}
    return {"ok": False, "error": "No recovery password found for that drive."}
