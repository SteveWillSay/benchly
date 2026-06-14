"""Managed Baseline — the enterprise-policy configurator for unmanaged machines.

Reads, and on request applies, the management-grade policies an admin normally
pushes via GPO or Intune: Windows Update for Business deferrals, BitLocker startup
PIN policy, telemetry level, auto-lock, and UAC. Built for MSPs and small businesses
running standalone PCs without Intune.

Every control is read first; applying is opt-in per item, shows the exact registry
key it writes, and is fully reversible — 'Clear' deletes the policy value, returning
the setting to its unmanaged Windows default. Two guards run alongside: a warning when
the machine is already centrally managed (real GPO/MDM would overwrite these), and
SKU/hardware awareness (e.g. telemetry 'Security' needs Enterprise; a startup PIN
needs a TPM). Everything here needs admin.
"""

import winreg

from . import security, identity
from .ps import ps_json, run_ps

HKLM = winreg.HKEY_LOCAL_MACHINE

_WU = r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"
_AU = r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"
_FVE = r"SOFTWARE\Policies\Microsoft\FVE"
_DC = r"SOFTWARE\Policies\Microsoft\Windows\DataCollection"
_SYS = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"

# Each control: type drives the UI widget.
#   toggle  -> on/off (value 1/0, recommended given)
#   number  -> integer in [min,max] with a unit
#   choice  -> pick from options [(value,label)]
#   string  -> free text (short)
# requires: optional gate key checked against machine context.
_CONTROLS = [
    # ---- Windows Update for Business -------------------------------------------------
    dict(key="wu_defer_quality", cat="Update management", type="number",
         label="Defer quality (monthly) updates", unit="days", min=0, max=30, recommended=0,
         path=_WU, name="DeferQualityUpdatesPeriodInDays", regtype="dword",
         companion=(_WU, "DeferQualityUpdates", 1),
         help="Hold back the monthly cumulative updates by N days so they're proven elsewhere first.",
         where=r"HKLM\…\WindowsUpdate\DeferQualityUpdatesPeriodInDays"),
    dict(key="wu_defer_feature", cat="Update management", type="number",
         label="Defer feature (version) updates", unit="days", min=0, max=365, recommended=0,
         path=_WU, name="DeferFeatureUpdatesPeriodInDays", regtype="dword",
         companion=(_WU, "DeferFeatureUpdates", 1),
         help="Hold back the big once- or twice-a-year version upgrades by N days.",
         where=r"HKLM\…\WindowsUpdate\DeferFeatureUpdatesPeriodInDays"),
    dict(key="wu_target_release", cat="Update management", type="string",
         label="Pin to a Windows version", placeholder="e.g. 23H2", recommended="",
         path=_WU, name="TargetReleaseVersionInfo", regtype="string",
         companion=(_WU, "TargetReleaseVersion", 1),
         help="Keep the machine on a specific feature version (e.g. 23H2) until you choose to move it.",
         where=r"HKLM\…\WindowsUpdate\TargetReleaseVersionInfo"),
    dict(key="wu_exclude_drivers", cat="Update management", type="toggle", recommended=1,
         label="Don't get drivers through Windows Update",
         path=_WU, name="ExcludeWUDriversInQualityUpdate", regtype="dword",
         help="Stops Windows Update pushing device drivers — useful where you manage drivers yourself.",
         where=r"HKLM\…\WindowsUpdate\ExcludeWUDriversInQualityUpdate"),
    dict(key="wu_no_auto_reboot", cat="Update management", type="toggle", recommended=1,
         label="Never auto-restart while someone's signed in",
         path=_AU, name="NoAutoRebootWithLoggedOnUsers", regtype="dword",
         help="Windows won't force a restart for updates while a user is logged on.",
         where=r"HKLM\…\WindowsUpdate\AU\NoAutoRebootWithLoggedOnUsers"),
    # ---- BitLocker ------------------------------------------------------------------
    dict(key="bl_require_startup_auth", cat="BitLocker", type="toggle", recommended=1,
         label="Require extra authentication at startup",
         path=_FVE, name="UseAdvancedStartup", regtype="dword",
         help="Turns on the policy that lets you require a PIN (or USB key) before Windows boots.",
         where=r"HKLM\…\FVE\UseAdvancedStartup"),
    dict(key="bl_require_pin", cat="BitLocker", type="toggle", recommended=1, requires="tpm",
         label="Require a startup PIN with the TPM",
         path=_FVE, name="UseTPMPIN", regtype="dword",
         help="Makes a boot-time PIN mandatory on top of the TPM. After setting this, enrol the PIN with "
              "manage-bde -protectors -add C: -TPMAndPIN.",
         where=r"HKLM\…\FVE\UseTPMPIN"),
    dict(key="bl_min_pin", cat="BitLocker", type="number", unit="characters",
         min=4, max=20, recommended=6, requires="tpm",
         label="Minimum startup-PIN length",
         path=_FVE, name="MinimumPIN", regtype="dword",
         help="The shortest startup PIN a user may set (6+ recommended).",
         where=r"HKLM\…\FVE\MinimumPIN"),
    # ---- Privacy / telemetry --------------------------------------------------------
    dict(key="telemetry", cat="Privacy", type="choice", recommended=1,
         options=[(0, "Security (Enterprise/Edu only)"), (1, "Required (minimum)"),
                  (2, "Enhanced"), (3, "Optional / Full")],
         label="Diagnostic data level",
         path=_DC, name="AllowTelemetry", regtype="dword",
         help="Caps how much diagnostic data Windows sends. 'Security' (0) is only honoured on Enterprise/Education.",
         where=r"HKLM\…\DataCollection\AllowTelemetry"),
    # ---- Auto-lock ------------------------------------------------------------------
    dict(key="lock_timeout", cat="Lock & sign-in", type="number", unit="seconds",
         min=0, max=3600, recommended=600,
         label="Auto-lock after inactivity",
         path=_SYS, name="InactivityTimeoutSecs", regtype="dword",
         help="Locks the machine after this many idle seconds (0 = never). 600 = 10 minutes.",
         where=r"HKLM\…\Policies\System\InactivityTimeoutSecs"),
    # ---- UAC ------------------------------------------------------------------------
    dict(key="uac_enabled", cat="UAC", type="toggle", recommended=1,
         label="User Account Control on",
         path=_SYS, name="EnableLUA", regtype="dword",
         help="The master UAC switch. Turning it off is a serious security downgrade.",
         where=r"HKLM\…\Policies\System\EnableLUA"),
    dict(key="uac_secure_desktop", cat="UAC", type="toggle", recommended=1,
         label="Dim the desktop for UAC prompts (secure desktop)",
         path=_SYS, name="PromptOnSecureDesktop", regtype="dword",
         help="Shows UAC prompts on the isolated secure desktop so other programs can't spoof or click them.",
         where=r"HKLM\…\Policies\System\PromptOnSecureDesktop"),
]


def _read(path, name):
    try:
        k = winreg.OpenKey(HKLM, path)
        try:
            v, _ = winreg.QueryValueEx(k, name)
            return v
        finally:
            winreg.CloseKey(k)
    except OSError:
        return None


def _write(path, name, value, regtype):
    k = winreg.CreateKeyEx(HKLM, path, 0, winreg.KEY_SET_VALUE)
    try:
        if regtype == "string":
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, str(value))
        else:
            winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, int(value))
    finally:
        winreg.CloseKey(k)


def _delete(path, name):
    try:
        k = winreg.OpenKey(HKLM, path, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(k, name)
        finally:
            winreg.CloseKey(k)
    except OSError:
        pass


def _by_key(key):
    return next((c for c in _CONTROLS if c["key"] == key), None)


def _machine_context():
    edition = (ps_json("(Get-CimInstance Win32_OperatingSystem).Caption", timeout=15) or "")
    tpm = ps_json("[bool](Get-CimInstance -Namespace root/cimv2/Security/MicrosoftTpm "
                  "-ClassName Win32_Tpm -ErrorAction SilentlyContinue)", timeout=15)
    ident = identity.identity_status()
    ed = str(edition)
    return {
        "edition": ed.strip() or None,
        "is_enterprise": any(w in ed for w in ("Enterprise", "Education")),
        "has_tpm": bool(tpm),
        "managed": ident.get("managed", False),
        "managed_verdict": ident.get("verdict"),
    }


def _password_policy():
    """Read-only view of the local password & lockout policy via `net accounts`."""
    out = run_ps("net accounts", timeout=15) or ""
    rows = []
    wanted = {
        "Minimum password length": "Minimum password length",
        "Maximum password age": "Maximum password age (days)",
        "Minimum password age": "Minimum password age (days)",
        "Length of password history": "Passwords remembered",
        "Lockout threshold": "Lockout after N bad attempts",
        "Lockout duration": "Lockout duration (mins)",
    }
    for line in out.splitlines():
        for needle, label in wanted.items():
            if line.strip().startswith(needle):
                val = line.split(":", 1)[1].strip() if ":" in line else "—"
                rows.append({"label": label, "value": val})
    return rows


def read_baseline():
    admin = security.is_admin()
    ctx = _machine_context()
    controls = []
    for c in _CONTROLS:
        cur = _read(c["path"], c["name"])
        gated = None
        if c.get("requires") == "tpm" and not ctx["has_tpm"]:
            gated = "Needs a TPM — none detected on this machine."
        if c["key"] == "telemetry" and not ctx["is_enterprise"]:
            gated = gated  # still settable; level 0 just won't be honoured (noted in help)
        item = {k: c[k] for k in ("key", "cat", "type", "label", "help", "where", "recommended")}
        for opt in ("unit", "min", "max", "options", "placeholder", "requires"):
            if opt in c:
                item[opt] = c[opt]
        item["current"] = cur
        item["set"] = cur is not None
        item["gated"] = gated
        controls.append(item)
    return {
        "ok": True, "is_admin": admin, "context": ctx,
        "controls": controls,
        "password_policy": _password_policy(),
    }


def apply_policy(key, value):
    if not security.is_admin():
        return {"ok": False, "error": "Policy changes need elevation — use Run as admin."}
    c = _by_key(key)
    if not c:
        return {"ok": False, "error": "Unknown policy."}
    # validate
    try:
        if c["type"] == "number":
            value = int(value)
            if not (c["min"] <= value <= c["max"]):
                return {"ok": False, "error": f"Value must be between {c['min']} and {c['max']}."}
        elif c["type"] == "toggle":
            value = 1 if int(value) else 0
        elif c["type"] == "choice":
            allowed = [o[0] for o in c["options"]]
            value = int(value)
            if value not in allowed:
                return {"ok": False, "error": "Not one of the allowed options."}
        elif c["type"] == "string":
            value = str(value).strip()
    except (ValueError, TypeError):
        return {"ok": False, "error": "Invalid value."}
    try:
        _write(c["path"], c["name"], value, c["regtype"])
        # paired enabler (e.g. DeferQualityUpdates=1 alongside the period)
        comp = c.get("companion")
        if comp and (c["type"] != "string" or value):
            _write(comp[0], comp[1], comp[2], "dword")
        return {"ok": True, "where": c["where"], "value": value}
    except OSError as e:
        return {"ok": False, "error": str(e)}


def clear_policy(key):
    """Delete the policy value — returns the setting to its unmanaged Windows default."""
    if not security.is_admin():
        return {"ok": False, "error": "Policy changes need elevation — use Run as admin."}
    c = _by_key(key)
    if not c:
        return {"ok": False, "error": "Unknown policy."}
    _delete(c["path"], c["name"])
    comp = c.get("companion")
    if comp:
        _delete(comp[0], comp[1])
    return {"ok": True, "cleared": key}


def export_baseline():
    """A JSON-able snapshot of the current policy state — for documentation / Fleet."""
    data = read_baseline()
    return {"ok": True, "context": data["context"],
            "policies": [{"key": c["key"], "label": c["label"],
                          "current": c["current"], "set": c["set"]} for c in data["controls"]],
            "password_policy": data["password_policy"]}
