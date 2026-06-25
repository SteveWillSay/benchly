"""Applied policy settings — 'what has Group Policy / MDM actually written here?'

Walks the Windows policy registry hives and enumerates every value found. These
hives are the *effect* of applied GPOs (and most MDM/Intune CSPs) regardless of
where the policy came from — a domain controller, local Group Policy, or an MDM
push all land here — so reading them is the most reliable way for a bench tech to
see exactly which settings have been imposed on a corporate machine.

Grouped by a friendly "area" derived from the registry path (Windows Update,
Microsoft Edge, Defender, …). Strictly READ-ONLY — this module only enumerates
and stringifies registry values; it never creates, writes, or deletes anything.
A clean / unmanaged box legitimately has very few values, which is fine.
"""

import winreg

HKLM = winreg.HKEY_LOCAL_MACHINE
HKCU = winreg.HKEY_CURRENT_USER

# Safety caps — keep the walk fast and bounded on a heavily-managed machine.
_MAX_VALUES = 600
_MAX_DEPTH = 6
_VALUE_REPR_LEN = 200

# (hive handle, friendly hive prefix, sub-key path) for each tree we enumerate.
_ROOTS = [
    (HKLM, r"HKLM", r"SOFTWARE\Policies"),
    (HKLM, r"HKLM", r"SOFTWARE\WOW6432Node\Policies"),
    (HKCU, r"HKCU", r"SOFTWARE\Policies"),
    (HKLM, r"HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies"),
    (HKCU, r"HKCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies"),
]

# Map a readable reg type onto each winreg constant.
_TYPE_NAMES = {
    winreg.REG_SZ: "sz",
    winreg.REG_EXPAND_SZ: "expand_sz",
    winreg.REG_MULTI_SZ: "multi_sz",
    winreg.REG_DWORD: "dword",
    winreg.REG_QWORD: "qword",
    winreg.REG_BINARY: "binary",
    winreg.REG_NONE: "none",
}

# Path-segment → area. First match (case-insensitive, substring) wins, so order
# the more specific products before the broad vendor catch-alls.
_AREA_RULES = [
    ("windowsupdate", "Windows Update"),
    ("wsus", "Windows Update"),
    ("microsoftedge", "Microsoft Edge"),
    ("edge", "Microsoft Edge"),
    ("google\\chrome", "Chrome"),
    ("chrome", "Chrome"),
    ("office", "Microsoft Office"),
    ("windows defender", "Windows Defender"),
    ("microsoft defender", "Windows Defender"),
    ("defender", "Windows Defender"),
    ("microsoft antimalware", "Windows Defender"),
    ("smartscreen", "Windows Defender"),
    ("fve", "BitLocker"),
    ("bitlocker", "BitLocker"),
    ("datacollection", "Telemetry / Data Collection"),
    ("telemetry", "Telemetry / Data Collection"),
    ("explorer", "Explorer / Shell"),
    ("shell", "Explorer / Shell"),
    ("system", "Explorer / Shell"),
    ("personalization", "Explorer / Shell"),
    ("activedesktop", "Explorer / Shell"),
    ("power", "Power"),
    ("network", "Networking"),
    ("tcpip", "Networking"),
    ("firewall", "Networking"),
    ("wcmsvc", "Networking"),
    ("windowsfirewall", "Networking"),
]


def _type_name(reg_type):
    """Readable name for a winreg value type ('dword', 'sz', …)."""
    return _TYPE_NAMES.get(reg_type, f"type_{reg_type}")


def _stringify(data, reg_type):
    """Stringify a registry value, truncating long/binary data to a short repr."""
    try:
        if reg_type == winreg.REG_BINARY and isinstance(data, (bytes, bytearray)):
            text = data[:24].hex(" ")
            if len(data) > 24:
                text += f" … ({len(data)} bytes)"
            return text
        if reg_type == winreg.REG_MULTI_SZ and isinstance(data, (list, tuple)):
            text = "; ".join(str(x) for x in data)
        else:
            text = str(data)
    except Exception:
        return "<unreadable>"
    if len(text) > _VALUE_REPR_LEN:
        text = text[:_VALUE_REPR_LEN] + "…"
    return text


def _area_for(key_path):
    """Derive a friendly area from a full key path; fall back to vendor/product."""
    low = key_path.lower()
    for needle, area in _AREA_RULES:
        if needle in low:
            return area
    # Fall back to the first segment after "Policies\".
    low_marker = low.find("policies\\")
    if low_marker != -1:
        tail = key_path[low_marker + len("policies\\"):]
        seg = tail.split("\\", 1)[0].strip()
        if seg:
            return seg
    return "Other"


def _walk(hive, prefix, subpath, settings, state):
    """Recurse one policy sub-tree, appending {key,name,type,value} dicts.

    `state` carries {"count": int, "truncated": bool} across the whole walk so the
    global value cap is shared by every hive. Never raises — missing keys (a clean
    box) and access-denied (no admin) are both expected and silently skipped.
    """
    if state["count"] >= _MAX_VALUES:
        state["truncated"] = True
        return
    try:
        key = winreg.OpenKey(hive, subpath, 0, winreg.KEY_READ)
    except OSError:
        return  # key absent or access denied — both fine
    try:
        human = f"{prefix}\\{subpath}"
        try:
            n_sub, n_vals, _ = winreg.QueryInfoKey(key)
        except OSError:
            n_sub, n_vals = 0, 0

        for i in range(n_vals):
            if state["count"] >= _MAX_VALUES:
                state["truncated"] = True
                return
            try:
                name, data, reg_type = winreg.EnumValue(key, i)
            except OSError:
                continue
            settings.append({
                "key": human,
                "name": name or "(default)",
                "type": _type_name(reg_type),
                "value": _stringify(data, reg_type),
            })
            state["count"] += 1

        # Depth guard: count separators in the sub-path beyond the policy root.
        if subpath.count("\\") >= _MAX_DEPTH + subpath.lower().count("policies"):
            return
        for i in range(n_sub):
            if state["count"] >= _MAX_VALUES:
                state["truncated"] = True
                return
            try:
                child = winreg.EnumKey(key, i)
            except OSError:
                continue
            _walk(hive, prefix, f"{subpath}\\{child}", settings, state)
    finally:
        winreg.CloseKey(key)


def applied_policies():
    """READ-ONLY snapshot of every policy registry value applied to this machine.

    Returns:
        {
          "ok": True,
          "count": <int total values>,
          "truncated": <bool>,            # hit the safety cap
          "groups": [ {"area": str, "count": int,
                       "settings": [ {"key","name","type","value"}, … ]}, … ],
          "summary": "<one-line plain-English verdict>"
        }
    Sorted by group count desc. Never raises — on total failure returns a clean
    empty result (an unmanaged box legitimately has very few values).
    """
    try:
        settings = []
        state = {"count": 0, "truncated": False}
        for hive, prefix, subpath in _ROOTS:
            _walk(hive, prefix, subpath, settings, state)

        # Group by friendly area.
        buckets = {}
        for s in settings:
            area = _area_for(s["key"])
            buckets.setdefault(area, []).append(s)

        groups = [
            {"area": area, "count": len(items), "settings": items}
            for area, items in buckets.items()
        ]
        groups.sort(key=lambda g: g["count"], reverse=True)

        total = state["count"]
        if total == 0:
            return {
                "ok": True, "count": 0, "truncated": False, "groups": [],
                "summary": "No applied machine policies found — this box looks "
                           "unmanaged.",
            }

        heaviest = groups[0]
        more = " (truncated at the safety cap)" if state["truncated"] else ""
        summary = (
            f"{total} policy setting{'s' if total != 1 else ''} applied across "
            f"{len(groups)} area{'s' if len(groups) != 1 else ''} — heaviest: "
            f"{heaviest['area']} ({heaviest['count']}){more}."
        )
        return {
            "ok": True, "count": total, "truncated": state["truncated"],
            "groups": groups, "summary": summary,
        }
    except Exception:
        return {
            "ok": True, "count": 0, "truncated": False, "groups": [],
            "summary": "No applied machine policies found.",
        }
