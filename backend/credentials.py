"""Mapped drives & saved credentials — the silent auth-failure stuff.

Stale mapped network drives (the red-X 'reconnect' drive) and orphaned saved
credentials are a constant source of mystery sign-in prompts. This lists both —
the drives and where they point, and the Credential Manager *entries* (target and
type only; Windows never exposes the stored secret, and neither does this). Reading
is harmless; removing a stale entry is optional and confirmed.
"""

import re

from .ps import ps_json, as_list, run_ps

_SMB_STATUS = {0: "OK", 1: "Paused", 2: "Disconnected", 3: "Reconnecting",
               4: "Unavailable", 5: "Failed"}


def mapped_drives():
    rows = as_list(ps_json(
        "Get-SmbMapping -ErrorAction SilentlyContinue | "
        "Select-Object LocalPath,RemotePath,@{n='St';e={[string]$_.Status}}", timeout=20))
    drives = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        status = r.get("St")
        if isinstance(status, int):
            status = _SMB_STATUS.get(status, str(status))
        stale = str(status).lower() not in ("ok", "0")
        drives.append({
            "local": r.get("LocalPath") or "—",
            "remote": r.get("RemotePath") or "—",
            "status": status or "—",
            "stale": stale,
        })
    return {"ok": True, "drives": drives,
            "stale": sum(1 for d in drives if d["stale"])}


def stored_credentials():
    """Credential Manager entries — names and types only, never secrets."""
    out = run_ps("cmdkey /list", timeout=15) or ""
    creds, cur = [], {}
    for line in out.splitlines():
        s = line.strip()
        m = re.match(r"Target:\s*(.+)", s)
        if m:
            if cur.get("target"):
                creds.append(cur)
            cur = {"target": m.group(1).strip()}
            continue
        m = re.match(r"Type:\s*(.+)", s)
        if m and cur:
            cur["type"] = m.group(1).strip()
            continue
        m = re.match(r"User:\s*(.+)", s)
        if m and cur:
            cur["user"] = m.group(1).strip()
    if cur.get("target"):
        creds.append(cur)
    # tidy the noisy 'LegacyGeneric:target=' / 'Domain:target=' prefixes for display
    for c in creds:
        t = c["target"]
        c["display"] = re.sub(r"^(LegacyGeneric|Domain|WindowsLive|MicrosoftAccount):target=",
                              "", t).strip() or t
        c.setdefault("type", "—")
        c.setdefault("user", "—")
    return {"ok": True, "credentials": creds, "total": len(creds)}


def remove_credential(target):
    """Delete a saved credential by its exact target string (confirmed in the UI)."""
    safe = target.replace('"', '')
    out = run_ps(f'cmdkey /delete:"{safe}"', timeout=15) or ""
    if "deleted" in out.lower() or "success" in out.lower():
        return {"ok": True, "where": f"Removed saved credential '{target}'."}
    return {"ok": False, "error": "Couldn't remove that credential (it may already be gone)."}
