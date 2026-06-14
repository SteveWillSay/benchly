"""Environment & PATH audit — the baffling 'command not found / wrong version' fixer.

A broken or bloated PATH is a constant, hard-to-spot source of "the tool won't launch"
or "the wrong version runs". This reads the Machine and User PATH straight from the
registry and checks each entry — missing folder, duplicate, quoting/space issues,
overall length — and lists the other environment variables, flagging any that point at
a folder that no longer exists. Read-only by default; cleaning broken/duplicate PATH
entries is optional, backs up the prior value and is reversible.
"""

import os
import winreg

from . import security

HKLM = winreg.HKEY_LOCAL_MACHINE
HKCU = winreg.HKEY_CURRENT_USER
_SYS_ENV = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
_USER_ENV = r"Environment"


def _read_raw_path(root, sub):
    """Read PATH WITHOUT expanding %VARS% (so we see what's actually stored)."""
    try:
        k = winreg.OpenKey(root, sub)
        try:
            v, _ = winreg.QueryValueEx(k, "Path")
            return v or ""
        finally:
            winreg.CloseKey(k)
    except OSError:
        return ""


def _analyse(raw, scope):
    entries, seen = [], {}
    parts = [p for p in raw.split(";")]
    for p in parts:
        item = p.strip()
        if not item:
            continue
        expanded = os.path.expandvars(item)
        low = expanded.lower().rstrip("\\")
        problems = []
        if not os.path.isdir(expanded):
            problems.append("folder doesn't exist")
        if low in seen:
            problems.append("duplicate")
        else:
            seen[low] = True
        if '"' in item:
            problems.append("contains quotes")
        if item != item.strip():
            problems.append("leading/trailing space")
        entries.append({"scope": scope, "value": item, "expanded": expanded,
                        "problems": problems, "ok": not problems})
    return entries, len(raw)


def env_audit():
    machine, mlen = _analyse(_read_raw_path(HKLM, _SYS_ENV), "Machine")
    user, ulen = _analyse(_read_raw_path(HKCU, _USER_ENV), "User")
    all_entries = machine + user
    problems = [e for e in all_entries if not e["ok"]]

    # other environment variables that point at a missing folder
    var_warnings = []
    for name in ("TEMP", "TMP", "JAVA_HOME", "GOPATH", "PYTHONHOME", "ANDROID_HOME",
                 "NODE_PATH", "M2_HOME", "DOTNET_ROOT"):
        val = os.environ.get(name)
        if val and os.path.sep in val and not os.path.isdir(os.path.expandvars(val)):
            var_warnings.append({"name": name, "value": val})

    total_len = mlen + ulen
    notes = []
    if total_len > 2000:
        notes.append(f"PATH is long ({total_len} chars) — close to limits that can truncate it.")
    return {
        "ok": True,
        "entries": all_entries,
        "problem_count": len(problems),
        "machine_len": mlen, "user_len": ulen, "total_len": total_len,
        "var_warnings": var_warnings,
        "notes": notes,
    }


def clean_path(scope):
    """Remove broken (missing-folder) and duplicate entries from the PATH. Reversible:
    the prior raw value is returned so it can be restored."""
    if scope == "Machine" and not security.is_admin():
        return {"ok": False, "error": "Editing the Machine PATH needs elevation — use Run as admin."}
    root, sub = (HKLM, _SYS_ENV) if scope == "Machine" else (HKCU, _USER_ENV)
    raw = _read_raw_path(root, sub)
    kept, seen = [], set()
    for p in raw.split(";"):
        item = p.strip()
        if not item:
            continue
        expanded = os.path.expandvars(item)
        low = expanded.lower().rstrip("\\")
        if not os.path.isdir(expanded):
            continue
        if low in seen:
            continue
        seen.add(low)
        kept.append(item)
    new_val = ";".join(kept)
    if new_val == raw:
        return {"ok": True, "changed": False, "message": "Nothing to clean — PATH is already tidy."}
    try:
        k = winreg.OpenKey(root, sub, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.SetValueEx(k, "Path", 0, winreg.REG_EXPAND_SZ, new_val)
        finally:
            winreg.CloseKey(k)
        return {"ok": True, "changed": True, "prior": raw,
                "where": f"{scope} PATH cleaned (broadcast on next sign-in). Prior value saved for undo."}
    except OSError as e:
        return {"ok": False, "error": str(e)}
