"""Hosts file viewer — what's in C:\\Windows\\System32\\drivers\\etc\\hosts.

A tampered hosts file silently redirects domains: malware/adware points a bank or AV
site at the wrong address, or an "optimizer" blackholes telemetry. It's also the answer
to "this one site won't load on this PC only." This shows every ACTIVE mapping and flags
anything that isn't the stock localhost line. Read-only — Benchly never edits the file.
"""

import os


def _hosts_path():
    return os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                        "System32", "drivers", "etc", "hosts")


def view_hosts():
    path = _hosts_path()
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
    except OSError as e:
        return {"ok": False, "error": str(e), "path": path}

    entries = []
    for ln in raw.splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):       # blank or comment — skip
            continue
        parts = s.split()
        if len(parts) < 2:
            continue
        ip = parts[0]
        for host in parts[1:]:
            if host.startswith("#"):         # trailing inline comment
                break
            # The only stock active mapping is loopback → localhost. Everything else is
            # an override worth a human's eyes (could be legit ad-blocking, could be a hijack).
            stock = ip in ("127.0.0.1", "::1") and host.lower() == "localhost"
            entries.append({"ip": ip, "host": host, "flagged": not stock})

    flagged = sum(1 for e in entries if e["flagged"])
    if not entries:
        summary = "No active host overrides — the file is at its Windows default."
    else:
        summary = f"{len(entries)} active mapping(s)" + (f", {flagged} non-default — review these." if flagged else ".")
    return {"ok": True, "path": path, "entries": entries,
            "count": len(entries), "flagged": flagged, "summary": summary}
