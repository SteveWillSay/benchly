# Benchly

**The IT technician's one-stop workstation triage bench.**

One window for everything you normally need a USB stick full of fragmented utilities for:
live performance telemetry, deep hardware inventory, SMART disk health, a network tool
console, a weighted health & security audit, and a client-ready HTML report — in a single
portable exe with a modern UI.

![Benchly](assets/icon.png)

## Features

| Page | What you get |
|---|---|
| **Dashboard** | Triage vitals strip, live CPU / RAM / disk-I/O / network sparklines (1 s), per-core load grid, health score ring, top processes, clickable volume bars |
| **System** | Full inventory: machine, OS, CPU, every RAM module (slot/speed/part no.), GPUs, monitor EDID, board, BIOS/UEFI, Secure Boot, TPM |
| **Storage** | Physical disks with SMART health, temperature, wear & power-on hours¹, volumes, and a drill-down space analyzer (drive chips, breadcrumbs, reveal-in-Explorer) |
| **Network** | Adapter/Wi-Fi detail, public IP, quick-target chips (gateway/DNS), and tools: ping, traceroute, DNS lookup, port test, active connections, flush DNS — with a copyable session log |
| **Processes** | Live sortable, filterable process table; end-task on row hover |
| **Software** | Installed apps (registry-accurate), startup entries with enabled/disabled state, services, hotfix history |
| **Devices** | Problem-device audit (yellow-bang devices with decoded CM error codes) and printer triage with one-click stuck-queue purge |
| **Security** | Every registered antivirus product via Security Center (third-party AVs detected correctly), firewall/BitLocker/UAC/Secure Boot/TPM at a glance, and a VirusTotal file-reputation check (files are hashed locally — only the SHA-256 leaves the machine) |
| **Health Audit** | 14 weighted checks → score /100 + grade, each failure with a one-click remediation link into Windows Settings |
| **Event Log** | A triage summary that groups events by source with plain-English explanations and remediation links, plus the raw log with level filters and a Crashes tab (BSOD bugchecks, dirty shutdowns, app crashes grouped by faulting module) |
| **Toolbox** | Repair tools with live streamed output (SFC, DISM scan/repair, chkdsk, winsock reset, WU cache reset) and a configuration baseline — snapshot the machine when healthy, diff later to see exactly what changed |
| **Export Report** | One click → polished standalone HTML **and PDF** report, generated in the background with stage-by-stage progress |

Software also audits **scheduled tasks** (non-Microsoft, failures first), **browser extensions**
(Chrome/Edge/Brave/Firefox) and **pending Windows Updates** (list + Settings deep link).
Network gains a **WAN speed test** (via speed.cloudflare.com). **Ctrl+K** opens a command palette
over every page and action.

**v1.5** adds safety, cleanup and malware-triage tooling — see [CHANGELOG.md](CHANGELOG.md) for the
full per-release history. Highlights: **Security** gains an autostart persistence map (with VirusTotal
triage), browser-hijack scan and remote-access/scam check; a new **Cleanup** page (junk, large &
duplicate files, debloat, privacy toggles); a new **Fix-It** page (guided runbooks); restore-point and
backup-posture cards in the Toolbox; a per-process deep-inspect drawer; a reliability timeline;
USB-device history; and an iCloud appearance theme with a customizable glass background.

v1.4 adds the field kit:

- **LAN toolkit** (Network) — subnet scanner (parallel ping sweep + ARP + reverse DNS + vendor
  lookup, with one-click port-profile and Wake from results), saved-machine **Wake-on-LAN**, and a
  **DHCP & DNS health** check (leases, per-server lookup timing, multiple-DHCP warning)
- **Port profile scan** — TCP-connect sweep of 25 common service ports with banner grab
- **Fleet** page — **remote snapshots over WinRM** (credentials passed via environment, never stored)
  and **cross-machine report comparison** using the `.json` twin saved beside every exported report
- **Live sensors** (System) — NVIDIA GPU temp/load/VRAM/power, disk temps when elevated, ACPI zones,
  and a LibreHardwareMonitor bridge for CPU cores when its web server is running — honestly labelled
- **Driver audit** (Devices) — third-party drivers with old/duplicate flags
- **Memory diagnostic** (Toolbox) — schedule the Windows memory test, read past verdicts
- **Battery health trend** (System) — one reading per day, charted across the battery's life
- **Ticket summary** (Toolbox / Ctrl+K) — paste-ready plain-text triage block for your PSA

¹ needs elevation — **Run as admin** in the title bar relaunches elevated and returns to the same page.

Everywhere: values like serials, MACs and IPs are click-to-copy; `/` focuses the page filter; `Esc` clears it; keys 1–8 switch pages.

## Run it

| Flavour | How |
|---|---|
| **Portable** | `dist\Benchly.exe` — single file, no install, run from a USB stick |
| **Installer** | `dist_installer\Benchly-Setup-<version>.exe` — Start-menu + optional desktop shortcut |
| **From source** | `.venv\Scripts\python.exe app.py` |

Keyboard: keys **1–8** switch pages. `--page <name>` opens on a specific page.

## Build from source

```powershell
python -m venv .venv
.venv\Scripts\pip install pywebview psutil pyinstaller pillow
.\build_portable.ps1                                  # → dist\Benchly.exe
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" installer.iss   # → dist_installer\
```

## Architecture

- **Shell** — [pywebview](https://pywebview.flowrl.com/) window on the WebView2 runtime (ships with Windows 11).
- **Backend** (`backend/`) — psutil for fast 1-second telemetry; batched PowerShell/CIM
  queries for the deep inventory (one shell round-trip per domain, JSON over stdout);
  registry reads for software/startup. Everything degrades gracefully without admin rights.
- **Frontend** (`ui/`) — vanilla HTML/CSS/JS, zero CDN dependencies (fully offline),
  custom canvas sparklines, dark theme tuned for long bench sessions.

## Requirements

Windows 10/11 with the WebView2 runtime (preinstalled on Win 11; the portable exe will
prompt on bare Win 10 LTSC machines). No other dependencies.
