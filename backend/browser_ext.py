"""Browser extension audit — Chrome / Edge (Chromium profiles) and Firefox."""

import glob
import json
import os

_CHROMIUM = [
    ("Chrome", os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data")),
    ("Edge", os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Edge", "User Data")),
    ("Brave", os.path.join(os.environ.get("LOCALAPPDATA", ""), "BraveSoftware", "Brave-Browser", "User Data")),
]


def get_extensions():
    found = []
    for browser, root in _CHROMIUM:
        if os.path.isdir(root):
            found.extend(_chromium_extensions(browser, root))
    found.extend(_firefox_extensions())
    found.sort(key=lambda x: (x["browser"], x["profile"], x["name"].lower()))
    return found


def _chromium_extensions(browser, root):
    out = []
    for profile_dir in glob.glob(os.path.join(root, "*")):
        profile = os.path.basename(profile_dir)
        if profile not in ("Default",) and not profile.startswith("Profile"):
            continue
        states = _chromium_states(profile_dir)
        ext_root = os.path.join(profile_dir, "Extensions")
        if not os.path.isdir(ext_root):
            continue
        for ext_id in os.listdir(ext_root):
            versions = sorted(glob.glob(os.path.join(ext_root, ext_id, "*")), reverse=True)
            if not versions:
                continue
            manifest_path = os.path.join(versions[0], "manifest.json")
            try:
                with open(manifest_path, encoding="utf-8", errors="replace") as f:
                    manifest = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            name = manifest.get("name", "")
            if name.startswith("__MSG_"):
                name = _resolve_msg(versions[0], manifest, name) or ext_id
            out.append({
                "browser": browser,
                "profile": profile,
                "id": ext_id,
                "name": name,
                "version": manifest.get("version", ""),
                "enabled": states.get(ext_id),
                "permissions": ", ".join(str(p) for p in (manifest.get("permissions") or [])[:8]),
            })
    return out


def _chromium_states(profile_dir):
    """extension id -> enabled bool, from Preferences / Secure Preferences (state 1 = enabled)."""
    states = {}
    for pref_file in ("Preferences", "Secure Preferences"):
        try:
            with open(os.path.join(profile_dir, pref_file), encoding="utf-8", errors="replace") as f:
                prefs = json.load(f)
            settings = (prefs.get("extensions") or {}).get("settings") or {}
            for ext_id, cfg in settings.items():
                if isinstance(cfg, dict) and "state" in cfg:
                    states[ext_id] = cfg["state"] == 1
                elif isinstance(cfg, dict) and cfg.get("disable_reasons"):
                    states[ext_id] = False
        except (OSError, json.JSONDecodeError):
            continue
    return states


def _resolve_msg(version_dir, manifest, raw):
    """Resolve __MSG_appName__ via _locales/<default_locale>/messages.json."""
    key = raw[6:-2]
    locale = manifest.get("default_locale", "en")
    for loc in (locale, "en", "en_US"):
        path = os.path.join(version_dir, "_locales", loc, "messages.json")
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                messages = json.load(f)
            for k, v in messages.items():
                if k.lower() == key.lower() and isinstance(v, dict):
                    return v.get("message")
        except (OSError, json.JSONDecodeError):
            continue
    return None


def _firefox_extensions():
    out = []
    profiles_root = os.path.join(os.environ.get("APPDATA", ""), "Mozilla", "Firefox", "Profiles")
    for ext_json in glob.glob(os.path.join(profiles_root, "*", "extensions.json")):
        profile = os.path.basename(os.path.dirname(ext_json))
        try:
            with open(ext_json, encoding="utf-8", errors="replace") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        for addon in data.get("addons", []):
            if addon.get("type") != "extension" or addon.get("location") != "app-profile":
                continue
            out.append({
                "browser": "Firefox",
                "profile": profile,
                "id": addon.get("id", ""),
                "name": (addon.get("defaultLocale") or {}).get("name") or addon.get("id", ""),
                "version": addon.get("version", ""),
                "enabled": addon.get("active"),
                "permissions": "",
            })
    return out
