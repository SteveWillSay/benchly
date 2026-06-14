"""Windows tweaks — performance, privacy and interface toggles.

Every tweak is a documented, reversible registry change. Each carries a plain-
English label, what it does, and exactly WHERE it writes (shown in the UI), so a
technician always knows what Benchly changed on the machine. `on` applies the
tweak; `off` restores the Windows default value.
"""

import subprocess
import winreg

from .ps import CREATE_NO_WINDOW
from . import security

HKCU = winreg.HKEY_CURRENT_USER
HKLM = winreg.HKEY_LOCAL_MACHINE

# Win11 classic right-click menu lives behind this CLSID
_CLASSIC_MENU_CLSID = r"Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}"
_CLASSIC_MENU_INPROC = _CLASSIC_MENU_CLSID + r"\InprocServer32"


def _win_build():
    try:
        k = winreg.OpenKey(HKLM, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
        try:
            v, _ = winreg.QueryValueEx(k, "CurrentBuildNumber")
            return int(v)
        finally:
            winreg.CloseKey(k)
    except (OSError, ValueError):
        return 0


def _is_win11():
    return _win_build() >= 22000

# Each tweak:
#   key, cat, label, help, where (human path), hive, path, name, kind, on, off,
#   admin (needs elevation), restart_explorer, extra [(name, on, off)] for multi-value
_TWEAKS = [
    # ---- performance ----
    {"key": "game_mode", "cat": "Performance", "label": "Enable Game Mode",
     "help": "Prioritises the foreground game and pauses background work while gaming.",
     "where": r"HKCU\Software\Microsoft\GameBar\AllowAutoGameMode",
     "hive": HKCU, "path": r"Software\Microsoft\GameBar", "name": "AllowAutoGameMode",
     "kind": "dword", "on": 1, "off": 0},
    {"key": "hags", "cat": "Performance", "label": "Hardware-accelerated GPU scheduling",
     "help": "Lets the GPU manage its own memory — can reduce latency. Needs a reboot.",
     "where": r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers\HwSchMode",
     "hive": HKLM, "path": r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "name": "HwSchMode",
     "kind": "dword", "on": 2, "off": 1, "admin": True, "restart": "reboot"},
    {"key": "bg_apps", "cat": "Performance", "label": "Stop background Store apps",
     "help": "Stops UWP/Store apps running in the background to free CPU and battery.",
     "where": r"HKCU\…\BackgroundAccessApplications\GlobalUserDisabled",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications",
     "name": "GlobalUserDisabled", "kind": "dword", "on": 1, "off": 0},

    # ---- privacy ----
    {"key": "advertising_id", "cat": "Privacy", "label": "Turn off advertising ID",
     "help": "Stops apps building a cross-system ad profile about you.",
     "where": r"HKCU\…\AdvertisingInfo\Enabled",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo",
     "name": "Enabled", "kind": "dword", "on": 0, "off": 1},
    {"key": "tailored", "cat": "Privacy", "label": "Turn off tailored experiences",
     "help": "Stops Windows using your diagnostic data to personalise tips and ads.",
     "where": r"HKCU\…\Privacy\TailoredExperiencesWithDiagnosticDataEnabled",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\Privacy",
     "name": "TailoredExperiencesWithDiagnosticDataEnabled", "kind": "dword", "on": 0, "off": 1},
    {"key": "start_suggestions", "cat": "Privacy", "label": "Hide Start menu suggestions",
     "help": "Removes promoted/suggested apps from the Start menu.",
     "where": r"HKCU\…\ContentDeliveryManager\SystemPaneSuggestionsEnabled",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
     "name": "SystemPaneSuggestionsEnabled", "kind": "dword", "on": 0, "off": 1},
    {"key": "tips", "cat": "Privacy", "label": "Turn off tips & suggestions",
     "help": "Stops Windows tips, tricks and suggestion notifications.",
     "where": r"HKCU\…\ContentDeliveryManager\SubscribedContent-338389Enabled",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
     "name": "SubscribedContent-338389Enabled", "kind": "dword", "on": 0, "off": 1},
    {"key": "bing_search", "cat": "Privacy", "label": "Disable web results in Search",
     "help": "Stops the Start menu search sending queries to Bing.",
     "where": r"HKCU\…\Search\BingSearchEnabled",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\Search",
     "name": "BingSearchEnabled", "kind": "dword", "on": 0, "off": 1},
    {"key": "copilot", "cat": "Privacy", "label": "Disable Windows Copilot",
     "help": "Turns off the Copilot assistant via policy.",
     "where": r"HKCU\…\Policies\…\WindowsCopilot\TurnOffWindowsCopilot",
     "hive": HKCU, "path": r"Software\Policies\Microsoft\Windows\WindowsCopilot",
     "name": "TurnOffWindowsCopilot", "kind": "dword", "on": 1, "off": 0},
    {"key": "recall", "cat": "Privacy", "label": "Disable Windows Recall",
     "help": "Stops the AI Recall feature from saving snapshots of your activity.",
     "where": r"HKCU\…\Policies\…\WindowsAI\DisableAIDataAnalysis",
     "hive": HKCU, "path": r"Software\Policies\Microsoft\Windows\WindowsAI",
     "name": "DisableAIDataAnalysis", "kind": "dword", "on": 1, "off": 0},
    {"key": "location", "cat": "Privacy", "label": "Deny location access",
     "help": "Sets the system location permission to Deny for apps.",
     "where": r"HKCU\…\CapabilityAccessManager\ConsentStore\location\Value",
     "hive": HKCU,
     "path": r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location",
     "name": "Value", "kind": "sz", "on": "Deny", "off": "Allow"},
    {"key": "telemetry", "cat": "Privacy", "label": "Minimise diagnostic data",
     "help": "Caps Windows telemetry at the lowest policy level.",
     "where": r"HKLM\…\Policies\…\DataCollection\AllowTelemetry",
     "hive": HKLM, "path": r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
     "name": "AllowTelemetry", "kind": "dword", "on": 0, "off": 1, "admin": True},

    # ---- interface ----
    {"key": "taskbar_left", "cat": "Interface", "label": "Left-align the taskbar",
     "help": "Moves taskbar icons to the left like Windows 10.",
     "where": r"HKCU\…\Explorer\Advanced\TaskbarAl",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
     "name": "TaskbarAl", "kind": "dword", "on": 0, "off": 1, "restart": "explorer"},
    {"key": "show_ext", "cat": "Interface", "label": "Show file extensions",
     "help": "Always shows .exe, .docx, etc. — safer for spotting fake files.",
     "where": r"HKCU\…\Explorer\Advanced\HideFileExt",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
     "name": "HideFileExt", "kind": "dword", "on": 0, "off": 1, "restart": "explorer"},
    {"key": "show_hidden", "cat": "Interface", "label": "Show hidden files",
     "help": "Reveals hidden files and folders in Explorer.",
     "where": r"HKCU\…\Explorer\Advanced\Hidden",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
     "name": "Hidden", "kind": "dword", "on": 1, "off": 2, "restart": "explorer"},
    {"key": "clock_seconds", "cat": "Interface", "label": "Show seconds in the clock",
     "help": "Adds seconds to the taskbar clock.",
     "where": r"HKCU\…\Explorer\Advanced\ShowSecondsInSystemClock",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
     "name": "ShowSecondsInSystemClock", "kind": "dword", "on": 1, "off": 0, "restart": "explorer"},
    {"key": "dark_mode", "cat": "Interface", "label": "Dark mode",
     "help": "Switches apps and the system to the dark theme.",
     "where": r"HKCU\…\Themes\Personalize\AppsUseLightTheme",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
     "name": "AppsUseLightTheme", "kind": "dword", "on": 0, "off": 1,
     "extra": [("SystemUsesLightTheme", 0, 1)]},
    {"key": "explorer_thispc", "cat": "Interface", "label": "Open Explorer to “This PC”",
     "help": "Opens File Explorer to This PC instead of Quick Access / Home.",
     "where": r"HKCU\…\Explorer\Advanced\LaunchTo",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
     "name": "LaunchTo", "kind": "dword", "on": 1, "off": 2, "restart": "explorer"},

    # ---- ads & noise ----
    {"key": "lockscreen_ads", "cat": "Ads & noise", "label": "Kill lock-screen ads & tips",
     "help": "Stops the “fun facts, tips & tricks” advertising overlay on the Spotlight lock screen.",
     "where": r"HKCU\…\ContentDeliveryManager\RotatingLockScreenOverlayEnabled",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
     "name": "RotatingLockScreenOverlayEnabled", "kind": "dword", "on": 0, "off": 1,
     "extra": [("SubscribedContent-338387Enabled", 0, 1)]},
    {"key": "settings_ads", "cat": "Ads & noise", "label": "Hide suggestions in Settings",
     "help": "Removes promoted/suggested content from the Settings app.",
     "where": r"HKCU\…\ContentDeliveryManager\SubscribedContent-338393Enabled",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
     "name": "SubscribedContent-338393Enabled", "kind": "dword", "on": 0, "off": 1,
     "extra": [("SubscribedContent-353694Enabled", 0, 1), ("SubscribedContent-353696Enabled", 0, 1)]},
    {"key": "widgets", "cat": "Ads & noise", "label": "Hide the taskbar Widgets/news button",
     "help": "Removes the weather/news Widgets button from the taskbar.",
     "where": r"HKCU\…\Explorer\Advanced\TaskbarDa",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
     "name": "TaskbarDa", "kind": "dword", "on": 0, "off": 1, "restart": "explorer"},
    {"key": "verbose_login", "cat": "Ads & noise", "label": "Verbose sign-in messages",
     "help": "Shows detailed “Applying settings…” status at sign-in/out — useful for diagnosing slow logons. Needs a reboot.",
     "where": r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System\VerboseStatus",
     "hive": HKLM, "path": r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System",
     "name": "VerboseStatus", "kind": "dword", "on": 1, "off": 0, "admin": True, "restart": "reboot"},

    # ---- shutdown ----
    {"key": "faster_shutdown", "cat": "Performance", "label": "Faster shutdown (force hung apps)",
     "help": "Shortens how long Windows waits for unresponsive apps and auto-closes them at shutdown. "
             "Slight risk of losing unsaved work in a frozen app. Sign out to apply.",
     "where": r"HKCU\Control Panel\Desktop\AutoEndTasks (+ HungAppTimeout, WaitToKillAppTimeout)",
     "hive": HKCU, "path": r"Control Panel\Desktop",
     "name": "AutoEndTasks", "kind": "sz", "on": "1", "off": "0",
     "extra": [("HungAppTimeout", "2000", "5000"), ("WaitToKillAppTimeout", "2000", "20000")]},
]

# Special tweaks that aren't a simple registry value (handled explicitly below)
_SPECIAL = [
    {"key": "classic_menu", "cat": "Interface", "label": "Classic right-click menu",
     "help": "Restores the full Windows 10 context menu (no “Show more options”). Restarts Explorer.",
     "where": _CLASSIC_MENU_CLSID + r"\InprocServer32 (empty default)",
     "special": "classic_menu", "restart": "explorer", "win11_only": True},
    {"key": "hibernation", "cat": "Performance", "label": "Enable hibernation",
     "help": "Turns hibernation on (powercfg /hibernate on) and restores the Hibernate option / hiberfil.sys.",
     "where": r"powercfg /hibernate · HKLM\SYSTEM\CurrentControlSet\Control\Power\HibernateEnabled",
     "special": "hibernation", "admin": True},
]

_BY_KEY = {t["key"]: t for t in _TWEAKS}
_BY_KEY.update({t["key"]: t for t in _SPECIAL})


def _key_exists(hive, path):
    try:
        winreg.CloseKey(winreg.OpenKey(hive, path))
        return True
    except OSError:
        return False


def _delete_tree(hive, path):
    """Delete a key and any subkeys (winreg.DeleteKey only removes leaf keys)."""
    try:
        k = winreg.OpenKey(hive, path, 0, winreg.KEY_ALL_ACCESS)
    except OSError:
        return
    try:
        while True:
            try:
                sub = winreg.EnumKey(k, 0)
            except OSError:
                break
            _delete_tree(hive, path + "\\" + sub)
    finally:
        winreg.CloseKey(k)
    try:
        winreg.DeleteKey(hive, path)
    except OSError:
        pass


def _special_enabled(key):
    if key == "classic_menu":
        return _key_exists(HKCU, _CLASSIC_MENU_INPROC)
    if key == "hibernation":
        return _read(HKLM, r"SYSTEM\CurrentControlSet\Control\Power", "HibernateEnabled", "dword") == 1
    return False


def _set_special(key, enable):
    if key == "classic_menu":
        if enable:
            k = winreg.CreateKeyEx(HKCU, _CLASSIC_MENU_INPROC, 0, winreg.KEY_SET_VALUE)
            try:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "")
            finally:
                winreg.CloseKey(k)
        else:
            _delete_tree(HKCU, _CLASSIC_MENU_CLSID)
        return {"ok": True, "restart": "explorer"}
    if key == "hibernation":
        r = subprocess.run(["powercfg", "/hibernate", "on" if enable else "off"],
                           capture_output=True, timeout=15, creationflags=CREATE_NO_WINDOW)
        if r.returncode == 0:
            return {"ok": True}
        return {"ok": False, "error": "powercfg failed — hibernation may be blocked by firmware or policy."}
    return {"ok": False, "error": "Unknown tweak."}


def _read(hive, path, name, kind):
    try:
        k = winreg.OpenKey(hive, path)
        try:
            v, _ = winreg.QueryValueEx(k, name)
            return v
        finally:
            winreg.CloseKey(k)
    except OSError:
        return None


def _write(hive, path, name, kind, value):
    k = winreg.CreateKeyEx(hive, path, 0, winreg.KEY_SET_VALUE)
    try:
        regtype = winreg.REG_DWORD if kind == "dword" else winreg.REG_SZ
        winreg.SetValueEx(k, name, 0, regtype, value)
    finally:
        winreg.CloseKey(k)


def get_tweaks():
    admin = security.is_admin()
    win11 = _is_win11()
    items = []
    for t in _TWEAKS:
        current = _read(t["hive"], t["path"], t["name"], t["kind"])
        items.append({
            "key": t["key"], "cat": t["cat"], "label": t["label"], "help": t["help"],
            "where": t["where"], "enabled": current == t["on"],
            "admin": t.get("admin", False),
            "restart": t.get("restart"),
        })
    for t in _SPECIAL:
        if t.get("win11_only") and not win11:
            continue
        items.append({
            "key": t["key"], "cat": t["cat"], "label": t["label"], "help": t["help"],
            "where": t["where"], "enabled": _special_enabled(t["key"]),
            "admin": t.get("admin", False),
            "restart": t.get("restart"),
        })
    return {"items": items, "is_admin": admin}


def set_tweak(key, enable=True):
    t = _BY_KEY.get(key)
    if not t:
        return {"ok": False, "error": "Unknown tweak."}
    if t.get("admin") and not security.is_admin():
        return {"ok": False, "error": f"'{t['label']}' needs elevation — use Run as admin."}
    if t.get("special"):
        try:
            return _set_special(key, enable)
        except OSError as e:
            return {"ok": False, "error": str(e)}
    value = t["on"] if enable else t["off"]
    try:
        _write(t["hive"], t["path"], t["name"], t["kind"], value)
        for name, on, off in t.get("extra", []):
            _write(t["hive"], t["path"], name, t["kind"], on if enable else off)
        return {"ok": True, "restart": t.get("restart")}
    except OSError as e:
        return {"ok": False, "error": str(e)}


# ---- power plans ----------------------------------------------------------------

_PLANS = {
    "balanced": ("381b4222-f694-41f0-9685-ff5bb260df2e", "Balanced"),
    "high": ("8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", "High performance"),
    "ultimate": ("e9a42b02-d5df-448d-aa00-03f14749eb61", "Ultimate performance"),
}


def set_power_plan(which):
    guid, label = _PLANS.get(which, (None, None))
    if not guid:
        return {"ok": False, "error": "Unknown plan."}
    try:
        # Ultimate plan must be duplicated in before it can be activated
        if which == "ultimate":
            subprocess.run(["powercfg", "-duplicatescheme", guid], capture_output=True,
                           timeout=15, creationflags=CREATE_NO_WINDOW)
        r = subprocess.run(["powercfg", "-setactive", guid], capture_output=True,
                           timeout=15, creationflags=CREATE_NO_WINDOW)
        if r.returncode == 0:
            return {"ok": True, "label": label}
        return {"ok": False, "error": f"This plan isn't available on this machine ({label})."}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# Bulk "calm this computer down" — the noise-reducing tweaks, applied together
_QUIET_KEYS = ["lockscreen_ads", "settings_ads", "tips", "start_suggestions", "widgets",
               "bing_search", "advertising_id", "tailored"]


def apply_quiet_mode():
    applied, skipped = [], []
    for key in _QUIET_KEYS:
        t = _BY_KEY.get(key)
        if not t:
            continue
        if t.get("admin") and not security.is_admin():
            skipped.append(t["label"])
            continue
        r = set_tweak(key, True)
        (applied if r.get("ok") else skipped).append(t["label"])
    return {"ok": True, "applied": applied, "skipped": skipped,
            "restart_explorer": True}


def restart_explorer():
    try:
        subprocess.run(["taskkill", "/f", "/im", "explorer.exe"], capture_output=True,
                       timeout=15, creationflags=CREATE_NO_WINDOW)
        subprocess.Popen(["explorer.exe"])
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
