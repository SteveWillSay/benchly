# Features — the complete tour

This is the long version: every page, every tool, what it reads and what it does.
If you just want the highlights, the [README](../README.md) has them. If you want to
know whether a button is safe to press, [privacy-and-safety.md](privacy-and-safety.md)
is the page you want.

Benchly's pages live down the left rail. Number keys **1–9** jump to the first nine;
**0** jumps to the Toolbox; **Ctrl + K** searches every page and action by name.

---

## Dashboard

The triage glance — what you look at in the first ten seconds.

- **Live vitals** — CPU, RAM, disk I/O and network, each on a one-second sparkline that
  genuinely updates once a second (the loop is visibility-aware, so it pauses when the
  window is hidden instead of piling up work).
- **Per-core grid** — every logical core's load at a glance.
- **Health ring** — the same score the Health Audit computes, mirrored here with a grade.
- **Top processes** — the current CPU and memory hogs, click-through to the Processes page.
- **Volumes** — capacity bars you can click to open the space analyzer on that drive.

## System

The deep inventory — everything the machine *is*.

Machine make/model and serial, the OS edition and build, the CPU (cores, cache, current
clocks), **every RAM module** in its own row (slot, size, speed, manufacturer and part
number), GPUs, the monitor's EDID details, the motherboard, and the firmware: BIOS/UEFI
version, Secure Boot state, and TPM. With elevation it also surfaces **live sensors** —
NVIDIA GPU temperature/load/VRAM/power, disk temperatures, ACPI thermal zones, and CPU
core temperatures when a LibreHardwareMonitor bridge is running (honestly labelled when
it isn't). On laptops, a **battery health trend** charts one reading a day across the
battery's life.

## Storage

Physical disks first: model, bus, and **real SMART health** — temperature, wear level,
and power-on hours (the wear and hours need elevation). Then volumes with capacity and
file system. The **space analyzer** drills into any folder with drive chips, a
breadcrumb trail, and a reveal-in-Explorer on every row, so "where did 200 GB go" takes
about four clicks.

## Network

Adapter and Wi-Fi detail, your public IP on demand, and quick-target chips for the
gateway and DNS servers. Then the tools, each logging to a copyable session console:

- **ping / traceroute / DNS lookup / port test / active connections / flush DNS** — the
  daily console work, plus a WAN **speed test** via speed.cloudflare.com.
- **Domain & website lookup** — paste any domain or URL and Benchly returns a trust
  verdict: WHOIS/RDAP registration (registrar, age, expiry, abuse contact), DNS records
  with SPF/DMARC, the resolved IP's hosting org and country, a live TLS certificate
  inspection, and optional VirusTotal reputation. Young domains, invalid certificates and
  bad reputation get flagged in plain English.
- **URL / redirect unmasker** — expands a shortened link by following the redirect chain
  hop by hop and showing you the real destination, **without running any page scripts**.
  Flags chained shorteners and client-side redirects it can't safely follow.
- **Wi-Fi analyzer** — nearby networks with signal (as % and dBm), band, and 2.4 GHz
  channel congestion across the non-overlapping 1 / 6 / 11.
- **LAN toolkit** — a subnet scanner (parallel ping sweep + ARP + reverse DNS + vendor
  lookup), saved-machine Wake-on-LAN, and a DHCP & DNS health check.

## Processes

A live process table — sortable by any column, filterable as you type, with end-task on
row hover. Click a row for a Process-Explorer-style drawer: loaded modules, open handles,
the network connections it owns, and the full command line.

## Software

Installed applications (read accurately from the registry, not a flaky WMI query),
startup entries with their enabled/disabled state and an estimated boot impact, services,
and hotfix history. Plus three audits — non-Microsoft **scheduled tasks** (failures
first), **browser extensions** across Chrome/Edge/Brave/Firefox, and **pending Windows
Updates** — and an **App updates** tab that finds newer versions of your installed apps
through winget and updates them individually or all at once.

## Devices

The **problem-device audit** — yellow-bang devices with their Configuration Manager error
codes decoded into something readable — plus a **driver audit** (third-party drivers,
old/duplicate flagged), **printer triage** with one-click stuck-queue purge, and **USB
device history**: everything ever plugged in, with serials.

## Security

The trust hub, in tabs:

- **Overview** — every registered antivirus via Security Center (so Bitdefender, ESET and
  friends show as active rather than "no protection"), and firewall / BitLocker / UAC /
  Secure Boot / TPM at a glance.
- **Autoruns** — the full autostart persistence map (Run keys, Winlogon, IFEO, services,
  scheduled tasks, WMI consumers…), each target Authenticode-checked, unsigned entries in
  suspicious paths floated to the top, one-click VirusTotal on any of them.
- **Browser hijack** — hosts-file tampering, system proxy/PAC, and per-browser homepage
  and default-search hijacks.
- **Remote access** — installed/running remote-access tools and the local admin accounts
  to review after a suspected scam.
- **Root certificates** — audits the trusted root store for interception and adware roots
  (Superfish, antivirus TLS-scanning roots, corporate proxies, dev tools) and any
  unrecognised self-signed CA, with weak-key and old-signature notes.
- **Listening ports** — every port the machine accepts connections on, the owning
  process, and whether that program is signed. Unsigned listeners on a network interface
  are flagged.
- **Email headers** — paste the raw headers of a suspicious email; Benchly reconstructs
  the delivery path, finds the originating IP, reads SPF/DKIM/DMARC, and flags the classic
  spoofing tells (Return-Path, Reply-To and display-name mismatches). Parsed entirely on
  your machine.
- **VirusTotal** — hash a local file or paste a hash. The file never leaves the machine;
  only its SHA-256 does.

## Health Audit

Fourteen weighted checks across security, maintenance and resources, rolled into a score
out of 100 and a grade. A pass earns full weight, a warning half, a failure none — and
checks that can't run (no admin, no battery) are excluded rather than counted against you.
Every failure carries a one-click jump to the right Windows Settings page.

## Event Log

A **triage summary** that groups events by source with plain-English explanations and
remediation links — so you read "your disk reported three bad sectors" instead of Event
ID 7. Then the raw log with level filters, a **Crashes** tab (BSOD bugchecks, dirty
shutdowns, app crashes grouped by faulting module, with the minidump list), and a
**Reliability timeline** that charts Windows' own stability index against crashes and
updates.

## Toolbox

The repair bench:

- **Repair tools** — SFC, DISM scan/repair, chkdsk, winsock reset, Windows Update cache
  reset, each streaming its output live, each documenting exactly what it touches.
- **Configuration baseline** — snapshot installed software, services and startup while the
  machine is healthy; compare later to see precisely what changed.
- **Performance snapshot** — a 30-second "why is it slow right now?" capture of the top
  CPU, memory and disk offenders plus system pressure, ready to copy into a ticket.
- **Restore point** and **backup-posture** cards, a **memory diagnostic** launcher, and a
  paste-ready **ticket summary** for your PSA.

## Fix-It

Symptom-first runbooks for the everyday complaints — no internet, no sound, Windows Update
stuck, can't print, running slow — that chain the right diagnostics and offer safe,
confirm-first fixes as they go.

## Cleanup

- **Junk** — measure and clear temp files, caches, Update leftovers, crash dumps and the
  Recycle Bin. File-scoped, junction-safe.
- **Large & duplicate** — the biggest files over a threshold, plus a byte-identical
  duplicate finder. Deletions go to the Recycle Bin.
- **Debloat** — curated, reversible removal of preinstalled junk apps; recommended bloat
  pre-ticked, system packages never touched.
- **Tweaks** — a shelf of documented, reversible Windows toggles across Performance,
  Privacy, Interface, and Ads & noise (Game Mode, GPU scheduling, power plans, Copilot,
  Recall, the Win11 classic right-click menu, faster shutdown, lock-screen ads, and more).
  Each shows the exact registry key it writes.

## Fleet

For more than one machine: compare exported report JSONs side by side to spot drift, and
pull **remote snapshots over WinRM** (credentials passed through the environment for the
single call, never stored).

## Export Report

One click produces a clean, standalone **HTML** report and a **PDF**, generated in the
background with stage-by-stage progress, plus a machine-readable **JSON twin** saved
beside it that powers the Fleet comparison. Hand the HTML/PDF to a client; keep the JSON
for yourself.
