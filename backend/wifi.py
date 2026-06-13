"""Wi-Fi analyzer — nearby networks, signal, band and 2.4 GHz congestion.

Parses `netsh wlan show networks mode=bssid`. Field labels are localised, so the
parser keys off the stable `SSID`/`BSSID` tokens and the *shape* of each value
(percent = signal, MAC = bssid, bare int = channel) rather than label text. On
Windows 11 scanning needs Location enabled, so an empty result with the location
message is surfaced as an actionable state, not an error.
"""

import re
import subprocess

from .ps import CREATE_NO_WINDOW

_RE_SSID = re.compile(r"^SSID\s+\d+\s*:\s*(.*)$", re.I)
_RE_BSSID = re.compile(r"^\s*BSSID\s+\d+\s*:\s*([0-9a-fA-F:]{17})", re.I)
_RE_MAC = re.compile(r"([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}")
_RE_PERCENT = re.compile(r":\s*(\d{1,3})\s*%")
_RE_INT = re.compile(r":\s*(\d{1,3})\s*$")
_RE_GHZ = re.compile(r":\s*([\d.]+)\s*GHz", re.I)


def _run_netsh(args, timeout=20):
    try:
        r = subprocess.run(["netsh"] + args, capture_output=True, timeout=timeout,
                           creationflags=CREATE_NO_WINDOW)
        return r.stdout.decode("mbcs", errors="replace")
    except Exception:
        return ""


def _band_from_channel(ch):
    if ch is None:
        return None
    if 1 <= ch <= 14:
        return "2.4 GHz"
    if 32 <= ch <= 177:
        return "5 GHz"
    return None


def _signal_to_dbm(pct):
    return round(pct / 2 - 100) if pct is not None else None


def scan_wifi():
    out = _run_netsh(["wlan", "show", "networks", "mode=bssid"])
    if not out:
        return {"ok": False, "error": "netsh returned nothing."}
    low = out.lower()
    if "no wireless interface" in low or "not running" in low:
        return {"ok": True, "available": False,
                "reason": "no_adapter" if "no wireless" in low else "wlansvc_stopped",
                "message": "No wireless interface on this PC." if "no wireless" in low
                           else "The WLAN AutoConfig service (WlanSvc) is not running."}
    if "location" in low and ("permission" in low or "enable location" in low):
        return {"ok": True, "available": False, "reason": "location_off",
                "message": "Windows needs Location enabled to scan Wi-Fi. Turn on Location (and app access), then rescan."}

    networks = []
    cur = None        # current SSID block
    bss = None        # current BSSID block
    for raw in out.splitlines():
        m = _RE_SSID.match(raw.strip())
        if m:
            cur = {"ssid": m.group(1).strip() or "(hidden)", "auth": None, "bssids": []}
            networks.append(cur)
            bss = None
            continue
        if cur is None:
            continue
        line = raw.strip()
        mb = _RE_BSSID.match(line)
        if mb:
            bss = {"bssid": mb.group(1).lower(), "signal": None, "dbm": None,
                   "channel": None, "band": None, "radio": None}
            cur["bssids"].append(bss)
            continue
        # network-level auth (first non-empty value line containing WPA/Open)
        if cur["auth"] is None and re.search(r"\b(WPA\d?|WEP|Open|RSNA)\b", line, re.I) and ":" in line:
            cur["auth"] = line.split(":", 1)[1].strip()
        if bss is None:
            continue
        if bss["signal"] is None and (mp := _RE_PERCENT.search(line)):
            bss["signal"] = int(mp.group(1))
            bss["dbm"] = _signal_to_dbm(bss["signal"])
            continue
        if (mg := _RE_GHZ.search(line)):
            bss["band"] = mg.group(1) + " GHz"
            continue
        if "802.11" in line:
            bss["radio"] = line.split(":", 1)[1].strip() if ":" in line else line.strip()
            continue
        if bss["channel"] is None and (mi := _RE_INT.search(line)) and "%" not in line:
            ch = int(mi.group(1))
            if 1 <= ch <= 233:
                bss["channel"] = ch
                if not bss["band"]:
                    bss["band"] = _band_from_channel(ch)

    # Flatten to per-BSSID rows for ranking + congestion
    aps = []
    for n in networks:
        for b in n["bssids"]:
            aps.append({**b, "ssid": n["ssid"], "auth": n["auth"]})
    aps.sort(key=lambda a: (a["signal"] is None, -(a["signal"] or 0)))

    # 2.4 GHz congestion across non-overlapping channels 1 / 6 / 11
    buckets = {1: 0, 6: 0, 11: 0, "other": 0}
    for a in aps:
        if a.get("band", "").startswith("2.4") or _band_from_channel(a.get("channel")) == "2.4 GHz":
            ch = a.get("channel")
            nearest = min((1, 6, 11), key=lambda c: abs((ch or 6) - c))
            if ch in (1, 6, 11):
                buckets[ch] += 1
            elif ch is not None:
                buckets["other"] += 1
                buckets[nearest] += 1

    return {"ok": True, "available": True, "networks": networks, "aps": aps,
            "count": len(aps), "ssid_count": len(networks),
            "congestion_24": buckets, "current": current_connection()}


def current_connection():
    out = _run_netsh(["wlan", "show", "interfaces"])
    if not out or "no wireless interface" in out.lower():
        return None
    info = {}
    fields = {
        "ssid": r"^\s*SSID\s*:\s*(.+)$",
        "signal": r"^\s*Signal\s*:\s*(.+)$",
        "radio": r"^\s*Radio type\s*:\s*(.+)$",
        "band": r"^\s*Band\s*:\s*(.+)$",
        "channel": r"^\s*Channel\s*:\s*(.+)$",
        "rx": r"^\s*Receive rate \(Mbps\)\s*:\s*(.+)$",
        "tx": r"^\s*Transmit rate \(Mbps\)\s*:\s*(.+)$",
    }
    for line in out.splitlines():
        for key, pat in fields.items():
            m = re.match(pat, line, re.IGNORECASE)
            if m and key not in info:
                info[key] = m.group(1).strip()
    if info.get("signal", "").endswith("%"):
        try:
            info["dbm"] = _signal_to_dbm(int(info["signal"].rstrip("%")))
        except ValueError:
            pass
    return info or None
