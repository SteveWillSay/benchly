"""LAN toolkit — subnet scanner, port-profile scan, Wake-on-LAN, DHCP/DNS health."""

import ipaddress
import re
import socket
import struct
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

import psutil

from .jobs import JobStore
from .ps import ps_json, as_list, cim_date, CREATE_NO_WINDOW
from . import settings

# ---------------------------------------------------------------- subnet scan

# Curated OUI prefixes a bench tech actually meets — not exhaustive, just useful.
_OUI = {
    "00:05:CD": "D&M/Denon", "00:11:32": "Synology", "00:1B:63": "Apple", "00:50:56": "VMware",
    "00:15:5D": "Microsoft Hyper-V", "00:1A:79": "Cisco", "00:18:0A": "Cisco Meraki",
    "00:04:F2": "Polycom", "00:90:A9": "Western Digital", "00:24:E4": "Withings",
    "18:FE:34": "Espressif (IoT)", "24:0A:C4": "Espressif (IoT)", "CC:50:E3": "Espressif (IoT)",
    "B8:27:EB": "Raspberry Pi", "DC:A6:32": "Raspberry Pi", "E4:5F:01": "Raspberry Pi",
    "28:CD:C1": "Raspberry Pi", "D8:3A:DD": "Raspberry Pi",
    "F0:9F:C2": "Ubiquiti", "24:A4:3C": "Ubiquiti", "78:8A:20": "Ubiquiti", "FC:EC:DA": "Ubiquiti",
    "D8:B3:70": "Ubiquiti", "9C:05:D6": "Ubiquiti", "68:D7:9A": "Ubiquiti", "74:AC:B9": "Ubiquiti",
    "E0:63:DA": "Ubiquiti", "B4:FB:E4": "Ubiquiti", "70:A7:41": "Ubiquiti",
    "8C:7A:B3": "LG", "C8:08:E9": "LG", "A8:23:FE": "LG", "B8:AD:3E": "LG",
    "A0:36:BC": "ASUSTek", "FC:34:97": "ASUSTek", "08:BF:B8": "ASUSTek",
    "00:09:0F": "Fortinet", "00:1D:AA": "DrayTek", "4C:5E:0C": "MikroTik", "6C:3B:6B": "MikroTik",
    "00:1F:33": "Netgear", "A0:40:A0": "Netgear", "9C:3D:CF": "Netgear",
    "F4:F2:6D": "TP-Link", "50:C7:BF": "TP-Link", "98:DA:C4": "TP-Link", "60:32:B1": "TP-Link",
    "00:05:5D": "D-Link", "14:D6:4D": "D-Link", "00:13:49": "Zyxel",
    "00:1E:8C": "ASUS", "2C:FD:A1": "ASUS", "04:D9:F5": "ASUS", "70:4D:7B": "ASUS",
    "94:DE:80": "GIGA-BYTE", "1C:69:7A": "EliteGroup", "70:85:C2": "ASRock",
    "00:24:21": "Micro-Star (MSI)", "00:D8:61": "Micro-Star (MSI)", "04:42:1A": "ASUSTek",
    "F8:75:A4": "Lenovo", "54:E1:AD": "Lenovo", "8C:16:45": "Lenovo", "98:FA:9B": "Lenovo",
    "18:60:24": "HP", "94:57:A5": "HP", "3C:52:82": "HP", "10:E7:C6": "HP", "B0:5C:DA": "HP",
    "D4:81:D7": "Dell", "18:A9:9B": "Dell", "F8:BC:12": "Dell", "00:14:22": "Dell",
    "B4:45:06": "Dell", "E4:54:E8": "Dell", "8C:EC:4B": "Dell",
    "3C:22:FB": "Apple", "F0:18:98": "Apple", "A4:83:E7": "Apple", "BC:D0:74": "Apple",
    "F4:5C:89": "Apple", "14:7D:DA": "Apple", "28:6A:BA": "Apple",
    "28:39:5E": "Samsung", "8C:71:F8": "Samsung", "C0:97:27": "Samsung", "5C:49:7D": "Samsung",
    "64:16:66": "Google/Nest", "F4:F5:D8": "Google", "30:FD:38": "Google", "1C:F2:9A": "Google",
    "44:65:0D": "Amazon", "FC:65:DE": "Amazon", "0C:47:C9": "Amazon", "74:C2:46": "Amazon",
    "B4:7C:9C": "Amazon", "F0:27:2D": "Amazon",
    "5C:AA:FD": "Sonos", "00:0E:58": "Sonos", "B8:E9:37": "Sonos", "94:9F:3E": "Sonos",
    "00:17:88": "Philips Hue", "EC:B5:FA": "Philips Hue",
    "7C:DD:90": "Shenzhen (IoT)", "50:02:91": "Espressif (IoT)",
    "00:80:92": "Brother", "30:05:5C": "Brother", "00:1B:A9": "Brother",
    "00:00:85": "Canon", "00:1E:8F": "Canon", "00:26:AB": "Seiko Epson", "9C:AE:D3": "Seiko Epson",
    "AC:18:26": "Seiko Epson", "64:EB:8C": "Seiko Epson",
    "00:01:E6": "HP (print)", "94:E8:C5": "Xerox",
    "00:80:77": "Brother (print)", "00:22:58": "Lexmark",
    "00:50:B6": "Good Way (dock)", "00:E0:4C": "Realtek", "00:24:D7": "Intel", "8C:8C:AA": "Intel",
    "A0:36:9F": "Intel", "3C:E9:F7": "Intel", "48:51:B7": "Intel", "DC:21:48": "Intel",
    "00:1A:A0": "Marvell", "00:0A:CD": "Sunrich",
    "70:B3:D5": "IEEE-registered device", "84:EB:18": "Texas Instruments",
    "00:04:20": "Slim Devices", "00:11:D9": "TiVo", "60:CB:FB": "AsusTek",
    "00:50:F2": "Microsoft", "28:18:78": "Microsoft", "98:5F:D3": "Microsoft", "60:45:BD": "Microsoft",
    "7C:1E:52": "Microsoft", "C4:9D:ED": "Microsoft (Xbox)", "98:5D:AD": "Texas Instruments",
    "00:1F:C6": "ASUSTek", "00:26:37": "Samsung", "78:DD:08": "Hon Hai/Foxconn",
    "60:BE:B5": "Motorola", "CC:FA:00": "LG", "10:F1:F2": "LG", "64:BC:0C": "LG",
    "04:5D:4B": "Sony", "FC:0F:E6": "Sony", "00:19:C5": "Nintendo", "7C:BB:8A": "Nintendo",
    "98:B6:E9": "Nintendo", "00:1F:32": "Nintendo",
    "00:24:8C": "ASUSTek", "BC:EE:7B": "ASUSTek", "AC:9E:17": "ASUSTek",
    "00:08:9B": "QNAP", "24:5E:BE": "QNAP", "00:11:6B": "Digital Data (NAS)",
    "00:1C:C0": "Intel", "34:97:F6": "ASUSTek", "04:92:26": "ASUSTek",
}


def _vendor(mac: str):
    if not mac:
        return ""
    mac = mac.upper().replace("-", ":")
    # locally-administered bit ⇒ randomised/private MAC (phones, Windows privacy)
    try:
        if int(mac[0:2], 16) & 0x02:
            return "Private / randomised"
    except ValueError:
        pass
    return _OUI.get(mac[0:8], "")


_scan_store = JobStore()


def list_subnets():
    """IPv4 subnets on up interfaces, ready for the scanner dropdown."""
    subnets, seen = [], set()
    stats = psutil.net_if_stats()
    for alias, addrs in psutil.net_if_addrs().items():
        if not stats.get(alias) or not stats[alias].isup:
            continue
        for a in addrs:
            if a.family != socket.AF_INET or not a.netmask:
                continue
            if a.address.startswith(("127.", "169.254.")):
                continue
            try:
                net = ipaddress.ip_network(f"{a.address}/{a.netmask}", strict=False)
            except ValueError:
                continue
            # cap giant subnets to the /24 around our own address
            capped = False
            if net.num_addresses > 1024:
                net = ipaddress.ip_network(f"{a.address}/24", strict=False)
                capped = True
            key = str(net)
            if key in seen:
                continue
            seen.add(key)
            subnets.append({"network": key, "adapter": alias, "self": a.address,
                            "hosts": net.num_addresses - 2, "capped": capped})
    return subnets


def start_subnet_scan(network: str):
    try:
        net = ipaddress.ip_network(network, strict=False)
        assert net.num_addresses <= 1024
    except (ValueError, AssertionError):
        return {"ok": False, "error": "Invalid or oversized subnet (max /22)."}
    job_id = _scan_store.start(_scan_run, network=str(net), found=[],
                               done_count=0, total=net.num_addresses - 2)
    if job_id is None:
        return {"ok": False, "error": "A scan is already running."}
    return {"ok": True, "job": job_id, "total": net.num_addresses - 2}


def _ping_one(ip: str) -> bool:
    r = subprocess.run(["ping", "-n", "1", "-w", "300", ip],
                       capture_output=True, creationflags=CREATE_NO_WINDOW)
    return r.returncode == 0


def _scan_run(job):
    net = ipaddress.ip_network(job["network"])
    alive = []
    with ThreadPoolExecutor(max_workers=64) as pool:
        futures = {pool.submit(_ping_one, str(ip)): str(ip) for ip in net.hosts()}
        for fut in as_completed(futures):
            job["done_count"] += 1
            try:
                if fut.result():
                    alive.append(futures[fut])
            except Exception:
                pass

    # MACs from the ARP cache the sweep just populated
    arp = {}
    try:
        out = subprocess.run(["arp", "-a"], capture_output=True, timeout=15,
                             creationflags=CREATE_NO_WINDOW).stdout.decode("mbcs", "replace")
        for m in re.finditer(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]{17})", out):
            arp[m.group(1)] = m.group(2).replace("-", ":").upper()
    except Exception:
        pass

    own_ips = {a.address for addrs in psutil.net_if_addrs().values()
               for a in addrs if a.family == socket.AF_INET}

    def resolve(ip):
        try:
            return socket.gethostbyaddr(ip)[0]
        except OSError:
            return ""

    names = {}
    with ThreadPoolExecutor(max_workers=32) as pool:
        futures = {pool.submit(resolve, ip): ip for ip in alive}
        for fut in as_completed(futures):
            try:
                names[futures[fut]] = fut.result()
            except Exception:
                names[futures[fut]] = ""

    for ip in sorted(alive, key=lambda x: tuple(int(o) for o in x.split("."))):
        mac = arp.get(ip, "")
        job["found"].append({
            "ip": ip,
            "mac": mac,
            "vendor": _vendor(mac),
            "name": names.get(ip, ""),
            "self": ip in own_ips,
        })


def get_scan_job(job_id: str):
    job = _scan_store.get(job_id)
    if not job:
        return {"ok": False, "error": "No such scan."}
    return {"ok": True, "done": job["done"], "done_count": job["done_count"],
            "total": job["total"], "found": list(job["found"])}


# ---------------------------------------------------------------- port profile

_PROFILE_PORTS = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 80: "HTTP",
    110: "POP3", 135: "MS RPC", 139: "NetBIOS", 143: "IMAP", 389: "LDAP",
    443: "HTTPS", 445: "SMB", 515: "LPD print", 548: "AFP", 631: "IPP print",
    1433: "MS SQL", 3306: "MySQL", 3389: "RDP", 5060: "SIP", 5900: "VNC",
    8006: "Proxmox", 8080: "HTTP alt", 8443: "HTTPS alt", 9100: "JetDirect print",
}
_BANNER_PORTS = {21, 22, 25, 110, 143}   # protocols that speak first


def port_profile(host: str):
    host = (host or "").strip()
    if not host or not re.match(r"^[A-Za-z0-9._\-]+$", host):
        return {"ok": False, "error": "Enter a valid hostname or IP."}
    try:
        target = socket.gethostbyname(host)
    except OSError:
        return {"ok": False, "error": f"Could not resolve {host}."}

    def probe(port):
        try:
            with socket.create_connection((target, port), timeout=1.2) as s:
                banner = ""
                if port in _BANNER_PORTS:
                    try:
                        s.settimeout(1.2)
                        banner = s.recv(120).decode("ascii", "replace").strip().splitlines()[0][:90]
                    except OSError:
                        pass
                return {"port": port, "service": _PROFILE_PORTS[port], "banner": banner}
        except OSError:
            return None

    open_ports = []
    with ThreadPoolExecutor(max_workers=24) as pool:
        for result in pool.map(probe, sorted(_PROFILE_PORTS)):
            if result:
                open_ports.append(result)
    return {"ok": True, "host": host, "ip": target,
            "open": open_ports, "scanned": len(_PROFILE_PORTS)}


# ---------------------------------------------------------------- Wake-on-LAN

_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")


def wol_machines():
    return settings.get("wol_machines") or []


def wol_save(machines):
    return settings.set_value("wol_machines", machines)


def wol_send(mac: str):
    mac = (mac or "").strip()
    if not _MAC_RE.match(mac):
        return {"ok": False, "error": "MAC must look like AA:BB:CC:DD:EE:FF."}
    payload = b"\xff" * 6 + bytes.fromhex(mac.replace(":", "").replace("-", "")) * 16
    sent = 0
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            for port in (9, 7):
                s.sendto(payload, ("255.255.255.255", port))
                sent += 1
        return {"ok": True, "sent": sent}
    except OSError as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------- DHCP / DNS health

_DHCP_PS = r"""
$o = [ordered]@{}
$o.leases = Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "IPEnabled=true" |
    Select-Object Description,DHCPEnabled,DHCPServer,DHCPLeaseObtained,DHCPLeaseExpires,
                  @{n='IP';e={($_.IPAddress | Where-Object { $_ -notmatch ':' }) -join ', '}},
                  @{n='DNS';e={$_.DNSServerSearchOrder -join ', '}}
$servers = @($o.leases | ForEach-Object { $_.DNS -split ', ' } | Where-Object { $_ } | Select-Object -Unique)
$o.dns_tests = foreach ($srv in $servers) {
    $ms = $null; $ok = $false
    try {
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $null = Resolve-DnsName -Name microsoft.com -Server $srv -DnsOnly -QuickTimeout -ErrorAction Stop
        $sw.Stop(); $ms = [math]::Round($sw.Elapsed.TotalMilliseconds); $ok = $true
    } catch { }
    [pscustomobject]@{ Server = $srv; Ok = $ok; Ms = $ms }
}
$o
"""


def dhcp_dns_health():
    raw = ps_json(_DHCP_PS, timeout=60) or {}
    leases = []
    dhcp_servers = set()
    for l in as_list(raw.get("leases")):
        server = l.get("DHCPServer") or ""
        if server:
            dhcp_servers.add(server)
        leases.append({
            "adapter": l.get("Description"),
            "ip": l.get("IP") or "",
            "dhcp": bool(l.get("DHCPEnabled")),
            "server": server,
            "obtained": cim_date(l.get("DHCPLeaseObtained")),
            "expires": cim_date(l.get("DHCPLeaseExpires")),
            "dns": l.get("DNS") or "",
        })
    dns_tests = [{
        "server": t.get("Server"),
        "ok": bool(t.get("Ok")),
        "ms": t.get("Ms"),
    } for t in as_list(raw.get("dns_tests"))]
    return {
        "leases": leases,
        "dns_tests": dns_tests,
        "multiple_dhcp": len(dhcp_servers) > 1,
        "dhcp_servers": sorted(dhcp_servers),
    }
