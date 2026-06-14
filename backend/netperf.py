"""Network performance — bufferbloat grade.

"Why does my call stutter when someone's downloading?" Bufferbloat: latency that
balloons the moment the link is saturated. We measure round-trip latency while idle,
then again while hammering the connection, and grade the difference. A low idle ping
that triples under load is the classic sign your router needs SQM/QoS.
"""

import socket
import statistics
import threading
import time
import urllib.request

_ANCHORS = [("1.1.1.1", 443), ("8.8.8.8", 443)]
_SATURATE_URL = "https://speed.cloudflare.com/__down?bytes=200000000"


def _rtt(host, port, timeout=2.0):
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return (time.perf_counter() - start) * 1000
    except OSError:
        return None


def _median_latency(samples=8):
    vals = []
    for _ in range(samples):
        for host, port in _ANCHORS:
            r = _rtt(host, port)
            if r is not None:
                vals.append(r)
                break
        time.sleep(0.15)
    return statistics.median(vals) if vals else None


def _saturate(stop, direction):
    """Download (and/or upload) to flood the link until told to stop."""
    while not stop.is_set():
        try:
            req = urllib.request.Request(_SATURATE_URL, headers={"User-Agent": "Benchly"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                while not stop.is_set():
                    if not resp.read(65536):
                        break
        except Exception:
            time.sleep(0.3)


def bufferbloat_test():
    idle = _median_latency(8)
    if idle is None:
        return {"ok": False, "error": "No internet route — couldn't measure latency."}

    stop = threading.Event()
    threads = [threading.Thread(target=_saturate, args=(stop, "down"), daemon=True) for _ in range(4)]
    for t in threads:
        t.start()
    time.sleep(2.0)                       # let the link fill
    loaded = _median_latency(10)
    stop.set()
    for t in threads:
        t.join(timeout=2)

    if loaded is None:
        loaded = idle
    added = max(0, round(loaded - idle))
    grade = ("A" if added < 30 else "B" if added < 60 else "C" if added < 100
             else "D" if added < 200 else "F")
    flags = []
    if grade in ("A", "B"):
        flags.append({"level": "good", "text": f"Grade {grade} — latency stays low under load. Good for calls and gaming."})
    else:
        flags.append({"level": "warn", "text": f"Grade {grade} — latency jumps by {added} ms under load (bufferbloat). Enable SQM/QoS on your router to fix it."})
    return {"ok": True, "idle_ms": round(idle), "loaded_ms": round(loaded),
            "added_ms": added, "grade": grade, "flags": flags}
