"""Network inventory and the technician's interactive tool console."""

import json
import re
import socket
import subprocess
import time
import urllib.request

import psutil

from .ps import ps_json, run_ps, as_list, CREATE_NO_WINDOW

_IPCONFIG_PS = r"""
Get-NetIPConfiguration -Detailed | ForEach-Object {
    [pscustomobject]@{
        Alias    = $_.InterfaceAlias
        Desc     = $_.InterfaceDescription
        IPv4     = ($_.IPv4Address | ForEach-Object { $_.IPAddress }) -join ', '
        IPv6     = ($_.IPv6Address | ForEach-Object { $_.IPAddress }) -join ', '
        Gateway  = ($_.IPv4DefaultGateway | ForEach-Object { $_.NextHop }) -join ', '
        DNS      = ($_.DNSServer | Where-Object { $_.AddressFamily -eq 2 } | ForEach-Object { $_.ServerAddresses }) -join ', '
        Status   = $_.NetAdapter.Status
        Mac      = $_.NetAdapter.MacAddress
        Speed    = $_.NetAdapter.LinkSpeed
        DhcpV4   = $_.NetIPv4Interface.Dhcp
    }
}
"""


def get_network_info():
    adapters = []
    raw = as_list(ps_json(_IPCONFIG_PS, timeout=30))
    stats = psutil.net_if_stats()
    for a in raw:
        alias = a.get("Alias") or ""
        st = stats.get(alias)
        adapters.append({
            "alias": alias,
            "desc": a.get("Desc"),
            "ipv4": a.get("IPv4") or "",
            "ipv6": a.get("IPv6") or "",
            "gateway": a.get("Gateway") or "",
            "dns": a.get("DNS") or "",
            "status": a.get("Status"),
            "mac": a.get("Mac"),
            "speed": a.get("Speed"),
            "dhcp": a.get("DhcpV4"),
            "up": bool(st.isup) if st else None,
        })
    # Connected adapters first, then alphabetically
    adapters.sort(key=lambda x: (x.get("status") != "Up", x["alias"].lower()))
    return {"adapters": adapters, "wifi": _wifi_info()}


def _wifi_info():
    out = run_ps("netsh wlan show interfaces", timeout=15)
    if not out or "There is no wireless interface" in out:
        return None
    info = {}
    patterns = {
        "ssid": r"^\s*SSID\s*:\s*(.+)$",
        "signal": r"^\s*Signal\s*:\s*(.+)$",
        "radio": r"^\s*Radio type\s*:\s*(.+)$",
        "band": r"^\s*Band\s*:\s*(.+)$",
        "channel": r"^\s*Channel\s*:\s*(.+)$",
        "rx_rate": r"^\s*Receive rate \(Mbps\)\s*:\s*(.+)$",
        "tx_rate": r"^\s*Transmit rate \(Mbps\)\s*:\s*(.+)$",
        "auth": r"^\s*Authentication\s*:\s*(.+)$",
    }
    for line in out.splitlines():
        for key, pat in patterns.items():
            m = re.match(pat, line, re.IGNORECASE)
            if m and key not in info:
                info[key] = m.group(1).strip()
    return info or None


def get_public_ip():
    for url in ("https://api.ipify.org?format=json", "https://ifconfig.me/all.json"):
        try:
            with urllib.request.urlopen(url, timeout=6) as resp:
                data = json.loads(resp.read().decode())
                ip = data.get("ip") or data.get("ip_addr")
                if ip:
                    return {"ok": True, "ip": ip}
        except Exception:
            continue
    return {"ok": False, "error": "No internet route (or lookup services unreachable)."}


def _run_tool(args, timeout):
    try:
        result = subprocess.run(args, capture_output=True, timeout=timeout,
                                creationflags=CREATE_NO_WINDOW)
        out = result.stdout.decode("mbcs", errors="replace")
        err = result.stderr.decode("mbcs", errors="replace")
        return {"ok": True, "output": (out + ("\n" + err if err.strip() else "")).strip()}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Timed out after {timeout}s."}
    except Exception as e:
        return {"ok": False, "error": str(e)}


_HOST_RE = re.compile(r"^[A-Za-z0-9._:\-]+$")


def _clean_host(host: str):
    host = (host or "").strip()
    return host if host and _HOST_RE.match(host) else None


def run_ping(host: str, count: int = 4):
    host = _clean_host(host)
    if not host:
        return {"ok": False, "error": "Enter a valid hostname or IP."}
    count = max(1, min(int(count or 4), 20))
    res = _run_tool(["ping", "-n", str(count), host], timeout=15 + count * 2)
    if res.get("ok"):
        res["summary"] = _ping_summary(res["output"])
    return res


def _ping_summary(output: str):
    m_loss = re.search(r"\((\d+)% loss\)", output)
    m_avg = re.search(r"Average = (\d+)ms", output)
    return {
        "loss_pct": int(m_loss.group(1)) if m_loss else None,
        "avg_ms": int(m_avg.group(1)) if m_avg else None,
    }


def run_traceroute(host: str):
    host = _clean_host(host)
    if not host:
        return {"ok": False, "error": "Enter a valid hostname or IP."}
    return _run_tool(["tracert", "-d", "-w", "800", "-h", "20", host], timeout=120)


def dns_lookup(host: str):
    host = _clean_host(host)
    if not host:
        return {"ok": False, "error": "Enter a valid hostname."}
    results = ps_json(
        f"Resolve-DnsName -Name '{host}' -ErrorAction Stop | "
        "Select-Object Name,Type,TTL,IPAddress,NameHost", timeout=15)
    rows = []
    type_names = {1: "A", 2: "NS", 5: "CNAME", 6: "SOA", 12: "PTR", 15: "MX", 16: "TXT", 28: "AAAA"}
    for r in as_list(results):
        rtype = r.get("Type")
        rows.append({
            "name": r.get("Name"),
            "type": type_names.get(rtype, str(rtype)),
            "ttl": r.get("TTL"),
            "value": r.get("IPAddress") or r.get("NameHost") or "",
        })
    if not rows:
        return {"ok": False, "error": f"No DNS records found for {host}."}
    return {"ok": True, "records": rows}


def port_test(host: str, port):
    host = _clean_host(host)
    try:
        port = int(port)
        assert 1 <= port <= 65535
    except Exception:
        return {"ok": False, "error": "Port must be 1–65535."}
    if not host:
        return {"ok": False, "error": "Enter a valid hostname or IP."}
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=5):
            ms = (time.perf_counter() - start) * 1000
        return {"ok": True, "open": True, "ms": round(ms, 1)}
    except socket.timeout:
        return {"ok": True, "open": False, "reason": "timed out (filtered or host down)"}
    except ConnectionRefusedError:
        return {"ok": True, "open": False, "reason": "connection refused (port closed)"}
    except socket.gaierror:
        return {"ok": False, "error": f"Could not resolve {host}."}
    except OSError as e:
        return {"ok": True, "open": False, "reason": str(e)}


def get_connections(limit: int = 200):
    """Active TCP/UDP connections with owning process names."""
    conns = []
    name_cache = {}
    try:
        raw = psutil.net_connections(kind="inet")
    except psutil.AccessDenied:
        return {"ok": False, "error": "Access denied — run as Administrator to list all connections."}
    for c in raw:
        if not c.laddr:
            continue
        pid = c.pid or 0
        if pid and pid not in name_cache:
            try:
                name_cache[pid] = psutil.Process(pid).name()
            except Exception:
                name_cache[pid] = "?"
        conns.append({
            "proto": "TCP" if c.type == socket.SOCK_STREAM else "UDP",
            "laddr": f"{c.laddr.ip}:{c.laddr.port}",
            "raddr": f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "",
            "status": c.status if c.status != psutil.CONN_NONE else "",
            "pid": pid or "",
            "process": name_cache.get(pid, ""),
        })
    # Established first, then listening, then the rest
    order = {"ESTABLISHED": 0, "LISTEN": 1}
    conns.sort(key=lambda x: (order.get(x["status"], 2), x["process"].lower()))
    return {"ok": True, "connections": conns[:limit], "total": len(conns)}


def flush_dns():
    # Exit-code based so it works on any Windows display language
    try:
        result = subprocess.run(["ipconfig", "/flushdns"], capture_output=True,
                                timeout=15, creationflags=CREATE_NO_WINDOW)
        out = result.stdout.decode("mbcs", errors="replace").strip()
        if result.returncode == 0:
            return {"ok": True, "output": out or "Done."}
        return {"ok": False, "error": out or f"ipconfig exited with code {result.returncode}."}
    except Exception as e:
        return {"ok": False, "error": str(e)}
