"""Group Policy results — 'which policies are actually hitting this machine?'

Runs `gpresult` and reports the Group Policy Objects that applied (computer and
user scope), when policy last refreshed, and any GPOs that were filtered out —
the quick answer to 'is this setting coming from a policy, and did any fail?'.
Read-only. Computer-scope detail needs admin; user scope works without.
"""

from . import security
from .ps import run_ps


def _section(text, header):
    """Return the lines of one top-level gpresult section (COMPUTER/USER SETTINGS)."""
    lines = text.splitlines()
    out, grab = [], False
    for ln in lines:
        s = ln.strip()
        if s.upper().startswith(header):
            grab = True
            continue
        if grab and s.upper() in ("COMPUTER SETTINGS", "USER SETTINGS"):
            break
        if grab:
            out.append(ln)
    return out


def _list_after(lines, marker):
    """Collect the indented list that follows a 'marker' header line."""
    out, grab = [], False
    for ln in lines:
        s = ln.strip()
        if not grab and marker.lower() in s.lower():
            grab = True
            continue
        if grab:
            if not s:
                if out:
                    break
                continue
            # a new header (ends with colon, not an item) stops the list
            if s.endswith(":") and not s.lower().startswith("gpo"):
                break
            if s.upper().startswith("N/A") or "does not have" in s.lower():
                break
            # skip sub-attribute lines (Filtering:, Link Location:, …) — keep GPO names
            if any(s.lower().startswith(k) for k in ("filtering", "link location", "revision")):
                continue
            out.append(s.lstrip("- ").strip())
    return [x for x in out if x]


def _value_after(lines, marker):
    for ln in lines:
        s = ln.strip()
        if marker.lower() in s.lower() and ":" in s:
            return s.split(":", 1)[1].strip()
    return None


def _scope(lines):
    return {
        "last_applied": _value_after(lines, "Last time Group Policy was applied"),
        "applied": _list_after(lines, "Applied Group Policy Objects"),
        "filtered": _list_after(lines, "were not applied because they were filtered"),
    }


def gpo_results():
    admin = security.is_admin()
    text = run_ps("gpresult /r /z 2>&1 | Out-String", timeout=40) or ""
    if not text.strip():
        text = run_ps("gpresult /r 2>&1 | Out-String", timeout=40) or ""

    comp_lines = _section(text, "COMPUTER SETTINGS")
    user_lines = _section(text, "USER SETTINGS")
    computer = _scope(comp_lines)
    user = _scope(user_lines)

    no_data = "does not have rsop data" in text.lower()
    any_applied = bool(computer["applied"] or user["applied"])
    if no_data and not any_applied:
        summary = ("No Group Policy is being applied — this machine isn't centrally managed "
                   "(nothing from a domain or local policy is in effect).")
    elif any_applied:
        n = len(computer["applied"]) + len(user["applied"])
        summary = f"{n} Group Policy Object(s) are being applied to this machine."
    else:
        summary = "No applied Group Policy Objects were found."

    return {
        "ok": True, "is_admin": admin,
        "computer": computer, "user": user,
        "computer_needs_admin": not admin and not computer["applied"],
        "summary": summary,
    }
