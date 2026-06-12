"""Baseline snapshot & diff — answer "what changed since this machine last worked?"."""

import datetime
import json
import os
import socket

from .settings import APP_DIR as _DIR
from . import software, security, sysinfo

_PATH = os.path.join(_DIR, "baseline.json")


def _snapshot():
    inv = sysinfo.get_inventory()
    health = security.get_health()
    return {
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "host": socket.gethostname(),
        "os_build": inv["os"].get("build"),
        "score": health["score"],
        "apps": {a["name"]: a["version"] for a in software.get_installed()},
        "services": {s["name"]: {"start": s["start"], "status": s["status"]}
                     for s in software.get_services()},
        "startup": {s["name"]: s["command"] for s in software.get_startup()},
    }


def save_baseline():
    try:
        os.makedirs(_DIR, exist_ok=True)
        snap = _snapshot()
        with open(_PATH, "w", encoding="utf-8") as f:
            json.dump(snap, f)
        return {"ok": True, "time": snap["time"],
                "counts": {"apps": len(snap["apps"]), "services": len(snap["services"]),
                           "startup": len(snap["startup"])}}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_baseline_info():
    if not os.path.exists(_PATH):
        return {"exists": False}
    try:
        with open(_PATH, encoding="utf-8") as f:
            snap = json.load(f)
        return {"exists": True, "time": snap.get("time"), "host": snap.get("host"),
                "score": snap.get("score"),
                "counts": {"apps": len(snap.get("apps", {})), "services": len(snap.get("services", {})),
                           "startup": len(snap.get("startup", {}))}}
    except Exception:
        return {"exists": False}


def compare_baseline():
    if not os.path.exists(_PATH):
        return {"ok": False, "error": "No baseline saved yet."}
    try:
        with open(_PATH, encoding="utf-8") as f:
            base = json.load(f)
    except Exception as e:
        return {"ok": False, "error": f"Baseline unreadable: {e}"}

    now = _snapshot()

    def dict_diff(old, new):
        added = [{"name": k, "value": _short(new[k])} for k in new if k not in old]
        removed = [{"name": k, "value": _short(old[k])} for k in old if k not in new]
        changed = [{"name": k, "old": _short(old[k]), "new": _short(new[k])}
                   for k in new if k in old and old[k] != new[k]]
        for lst in (added, removed, changed):
            lst.sort(key=lambda x: x["name"].lower())
        return added, removed, changed

    apps_added, apps_removed, apps_changed = dict_diff(base.get("apps", {}), now["apps"])
    svc_added, svc_removed, svc_changed = dict_diff(base.get("services", {}), now["services"])
    su_added, su_removed, su_changed = dict_diff(base.get("startup", {}), now["startup"])

    return {
        "ok": True,
        "baseline_time": base.get("time"),
        "now_time": now["time"],
        "score": {"old": base.get("score"), "new": now["score"]},
        "os_build": {"old": base.get("os_build"), "new": now["os_build"]},
        "apps": {"added": apps_added, "removed": apps_removed, "changed": apps_changed},
        "services": {"added": svc_added, "removed": svc_removed, "changed": svc_changed},
        "startup": {"added": su_added, "removed": su_removed, "changed": su_changed},
        "clean": not any([apps_added, apps_removed, apps_changed, svc_added, svc_removed,
                          svc_changed, su_added, su_removed, su_changed,
                          base.get("os_build") != now["os_build"]]),
    }


def _short(v):
    s = v if isinstance(v, str) else json.dumps(v)
    return s if len(s) <= 120 else s[:117] + "…"
