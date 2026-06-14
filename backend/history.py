"""Tiny append-only time-series store at %APPDATA%\\Benchly\\history\\<series>.jsonl.

Used for things that only mean something over time — SMART wear/error trends today,
and memory-leak / thermal trends later. One JSON object per line; capped so it can't
grow without bound.
"""

import datetime
import json
import os

from .settings import APP_DIR

_DIR = os.path.join(APP_DIR, "history")
_MAX_LINES = 2000


def _path(series):
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in str(series))
    return os.path.join(_DIR, safe + ".jsonl")


def append(series, sample):
    try:
        os.makedirs(_DIR, exist_ok=True)
        row = {"t": datetime.datetime.now().isoformat(timespec="seconds"), **sample}
        path = _path(series)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        _rotate(path)
        return row
    except OSError:
        return None


def read(series, limit=400):
    try:
        with open(_path(series), encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return []
    out = []
    for ln in lines[-limit:]:
        try:
            out.append(json.loads(ln))
        except ValueError:
            pass
    return out


def _rotate(path):
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > _MAX_LINES:
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines[-_MAX_LINES:])
    except OSError:
        pass
