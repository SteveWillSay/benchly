"""Battery degradation history — one reading per day, charted over time."""

import datetime
import json
import os

import psutil

from .settings import APP_DIR
from . import security

_PATH = os.path.join(APP_DIR, "battery_history.json")


def _load():
    try:
        with open(_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return []


def record():
    """Append today's reading if the machine has a battery. Called at boot."""
    if not psutil.sensors_battery():
        return
    health = security._battery_health()
    if not health:
        return
    history = _load()
    today = datetime.date.today().isoformat()
    if history and history[-1]["date"] == today:
        return
    history.append({"date": today,
                    "design_mwh": health["design_mwh"],
                    "full_mwh": health["full_mwh"],
                    "health_pct": health["health_pct"]})
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        with open(_PATH, "w", encoding="utf-8") as f:
            json.dump(history[-730:], f)   # keep ~2 years
    except OSError:
        pass


def get_history():
    return {"present": psutil.sensors_battery() is not None, "history": _load()}
