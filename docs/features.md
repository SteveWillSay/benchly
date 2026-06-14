# The full tour

This is the long version — every page, every tool, what it reads and what it does. If you
just want the highlights, the [README](../README.md) has those. And if you're wondering
whether a particular button is safe to press, [privacy-and-safety.md](privacy-and-safety.md)
is the page you actually want.

Pages live down the left rail. Number keys **1–9** jump to the first nine, **0** lands on
the Toolbox, and **Ctrl + K** searches every page and action by name.

---

## Dashboard

Your first ten-second glance — the stuff you check before you've even sat down properly.

- **Live vitals** — CPU, RAM, disk I/O and network, each on a one-second sparkline that
  honestly updates once a second (the loop pauses when the window's hidden, so it doesn't
  pile up work in the background).
- **Per-core grid** — every logical core's load at a glance.
- **Health ring** — the same score the Health Audit works out, mirrored here with a grade.
- **Top processes** — whatever's eating CPU and memory right now, click-through to Processes.
- **Volumes** — capacity bars you can click to drop straight into the space analyzer.

## System

The deep inventory — everything the machine actually *is*.

Make, model and serial; the OS edition and build; the CPU with its cores, cache and live
clocks; **every RAM module** on its own row (slot, size, speed, maker, part number); the
GPUs; the monitor's EDID; the motherboard; and the firmware — BIOS/UEFI version, Secure
Boot, TPM. Give it admin and it'll also pull **live sensors**: NVIDIA GPU temp/load/VRAM/
power, disk temperatures, ACPI thermal zones, and CPU core temps when a LibreHardwareMonitor
bridge is running (and it'll say so honestly when one isn't). On a laptop, a **battery
health trend** charts a reading a day across the battery's whole life.

## Storage

Physical disks first — model, bus, and **real SMART health**: temperature, wear, and
power-on hours (the wear and hours want admin). Then your volumes, with capacity and file
system. The **space analyzer** lets you dig into any folder with drive chips, a breadcrumb
trail, and a reveal-in-Explorer on every row — so "where did 200 GB go?" is about four
clicks, not an afternoon.

## Network

Adapter and Wi-Fi detail, your public IP on request, and quick-target chips for the gateway
and DNS. Then the tools, each logging to a console you can copy from:

- **ping / traceroute / DNS lookup / port test / active connections / flush DNS** — the
  daily console grind, plus a WAN **speed test** via speed.cloudflare.com.
- **Domain & website lookup** — paste any domain or URL and you get a trust verdict back:
  WHOIS/RDAP registration (registrar, age, expiry, abuse contact), DNS records with SPF and
  DMARC, the resolved IP's host and country, a live look at the TLS certificate, and
  optional VirusTotal reputation. Young domains, dodgy certs and bad reputation all get
  called out in plain English.
- **URL / redirect unmasker** — give it a shortened link and it follows the redirect chain
  hop by hop to show you where it really lands, **without ever running the page's scripts**.
  It flags chained shorteners and client-side redirects it can't safely follow.
- **Wi-Fi analyzer** — nearby networks with signal (as a % and in dBm), band, and how
  congested the 2.4 GHz channels are across the non-overlapping 1 / 6 / 11.
- **LAN toolkit** — a subnet scanner (parallel ping sweep + ARP + reverse DNS + vendor
  lookup), saved-machine Wake-on-LAN, and a DHCP & DNS health check.

## Processes

A live process table you can sort by any column and filter as you type, with end-task on
hover. Click a row and a Process-Explorer-style drawer slides out: loaded modules, open
handles, the network connections it owns, and the full command line.

## Software

Installed apps (read straight from the registry, not a flaky WMI query), startup entries
with their on/off state and an estimated boot impact, services, and hotfix history. Plus
three audits — non-Microsoft **scheduled tasks** (failures first), **browser extensions**
across Chrome/Edge/Brave/Firefox, and **pending Windows Updates** — and an **App updates**
tab that finds newer versions of your installed apps through winget and updates them, one at
a time or all at once.

## Devices

The **problem-device audit** — those yellow-bang devices, with their Configuration Manager
error codes decoded into something a human can read — plus a **driver audit** (third-party
drivers, old/duplicate flagged), **printer triage** with one-click stuck-queue purge, and
**USB device history**: everything that's ever been plugged in, serials and all.

## Security

The trust hub, in tabs:

- **Overview** — every registered antivirus via Security Center (so Bitdefender, ESET and
  the like show as active instead of "no protection"), and firewall / BitLocker / UAC /
  Secure Boot / TPM at a glance.
- **Autoruns** — the full autostart map (Run keys, Winlogon, IFEO, services, scheduled
  tasks, WMI consumers…), each target signature-checked, with the unsigned ones in dodgy
  paths floated to the top and a one-click VirusTotal on any of them.
- **Browser hijack** — hosts-file tampering, system proxy/PAC, and per-browser homepage and
  default-search hijacks.
- **Remote access** — installed and running remote-access tools, plus the local admin
  accounts worth reviewing after a suspected scam.
- **Root certificates** — audits the trusted root store for interception and adware roots
  (Superfish, antivirus TLS-scanners, corporate proxies, dev tools) and any self-signed CA
  it doesn't recognise, with weak-key and old-signature notes alongside.
- **Listening ports** — every port the machine's accepting connections on, the process
  behind it, and whether that program's signed. Unsigned listeners on a network interface
  get flagged.
- **Email headers** — paste the raw headers from a suspicious email and Benchly rebuilds the
  delivery path, finds the originating IP, reads SPF/DKIM/DMARC, and points out the classic
  spoofing tells (Return-Path, Reply-To and display-name mismatches). All parsed right on
  your machine.
- **VirusTotal** — hash a local file or paste a hash. The file never leaves; only its
  SHA-256 does.

## Health Audit

Fourteen weighted checks across security, maintenance and resources, rolled into a score out
of 100 and a grade. A pass earns full marks, a warning half, a fail nothing — and anything
that can't run (no admin, no battery) is left out rather than counted against you. Every
failure comes with a one-click jump to the right Windows Settings page.

## Event Log

A **triage summary** that groups events by source and explains them in plain English, with
remediation links — so you read "your disk reported three bad sectors" instead of squinting
at Event ID 7. Then the raw log with level filters, a **Crashes** tab (BSOD bugchecks, dirty
shutdowns, app crashes grouped by faulting module, with the minidumps), and a **Reliability
timeline** that charts Windows' own stability index against crashes and updates.

## Toolbox

The repair bench:

- **Repair tools** — SFC, DISM scan/repair, chkdsk, winsock reset, Windows Update cache
  reset, each streaming its output live and each spelling out exactly what it touches.
- **Configuration baseline** — snapshot installed software, services and startup while the
  machine's healthy, then compare later to see precisely what changed.
- **Performance snapshot** — a 30-second "why's it slow *right now*?" capture of the top CPU,
  memory and disk offenders plus overall pressure, ready to paste into a ticket.
- **Restore point** and **backup-posture** cards, a **memory diagnostic** launcher, and a
  paste-ready **ticket summary** for your PSA.

## Fix-It

Symptom-first runbooks for the everyday gripes — no internet, no sound, Windows Update stuck,
can't print, running slow — that chain the right diagnostics together and offer safe,
confirm-first fixes as they go.

## Cleanup

- **Junk** — measure and clear temp files, caches, Update leftovers, crash dumps and the
  Recycle Bin. File-scoped, and it won't follow junctions.
- **Large & duplicate** — the biggest files over a threshold, plus a byte-for-byte duplicate
  finder. Deletions go to the Recycle Bin, so they're undoable.
- **Debloat** — curated, reversible removal of the preinstalled junk; the obvious bloat comes
  pre-ticked, and system packages are never touched.
- **Tweaks** — a shelf of documented, reversible Windows toggles across Performance, Privacy,
  Interface, and Ads & noise (Game Mode, GPU scheduling, power plans, Copilot, Recall, the
  Win11 classic right-click menu, faster shutdown, lock-screen ads, and plenty more). Each
  one shows you the exact registry key it writes.

## Fleet

For when it's more than one machine: compare exported report JSONs side by side to spot
drift, and pull **remote snapshots over WinRM** (credentials passed through the environment
for that single call, never stored).

## Export Report

One click gives you a clean, standalone **HTML** report and a **PDF**, built in the
background with stage-by-stage progress, plus a machine-readable **JSON twin** saved next to
them that powers the Fleet comparison. Hand the HTML or PDF to a client; keep the JSON for
yourself.
