"""WAN speed test against Cloudflare's speed.cloudflare.com endpoints.

Third-party dependency disclosed in the UI (same as the public-IP lookup).
"""

import os
import time
import urllib.request

_BASE = "https://speed.cloudflare.com"
_UA = {"User-Agent": "Benchly"}


def run_speedtest():
    try:
        latency = _latency()
        down = _download()
        up = _upload()
        return {"ok": True, "latency_ms": latency, "down_mbps": down, "up_mbps": up,
                "server": "speed.cloudflare.com"}
    except Exception as e:
        return {"ok": False, "error": f"Speed test failed: {e}"}


def _latency(samples: int = 5):
    times = []
    for _ in range(samples):
        start = time.perf_counter()
        req = urllib.request.Request(f"{_BASE}/__down?bytes=0", headers=_UA)
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        times.append((time.perf_counter() - start) * 1000)
    times.sort()
    return round(sum(times[:3]) / min(3, len(times)), 1)   # mean of best 3


def _download():
    _fetch(2_000_000)                      # warm-up
    size = 30_000_000
    elapsed = _fetch(size)
    return round(size * 8 / elapsed / 1_000_000, 1)


def _fetch(nbytes: int) -> float:
    start = time.perf_counter()
    req = urllib.request.Request(f"{_BASE}/__down?bytes={nbytes}", headers=_UA)
    with urllib.request.urlopen(req, timeout=90) as resp:
        while resp.read(1 << 16):
            pass
    return time.perf_counter() - start


def _upload():
    payload = os.urandom(10_000_000)
    req = urllib.request.Request(f"{_BASE}/__up", data=payload, method="POST",
                                 headers={**_UA, "Content-Type": "application/octet-stream"})
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=90) as resp:
        resp.read()
    elapsed = time.perf_counter() - start
    return round(len(payload) * 8 / elapsed / 1_000_000, 1)
