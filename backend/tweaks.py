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
HKCR = winreg.HKEY_CLASSES_ROOT

# "Take ownership" right-click verb — takeown + icacls, for files and folders.
_TAKEOWN_FILE = r'cmd.exe /c takeown /f "%1" && icacls "%1" /grant *S-1-5-32-544:F'
_TAKEOWN_DIR = r'cmd.exe /c takeown /f "%1" /r /d y && icacls "%1" /grant *S-1-5-32-544:F /t'
# (*S-1-5-32-544 = the Administrators group SID — locale-independent, unlike "administrators")

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

    # ---- more performance ----
    {"key": "transparency", "cat": "Performance", "label": "Disable transparency effects",
     "help": "Turns off the Acrylic/Mica transparency in the taskbar, Start and title bars — a little "
             "less GPU work, and crisper on weak integrated graphics.",
     "where": r"HKCU\…\Themes\Personalize\EnableTransparency",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
     "name": "EnableTransparency", "kind": "dword", "on": 0, "off": 1},
    {"key": "window_animations", "cat": "Performance", "label": "Disable window animations",
     "help": "Stops the minimise/maximise window animations for snappier-feeling windows. Sign out to apply.",
     "where": r"HKCU\Control Panel\Desktop\WindowMetrics\MinAnimate",
     "hive": HKCU, "path": r"Control Panel\Desktop\WindowMetrics",
     "name": "MinAnimate", "kind": "sz", "on": "0", "off": "1", "restart": "explorer"},

    # ---- more privacy ----
    {"key": "activity_history", "cat": "Privacy", "label": "Disable Activity History / Timeline",
     "help": "Stops Windows collecting and uploading your activity history (the Timeline feed).",
     "where": r"HKLM\…\Policies\…\System\PublishUserActivities (+ EnableActivityFeed, UploadUserActivities)",
     "hive": HKLM, "path": r"SOFTWARE\Policies\Microsoft\Windows\System",
     "name": "PublishUserActivities", "kind": "dword", "on": 0, "off": 1, "admin": True,
     "extra": [("EnableActivityFeed", 0, 1), ("UploadUserActivities", 0, 1)]},
    {"key": "cortana", "cat": "Privacy", "label": "Disable Cortana",
     "help": "Turns Cortana off via policy (mainly affects Windows 10; harmless on 11).",
     "where": r"HKLM\…\Policies\…\Windows Search\AllowCortana",
     "hive": HKLM, "path": r"SOFTWARE\Policies\Microsoft\Windows\Windows Search",
     "name": "AllowCortana", "kind": "dword", "on": 0, "off": 1, "admin": True},

    # ---- more interface ----
    {"key": "taskview_button", "cat": "Interface", "label": "Hide the Task View button",
     "help": "Removes the Task View (virtual desktops) button from the taskbar.",
     "where": r"HKCU\…\Explorer\Advanced\ShowTaskViewButton",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
     "name": "ShowTaskViewButton", "kind": "dword", "on": 0, "off": 1, "restart": "explorer"},
    {"key": "compact_explorer", "cat": "Interface", "label": "Compact view in File Explorer",
     "help": "Tightens the row spacing in File Explorer (the pre-Win11 density).",
     "where": r"HKCU\…\Explorer\Advanced\UseCompactMode",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
     "name": "UseCompactMode", "kind": "dword", "on": 1, "off": 0, "restart": "explorer"},
    {"key": "aero_shake", "cat": "Interface", "label": "Disable Aero Shake",
     "help": "Stops a title-bar shake from minimising every other window — handy if you trigger it by accident.",
     "where": r"HKCU\…\Explorer\Advanced\DisallowShaking",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
     "name": "DisallowShaking", "kind": "dword", "on": 1, "off": 0, "restart": "explorer"},

    # ---- more ads & noise ----
    {"key": "explorer_sync_ads", "cat": "Ads & noise", "label": "Hide File Explorer promo ads",
     "help": "Stops the “sync provider” notifications — the OneDrive/Office ads that appear as banners in File Explorer.",
     "where": r"HKCU\…\Explorer\Advanced\ShowSyncProviderNotifications",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
     "name": "ShowSyncProviderNotifications", "kind": "dword", "on": 0, "off": 1, "restart": "explorer"},
    {"key": "finish_setup", "cat": "Ads & noise", "label": "Stop “Finish setting up” nags",
     "help": "Disables the full-screen “Let's finish setting up your device” prompt after updates.",
     "where": r"HKCU\…\UserProfileEngagement\ScoobeSystemSettingEnabled",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\UserProfileEngagement",
     "name": "ScoobeSystemSettingEnabled", "kind": "dword", "on": 0, "off": 1},
    {"key": "welcome_tips", "cat": "Ads & noise", "label": "Hide post-update “welcome” page",
     "help": "Stops the “Get the most out of Windows” welcome experience shown after updates and on first sign-in.",
     "where": r"HKCU\…\ContentDeliveryManager\SubscribedContent-310093Enabled",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
     "name": "SubscribedContent-310093Enabled", "kind": "dword", "on": 0, "off": 1},

    # ---- gaming ----
    {"key": "mouse_accel", "cat": "Gaming", "label": "Disable mouse acceleration",
     "help": "Turns off “enhance pointer precision” so cursor movement maps 1:1 — what most gamers want. Sign out to apply.",
     "where": r"HKCU\Control Panel\Mouse\MouseSpeed (+ MouseThreshold1, MouseThreshold2)",
     "hive": HKCU, "path": r"Control Panel\Mouse",
     "name": "MouseSpeed", "kind": "sz", "on": "0", "off": "1",
     "extra": [("MouseThreshold1", "0", "6"), ("MouseThreshold2", "0", "10")]},
    {"key": "game_dvr", "cat": "Gaming", "label": "Disable Game DVR background recording",
     "help": "Stops the Xbox Game Bar continuously recording in the background — frees CPU/GPU during games.",
     "where": r"HKCU\System\GameConfigStore\GameDVR_Enabled",
     "hive": HKCU, "path": r"System\GameConfigStore",
     "name": "GameDVR_Enabled", "kind": "dword", "on": 0, "off": 1},
    {"key": "net_throttle", "cat": "Gaming", "label": "Disable network throttling",
     "help": "Lifts the multimedia network-throttling cap (helps online-game latency on fast links). Needs a reboot.",
     "where": r"HKLM\…\Multimedia\SystemProfile\NetworkThrottlingIndex (+ SystemResponsiveness)",
     "hive": HKLM, "path": r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile",
     "name": "NetworkThrottlingIndex", "kind": "dword", "on": 0xFFFFFFFF, "off": 10, "admin": True,
     "restart": "reboot", "extra": [("SystemResponsiveness", 0, 20)]},

    # ---- more interface ----
    {"key": "menu_delay", "cat": "Interface", "label": "Snappier menus (no show delay)",
     "help": "Removes the small delay before menus and submenus open. Sign out (or restart Explorer) to apply.",
     "where": r"HKCU\Control Panel\Desktop\MenuShowDelay",
     "hive": HKCU, "path": r"Control Panel\Desktop",
     "name": "MenuShowDelay", "kind": "sz", "on": "0", "off": "400", "restart": "explorer"},
    {"key": "nav_expand", "cat": "Interface", "label": "Expand nav pane to current folder",
     "help": "Makes the Explorer folder tree expand to, and show all folders for, wherever you are.",
     "where": r"HKCU\…\Explorer\Advanced\NavPaneExpandToCurrentFolder (+ NavPaneShowAllFolders)",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
     "name": "NavPaneExpandToCurrentFolder", "kind": "dword", "on": 1, "off": 0, "restart": "explorer",
     "extra": [("NavPaneShowAllFolders", 1, 0)]},

    # ---- more privacy ----
    {"key": "track_apps", "cat": "Privacy", "label": "Stop tracking most-used apps",
     "help": "Turns off the “let Windows track app launches to improve Start and search” setting.",
     "where": r"HKCU\…\Explorer\Advanced\Start_TrackProgs",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
     "name": "Start_TrackProgs", "kind": "dword", "on": 0, "off": 1, "restart": "explorer"},
    {"key": "inking_typing", "cat": "Privacy", "label": "Disable inking & typing personalization",
     "help": "Stops Windows collecting your handwriting and typing samples to build a personal dictionary.",
     "where": r"HKCU\Software\Microsoft\InputPersonalization\RestrictImplicitTextCollection (+ Ink)",
     "hive": HKCU, "path": r"Software\Microsoft\InputPersonalization",
     "name": "RestrictImplicitTextCollection", "kind": "dword", "on": 1, "off": 0,
     "extra": [("RestrictImplicitInkCollection", 1, 0)]},
    {"key": "lang_web", "cat": "Privacy", "label": "Don't share language list with sites",
     "help": "Opts out of letting websites see your full preferred-language list (a fingerprinting signal).",
     "where": r"HKCU\Control Panel\International\User Profile\HttpAcceptLanguageOptOut",
     "hive": HKCU, "path": r"Control Panel\International\User Profile",
     "name": "HttpAcceptLanguageOptOut", "kind": "dword", "on": 1, "off": 0},

    # ---- power / startup ----
    {"key": "fast_startup", "cat": "Performance", "label": "Disable Fast Startup",
     "help": "Turns off hybrid shutdown so “Shut down” does a true full shutdown. Fixes dual-boot clock/driver "
             "oddities and ensures a clean boot — the classic “did you really restart?” fix. Needs a reboot.",
     "where": r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power\HiberbootEnabled",
     "hive": HKLM, "path": r"SYSTEM\CurrentControlSet\Control\Session Manager\Power",
     "name": "HiberbootEnabled", "kind": "dword", "on": 0, "off": 1, "admin": True, "restart": "reboot"},

    # ---- more interface / file management ----
    {"key": "full_path", "cat": "Interface", "label": "Show full path in the title bar",
     "help": "Shows the complete folder path in the File Explorer title/address bar instead of just the folder name.",
     "where": r"HKCU\…\Explorer\CabinetState\FullPath",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\CabinetState",
     "name": "FullPath", "kind": "dword", "on": 1, "off": 0, "restart": "explorer"},
    {"key": "taskbar_endtask", "cat": "Interface", "label": "Add “End task” to taskbar right-click",
     "help": "Adds an End task item to the taskbar right-click menu to kill a hung app without Task Manager "
             "(Windows 11 23H2 and later).",
     "where": r"HKCU\…\Explorer\Advanced\TaskbarDeveloperSettings\TaskbarEndTask",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced\TaskbarDeveloperSettings",
     "name": "TaskbarEndTask", "kind": "dword", "on": 1, "off": 0, "restart": "explorer"},

    # ---- more ads & noise ----
    {"key": "suggested_actions", "cat": "Ads & noise", "label": "Disable suggested actions",
     "help": "Stops the pop-up that offers actions when you copy a date or phone number (Windows 11).",
     "where": r"HKCU\…\SmartActionPlatform\SmartClipboard\Disabled",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\SmartActionPlatform\SmartClipboard",
     "name": "Disabled", "kind": "dword", "on": 1, "off": 0},
    {"key": "start_iris", "cat": "Ads & noise", "label": "Hide Start menu recommendations",
     "help": "Removes the “Recommended for you” tips, shortcuts and new-app promos from the Start menu "
             "(Windows 11 23H2 and later).",
     "where": r"HKCU\…\Explorer\Advanced\Start_IrisRecommendations",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
     "name": "Start_IrisRecommendations", "kind": "dword", "on": 0, "off": 1, "restart": "explorer"},

    # ---- more interface / desktop ----
    {"key": "desktop_thispc", "cat": "Interface", "label": "Show “This PC” on the desktop",
     "help": "Puts the This PC icon back on the desktop (hidden by default on a clean install).",
     "where": r"HKCU\…\Explorer\HideDesktopIcons\NewStartPanel\{20D04FE0-3AEA-1069-A2D8-08002B30309D}",
     "hive": HKCU, "path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\HideDesktopIcons\NewStartPanel",
     "name": "{20D04FE0-3AEA-1069-A2D8-08002B30309D}", "kind": "dword", "on": 0, "off": 1, "restart": "explorer"},
    {"key": "drive_letters_first", "cat": "Interface", "label": "Drive letters before names",
     "help": "Shows volumes as “C: Windows” instead of “Windows (C:)” — easier to scan in Explorer.",
     "where": r"HKLM\…\Explorer\ShowDriveLettersFirst",
     "hive": HKLM, "path": r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer",
     "name": "ShowDriveLettersFirst", "kind": "dword", "on": 4, "off": 0, "admin": True, "restart": "explorer"},

    # ---- network & power ----
    {"key": "disable_ipv6", "cat": "Network & power", "label": "Disable IPv6",
     "help": "Disables the IPv6 components via DisabledComponents (0xFF). A troubleshooting step for "
             "some VPN / connectivity faults — re-enable if anything that needs IPv6 breaks. Needs a reboot.",
     "where": r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip6\Parameters\DisabledComponents",
     "hive": HKLM, "path": r"SYSTEM\CurrentControlSet\Services\Tcpip6\Parameters",
     "name": "DisabledComponents", "kind": "dword", "on": 0xFF, "off": 0, "admin": True, "restart": "reboot"},
    {"key": "hibernate_menu", "cat": "Network & power", "label": "Show Hibernate in the power menu",
     "help": "Adds Hibernate to the Start power menu (requires hibernation to be enabled — see the Performance tab).",
     "where": r"HKLM\…\Explorer\FlyoutMenuSettings\ShowHibernateOption",
     "hive": HKLM, "path": r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\FlyoutMenuSettings",
     "name": "ShowHibernateOption", "kind": "dword", "on": 1, "off": 0, "admin": True},
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
    {"key": "take_ownership", "cat": "Interface", "label": "Add “Take ownership” to right-click",
     "help": "Adds a Take ownership item to the right-click menu for files and folders — grants your "
             "Administrators group full control in one click (the “access denied, can't delete” fix).",
     "where": r"HKCR\*\shell\TakeOwnership and HKCR\Directory\shell\TakeOwnership (takeown + icacls)",
     "special": "take_ownership", "admin": True},
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
    if key == "take_ownership":
        return _key_exists(HKCR, r"*\shell\TakeOwnership\command")
    return False


def _add_takeown_verb(parent, command):
    """Create a 'TakeOwnership' shell verb under an HKCR class (e.g. '*' or 'Directory')."""
    k = winreg.CreateKeyEx(HKCR, parent + r"\shell\TakeOwnership", 0, winreg.KEY_SET_VALUE)
    try:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "Take ownership")
        winreg.SetValueEx(k, "HasLUAShield", 0, winreg.REG_SZ, "")        # admin shield icon
        winreg.SetValueEx(k, "NoWorkingDirectory", 0, winreg.REG_SZ, "")
    finally:
        winreg.CloseKey(k)
    c = winreg.CreateKeyEx(HKCR, parent + r"\shell\TakeOwnership\command", 0, winreg.KEY_SET_VALUE)
    try:
        winreg.SetValueEx(c, "", 0, winreg.REG_SZ, command)
        winreg.SetValueEx(c, "IsolatedCommand", 0, winreg.REG_SZ, command)
    finally:
        winreg.CloseKey(c)


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
    if key == "take_ownership":
        if enable:
            _add_takeown_verb("*", _TAKEOWN_FILE)             # files
            _add_takeown_verb("Directory", _TAKEOWN_DIR)      # folders
        else:
            _delete_tree(HKCR, r"*\shell\TakeOwnership")
            _delete_tree(HKCR, r"Directory\shell\TakeOwnership")
        return {"ok": True}
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
               "bing_search", "advertising_id", "tailored",
               "explorer_sync_ads", "finish_setup", "welcome_tips",
               "suggested_actions", "start_iris"]


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
