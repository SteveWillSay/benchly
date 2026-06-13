"""Listening ports → owning process → Authenticode signature.

Maps every TCP/UDP listener to the process behind it and checks whether that
executable is validly signed. Unsigned listeners — especially in temp/AppData or
on a public interface — are the kind of thing to look at twice after a compromise.
"""

import re
import socket

import psutil

from .ps import ps_json, as_list

# Well-known service ports for a friendly label
_WELL_KNOWN = {
    135: "RPC", 139: "NetBIOS", 445: "SMB", 3389: "RDP", 5985: "WinRM",
    5986: "WinRM/HTTPS", 80: "HTTP", 443: "HTTPS", 21: "FTP", 22: "SSH",
    23: "Telnet", 25: "SMTP", 53: "DNS", 1433: "MSSQL", 3306: "MySQL",
    5432: "PostgreSQL", 6379: "Redis", 27017: "MongoDB", 8080: "HTTP-alt",
}

_SUSPECT_DIR = re.compile(r"\\(temp|tmp|appdata\\local\\temp|downloads|programdata)\\", re.I)


def _signatures(paths):
    if not paths:
        return {}
    uniq = sorted(set(p for p in paths if p))
    if not uniq:
        return {}
    arr = ",".join("'" + p.replace("'", "''") + "'" for p in uniq)
    rows = as_list(ps_json(
        f"@({arr}) | ForEach-Object {{ $s = Get-AuthenticodeSignature -LiteralPath $_ -ErrorAction SilentlyContinue; "
        "[pscustomobject]@{ Path=$_; Status=[string]$s.Status; Signer=$s.SignerCertificate.Subject } }",
        timeout=60, depth=3))
    out = {}
    for r in rows:
        p = (r.get("Path") or "").lower()
        if r.get("Status") == "Valid":
            subj = r.get("Signer") or ""
            m = re.search(r"CN=([^,]+)", subj)
            out[p] = m.group(1).strip() if m else "Signed"
        else:
            out[p] = False
    return out


def get_listeners():
    try:
        conns = psutil.net_connections(kind="inet")
    except psutil.AccessDenied:
        return {"ok": False, "error": "Access denied — run as Administrator to map every listening port."}

    rows = {}
    proc_cache = {}
    for c in conns:
        listening = (c.type == socket.SOCK_STREAM and c.status == psutil.CONN_LISTEN) or \
                    (c.type == socket.SOCK_DGRAM and (not c.raddr))
        if not listening or not c.laddr:
            continue
        pid = c.pid or 0
        if pid and pid not in proc_cache:
            try:
                p = psutil.Process(pid)
                proc_cache[pid] = {"name": p.name(), "exe": (p.exe() or "")}
            except Exception:
                proc_cache[pid] = {"name": "?", "exe": ""}
        info = proc_cache.get(pid, {"name": "", "exe": ""})
        ip = c.laddr.ip
        port = c.laddr.port
        key = (c.type, port, pid)
        public = ip not in ("127.0.0.1", "::1") and not ip.startswith("169.254")
        rows[key] = {
            "proto": "TCP" if c.type == socket.SOCK_STREAM else "UDP",
            "addr": f"{ip}:{port}",
            "port": port,
            "service": _WELL_KNOWN.get(port, ""),
            "pid": pid or "",
            "process": info["name"],
            "exe": info["exe"],
            "public": public,
        }

    listeners = list(rows.values())
    sigs = _signatures([r["exe"] for r in listeners if r["exe"]])

    flagged = 0
    for r in listeners:
        exe = (r["exe"] or "").lower()
        signed = sigs.get(exe) if exe else None
        r["signer"] = signed if isinstance(signed, str) else None
        # True = validly signed, False = unsigned, None = unknown (no readable exe)
        r["signed"] = None if signed is None else (signed is not False)
        reasons = []
        if signed is False:
            reasons.append("unsigned executable")
        if exe and _SUSPECT_DIR.search(exe):
            reasons.append("runs from a temp/AppData path")
        if r["public"] and signed is False:
            reasons.append("listening on a non-loopback interface")
        r["reasons"] = reasons
        r["suspect"] = bool(reasons)
        if r["suspect"]:
            flagged += 1

    listeners.sort(key=lambda x: (not x["suspect"], not x["public"], x["port"]))
    return {"ok": True, "listeners": listeners, "total": len(listeners), "flagged": flagged}
