"""Crash logging and a liveness watchdog.

Writes to %APPDATA%\\Benchly\\benchly.log so that if the app ever wedges or
dies, there is a trail: uncaught exceptions (main + threads), and a 30 s
heartbeat line carrying process memory, thread count, and the age of the last
UI bridge call. A climbing thread count or RSS points at a leak; a stale
last-call age while threads are alive points at a hung WebView2 renderer.
"""

import logging
import logging.handlers
import os
import sys
import threading
import time

from .settings import APP_DIR

_LOG_PATH = os.path.join(APP_DIR, "benchly.log")

# Updated by the API bridge on every inbound call (see app.py).
last_call = {"ts": time.time(), "method": "boot", "count": 0}

log = logging.getLogger("benchly")


def install(version: str):
    try:
        os.makedirs(APP_DIR, exist_ok=True)
    except OSError:
        return  # logging is best-effort; never block startup

    handler = logging.handlers.RotatingFileHandler(
        _LOG_PATH, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.setLevel(logging.INFO)
    log.addHandler(handler)
    log.info("=== Benchly %s starting (pid %d) ===", version, os.getpid())

    def _excepthook(exc_type, exc, tb):
        log.error("UNCAUGHT", exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _excepthook

    def _threadhook(args):
        log.error("UNCAUGHT in thread %s", args.thread_name,
                  exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    threading.excepthook = _threadhook

    threading.Thread(target=_watchdog, daemon=True, name="watchdog").start()


def note_call(method: str):
    last_call["ts"] = time.time()
    last_call["method"] = method
    last_call["count"] += 1


def _watchdog():
    try:
        import psutil
        proc = psutil.Process()
    except Exception:
        proc = None
    while True:
        time.sleep(30)
        try:
            rss = proc.memory_info().rss / (1024 * 1024) if proc else -1
            age = time.time() - last_call["ts"]
            log.info("heartbeat rss=%.0fMB threads=%d calls=%d last=%s age=%.0fs",
                     rss, threading.active_count(), last_call["count"],
                     last_call["method"], age)
        except Exception:
            pass
