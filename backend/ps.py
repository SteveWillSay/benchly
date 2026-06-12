"""Helpers for running PowerShell queries and returning parsed JSON."""

import json
import os
import subprocess

CREATE_NO_WINDOW = 0x08000000

_PS_PREFIX = (
    "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
    "$ProgressPreference='SilentlyContinue'; "
    "$ErrorActionPreference='SilentlyContinue'; "
)


def run_ps(command: str, timeout: int = 45, env: dict | None = None) -> str:
    """Run a PowerShell command and return raw stdout text ('' on failure).

    `env` adds variables to the child environment — the safe channel for
    secrets, which must never appear on a command line.
    """
    try:
        result = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-Command", _PS_PREFIX + command,
            ],
            capture_output=True,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
            env={**os.environ, **env} if env else None,
        )
        return result.stdout.decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def ps_json(command: str, timeout: int = 45, depth: int = 4, env: dict | None = None):
    """Run a PowerShell pipeline and parse its output as JSON.

    Returns the parsed object, or None if the command produced no output
    or unparseable output.
    """
    out = run_ps(f"& {{ {command} }} | ConvertTo-Json -Depth {depth} -Compress",
                 timeout=timeout, env=env)
    if not out:
        return None
    try:
        return json.loads(out)
    except (json.JSONDecodeError, ValueError):
        return None


def as_list(value):
    """ConvertTo-Json collapses single-element arrays; normalise back to a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def cim_date(value):
    """Parse a CIM datetime out of ConvertTo-Json output → 'YYYY-MM-DD' or None.

    PS 5.1 serialises DateTime either as "/Date(ms)/" or, at depth, as
    @{value=/Date(ms)/; DateTime=...} — accept both.
    """
    import datetime
    if isinstance(value, dict):
        value = value.get("value") or value.get("DateTime")
    if isinstance(value, str) and value.startswith("/Date("):
        try:
            ms = int(value[6:-2])
            return datetime.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            return None
    return value if isinstance(value, str) else None


def cim_age_days(value):
    """Days elapsed since a CIM datetime, or None if unparseable."""
    import datetime
    import time
    text = cim_date(value)
    if not text:
        return None
    try:
        dt = datetime.datetime.strptime(text[:10], "%Y-%m-%d")
        return max(0, int((time.time() - dt.timestamp()) / 86400))
    except ValueError:
        return None


def fmt_gb(n):
    return f"{n / (1024 ** 3):.1f} GB" if n else "—"
