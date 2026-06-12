"""Live performance metrics sampled with psutil (fast path, called every second)."""

import socket
import time

import psutil

_prev = {"t": None, "disk": None, "net": None}

# Prime CPU counters so the first real reading isn't 0.0
psutil.cpu_percent(interval=None)
psutil.cpu_percent(interval=None, percpu=True)


def _rates():
    """Compute disk and network throughput in bytes/sec since the last call."""
    now = time.monotonic()
    disk = psutil.disk_io_counters()
    net = psutil.net_io_counters()
    rates = {"disk_read": 0, "disk_write": 0, "net_up": 0, "net_down": 0}

    if _prev["t"] is not None:
        dt = max(now - _prev["t"], 0.001)
        if disk and _prev["disk"]:
            rates["disk_read"] = max(0, (disk.read_bytes - _prev["disk"].read_bytes) / dt)
            rates["disk_write"] = max(0, (disk.write_bytes - _prev["disk"].write_bytes) / dt)
        if net and _prev["net"]:
            rates["net_up"] = max(0, (net.bytes_sent - _prev["net"].bytes_sent) / dt)
            rates["net_down"] = max(0, (net.bytes_recv - _prev["net"].bytes_recv) / dt)

    _prev.update(t=now, disk=disk, net=net)
    return rates


def get_metrics():
    """One-second snapshot for the live dashboard."""
    vm = psutil.virtual_memory()
    rates = _rates()

    try:
        freq = psutil.cpu_freq()
        cpu_mhz = round(freq.current) if freq else None
    except Exception:
        cpu_mhz = None

    battery = None
    try:
        b = psutil.sensors_battery()
        if b:
            battery = {"percent": round(b.percent, 1), "plugged": bool(b.power_plugged)}
    except Exception:
        pass

    sys_disk = None
    try:
        u = psutil.disk_usage("C:\\")
        sys_disk = {"total": u.total, "used": u.used, "percent": u.percent}
    except Exception:
        pass

    return {
        "cpu": psutil.cpu_percent(interval=None),
        "cpu_per_core": psutil.cpu_percent(interval=None, percpu=True),
        "cpu_mhz": cpu_mhz,
        "ram": {
            "total": vm.total,
            "used": vm.total - vm.available,
            "available": vm.available,
            "percent": vm.percent,
        },
        "rates": rates,
        "sys_disk": sys_disk,
        "battery": battery,
        "boot_time": psutil.boot_time(),
        "proc_count": len(psutil.pids()),
    }


def get_processes(limit: int = 250):
    """Process table. cpu_percent uses psutil's per-instance cache, so values
    reflect usage since the previous call (first call after launch reads 0)."""
    procs = []
    ncpu = psutil.cpu_count(logical=True) or 1
    for p in psutil.process_iter(["pid", "name", "username", "memory_info", "status", "create_time"]):
        try:
            info = p.info
            cpu = p.cpu_percent(interval=None) / ncpu
            mem = info["memory_info"].rss if info["memory_info"] else 0
            user = info["username"] or ""
            if "\\" in user:
                user = user.split("\\", 1)[1]
            procs.append({
                "pid": info["pid"],
                "name": info["name"] or "?",
                "user": user,
                "cpu": round(cpu, 1),
                "mem": mem,
                "status": info["status"] or "",
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    procs.sort(key=lambda x: (x["cpu"], x["mem"]), reverse=True)
    return procs[:limit]


def process_detail(pid: int):
    """Deep inspect a single process — the Process Explorer / TCPView join.
    Many fields need admin; each degrades to None rather than failing."""
    try:
        p = psutil.Process(int(pid))
    except (psutil.NoSuchProcess, ValueError):
        return {"ok": False, "error": "Process no longer exists."}

    def safe(fn, default=None):
        try:
            return fn()
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            return default

    import datetime
    info = {"ok": True, "pid": p.pid, "name": safe(p.name, "?")}
    info["exe"] = safe(p.exe)
    info["cmdline"] = " ".join(safe(p.cmdline, []) or [])
    info["cwd"] = safe(p.cwd)
    user = safe(p.username, "") or ""
    info["user"] = user.split("\\", 1)[1] if "\\" in user else user
    ct = safe(p.create_time)
    info["started"] = datetime.datetime.fromtimestamp(ct).strftime("%Y-%m-%d %H:%M:%S") if ct else None
    info["status"] = safe(p.status, "")
    info["threads"] = safe(p.num_threads)
    mem = safe(p.memory_info)
    info["rss"] = mem.rss if mem else None
    info["vms"] = mem.vms if mem else None
    par = safe(p.parent)
    info["parent"] = f"{par.name()} ({par.pid})" if par else None

    conns = safe(p.net_connections, []) or []
    info["connections"] = [{
        "proto": "TCP" if c.type == socket.SOCK_STREAM else "UDP",
        "laddr": f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "",
        "raddr": f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "",
        "status": c.status if c.status != psutil.CONN_NONE else "",
    } for c in conns][:60]

    files = safe(p.open_files, []) or []
    info["open_files"] = [f.path for f in files][:60]

    mods = safe(p.memory_maps, []) or []
    seen = set()
    dlls = []
    for m in mods:
        path = getattr(m, "path", "")
        if path.lower().endswith(".dll") and path not in seen:
            seen.add(path)
            dlls.append(path)
    info["modules"] = sorted(dlls)[:120]
    return info


def find_lockers(path: str):
    """Which processes hold an open handle to a file/folder path."""
    path = (path or "").lower()
    if not path:
        return {"ok": False, "error": "Enter a path."}
    hits = []
    for p in psutil.process_iter(["name", "pid"]):
        try:
            for f in p.open_files():
                if path in f.path.lower():
                    hits.append({"pid": p.info["pid"], "name": p.info["name"], "file": f.path})
                    break
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return {"ok": True, "lockers": hits[:50]}


def kill_process(pid: int):
    try:
        p = psutil.Process(int(pid))
        name = p.name()
        p.terminate()
        try:
            p.wait(timeout=3)
        except psutil.TimeoutExpired:
            p.kill()
        return {"ok": True, "name": name}
    except psutil.AccessDenied:
        return {"ok": False, "error": "Access denied — run Benchly as Administrator to end this process."}
    except psutil.NoSuchProcess:
        return {"ok": False, "error": "Process no longer exists."}
    except Exception as e:
        return {"ok": False, "error": str(e)}
