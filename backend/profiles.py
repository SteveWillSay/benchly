"""Corrupted / temporary user-profile detector — 'why am I on a temp profile?'

When Windows says "You've been signed in with a temporary profile" or a profile
just won't load, the fingerprint is in the registry under
`HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\ProfileList\\<SID>`.
The classic tell is a duplicated key with a `.bak` suffix; a non-zero `State`,
a missing profile folder, or a path pointing at `C:\\Users\\TEMP` are the others.

This reads that key per-SID and turns it into a plain-English verdict. It is
detection only — the actual fix (renaming the `.bak` key, migrating data) is
guided manually, so nothing here writes to the registry. Read-only.
"""

from .ps import ps_json, as_list

_PROFILE_LIST = (
    r"HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList"
)


def _to_int(value):
    """ProfileList State/RefCount come back as ints, but be defensive."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _account_for(sid, path):
    """Friendly name for a SID — Translate first, profile-folder leaf as fallback."""
    if isinstance(path, str) and path.strip():
        leaf = path.replace("/", "\\").rstrip("\\").split("\\")[-1]
        if leaf:
            return leaf
    return sid


# Well-known service accounts: SYSTEM / LOCAL SERVICE / NETWORK SERVICE. Their
# profile folders live under protected system paths that Test-Path can't always
# read without elevation, and they're never the temp-profile case this targets —
# so don't flag them on a missing-folder check.
_SERVICE_SIDS = {"S-1-5-18", "S-1-5-19", "S-1-5-20"}


def _is_temp_path(path):
    """C:\\Users\\TEMP or any ...\\TEMP* leaf is the temp-profile signature."""
    if not isinstance(path, str) or not path.strip():
        return False
    leaf = path.replace("/", "\\").rstrip("\\").split("\\")[-1]
    return leaf.upper().startswith("TEMP")


def detect_profiles():
    """Scan ProfileList for corrupted/temp profiles; plain-English verdict.

    Returns:
        {
          "profiles": [
            {"sid", "account", "path", "path_exists", "state",
             "has_bak", "is_temp", "problem", "issue"}, ...
          ],
          "problems": <int count of problem profiles>,
          "summary": "<one-line verdict>",
        }
    Never raises — returns a zeroed structure on failure.
    """
    empty = {"profiles": [], "problems": 0,
             "summary": "Couldn't read the profile list."}

    # Walk each ProfileList subkey. `.bak` keys are real, separate subkeys, so
    # Get-ChildItem surfaces them in PSChildName alongside the live SID. We also
    # resolve the account name and test whether the profile folder exists, all
    # in one pass.
    cmd = (
        f"Get-ChildItem -Path '{_PROFILE_LIST}' | ForEach-Object {{ "
        "$name = $_.PSChildName; "
        "$p = Get-ItemProperty -Path $_.PSPath; "
        "$imgPath = $p.ProfileImagePath; "
        "$acct = $null; "
        "$sid = $name -replace '\\.bak$',''; "
        "try { $acct = (New-Object System.Security.Principal.SecurityIdentifier($sid))"
        ".Translate([System.Security.Principal.NTAccount]).Value } catch { $acct = $null }; "
        "[pscustomobject]@{ "
        "Name=$name; "
        "Sid=$sid; "
        "Bak=($name -like '*.bak'); "
        "Account=$acct; "
        "Path=$imgPath; "
        "PathExists=([bool]($imgPath -and (Test-Path -LiteralPath $imgPath))); "
        "State=$p.State; "
        "RefCount=$p.RefCount } }"
    )

    rows = as_list(ps_json(cmd, timeout=40, depth=3))
    if not rows:
        return empty

    # First pass: which base SIDs have a .bak twin? That's the headline signal.
    bak_sids = set()
    for r in rows:
        if isinstance(r, dict) and r.get("Bak"):
            sid = r.get("Sid")
            if sid:
                bak_sids.add(sid)

    profiles = []
    seen = set()
    for r in rows:
        if not isinstance(r, dict):
            continue
        # Collapse the live SID and its .bak twin into one entry, keyed on SID.
        sid = r.get("Sid")
        if not sid or sid in seen:
            continue
        seen.add(sid)

        path = r.get("Path") or None
        has_bak = sid in bak_sids
        is_temp = _is_temp_path(path)
        state = _to_int(r.get("State"))
        ref_count = _to_int(r.get("RefCount"))
        path_given = bool(path)
        path_exists = bool(r.get("PathExists"))
        account = (r.get("Account") or "").strip() or _account_for(sid, path)

        is_service = sid in _SERVICE_SIDS
        missing_folder = path_given and not path_exists and not is_service
        bad_state = state not in (0, None)
        problem = has_bak or is_temp or bad_state or missing_folder

        # One-liner that names the most telling symptom first.
        if has_bak:
            issue = ("Has a '.bak' duplicate registry key — the classic corrupted-profile "
                     "fingerprint; Windows likely loads a temporary profile instead.")
        elif is_temp:
            issue = ("Profile folder is a TEMP path — you're signed in with a temporary "
                     "profile; changes won't be saved.")
        elif missing_folder:
            issue = f"Registry points at '{path}' but that folder no longer exists on disk."
        elif bad_state:
            issue = (f"Profile State is {state} (non-zero) — often flags an in-use or "
                     "problem/temp condition.")
        else:
            issue = ""

        profiles.append({
            "sid": sid,
            "account": account,
            "path": path,
            "path_exists": path_exists,
            "state": state,
            "ref_count": ref_count,
            "has_bak": has_bak,
            "is_temp": is_temp,
            "problem": problem,
            "issue": issue,
        })

    # Problems first, then alphabetically by account for a stable order.
    profiles.sort(key=lambda p: (not p["problem"], (p["account"] or "").lower()))

    problems = sum(1 for p in profiles if p["problem"])
    if not profiles:
        summary = "No user profiles found."
    elif problems == 0:
        summary = f"All {len(profiles)} profile(s) look healthy — no corrupted or temporary profiles."
    elif problems == 1:
        summary = "1 profile looks corrupted or temporary — see the flagged entry."
    else:
        summary = f"{problems} profiles look corrupted or temporary — see the flagged entries."

    return {"profiles": profiles, "problems": problems, "summary": summary}
