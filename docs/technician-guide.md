# Benchly — Technician's Guide

The full walkthrough: every screen, what each tab and button does, and what needs
administrator rights. Written for the person with the machine on the bench — hand it to a
junior, or keep it open while you work. For the highlights, the [README](../README.md) has
those; for the exact "what changes / what leaves the machine" detail, see
[privacy-and-safety.md](privacy-and-safety.md).

---

## 1. The two rules Benchly runs on

Everything below rests on two promises, because Benchly is built to run on machines you don't
own:

1. **Every change is spelled out before it happens.** A repair tool names the exact paths and
   services it will touch. A tweak shows the precise registry key it writes. A destructive
   action lists what it will remove *before* you confirm — and most of it is reversible.
2. **Nothing leaves the machine quietly.** By default nothing leaves at all. The handful of
   network features (VirusTotal, domain lookup, update check…) are named where you use them and
   send the bare minimum — a file's SHA-256, never the file itself.

No telemetry, no account, no background service. Benchly does nothing on its own; everything
that happens is something you clicked.

## 2. Getting it running

- **Portable** — `Benchly-x.y.z-portable.exe` is one file. Run it off a desktop, a share or a
  USB stick; it leaves nothing behind but its settings in `%APPDATA%\Benchly`.
- **Installer** — `Benchly-Setup-x.y.z.exe` adds a Start-menu entry and a clean uninstaller.
- Runs on **Windows 10 / 11 (64-bit)** on the WebView2 runtime (already present on current
  builds; a stripped LTSC image gets prompted to install it once).

### The window at a glance

- **Title bar** shows the machine name, OS, uptime, and a **session badge**: **Standard** or
  **Elevated**.
- **Run as admin** (title bar) relaunches Benchly elevated and drops you back on the same page.
- **⊘ Appearance** (title bar) switches the look and accent — see §3.
- **Export report** (title bar) builds a client-ready report — see §21.
- The **version number** (bottom-left) opens "What's new"; a dot means there's an unread entry.

### Standard vs. elevated — the hide-until-elevated model

Benchly runs fine as a standard user, but Windows keeps some things behind admin rights: SMART
drive wear, BitLocker/TPM/Secure Boot detail, the full port→process map, the repair tools, and
machine-wide tweaks. **Until you elevate, those features are *hidden* — not greyed-out and
teasing.** So the standard view only ever shows what you can actually use. Click **Run as
admin** to reveal the rest. Nothing ever escalates on its own. Throughout this guide, *(admin)*
marks something that appears or works only when elevated.

## 3. Navigation & appearance

| How | What it does |
|---|---|
| **Left rail** | Every page is one click. |
| **Number keys 1–9** | Jump to the first nine pages; **0** lands on the Toolbox. |
| **Ctrl + K** | The command palette — fuzzy-search every page *and* action by name, then Enter. |
| **/** | Focus the current page's filter box · **Esc** clears it. |
| **Hover anything** | Every control has a plain-English tooltip explaining it before you click. |
| **Click-to-copy** | Serials, MACs, IPs, hashes — click to copy. |

**Appearance (⊘ in the title bar).** Four themes, switched live: **Precision** (the default —
an editorial, instrument-panel look with a **pick-your-own accent**: Iris, Coral, Amber or
Teal), **Graphite** (the original flat-dark theme, kept pixel-for-pixel), **Frosted Glass**
(glass over a gradient you can recolour), and **Chevron** (warm amber, all-lowercase). Your
theme and accent are remembered. You can also boot straight into one with `--theme graphite`
(or `frost` / `chevron`) and onto a page with `--page <name>`.

---

## 4. Dashboard

Your ten-second glance — the stuff you check before you've sat down.

- **Live vitals** — CPU, RAM, disk I/O and network, each on a one-second sparkline (the loop
  pauses when the window's hidden).
- **Status pills** (top) — uptime, C: free, memory, antivirus, disks, updates, pending-reboot.
- **Health ring** — the same score the Health Audit computes, with a grade; **Details ›** jumps
  to Health audit.
- **Logical cores** — every thread's load at a glance.
- **Top processes** — what's eating CPU/RAM now; **All ›** jumps to Processes.
- **At a glance / Volumes** — machine summary; click a volume bar to drop into the space analyzer.

## 5. System

The deep inventory — everything the machine actually *is*. Make/model/serial, OS edition and
build, CPU with live clocks, **every RAM module** on its own row (slot, size, speed, part
number), GPUs, monitor EDID, motherboard, BIOS/UEFI, Secure Boot, TPM.

- **Live sensors** *(fuller with admin)* — GPU temp/load/VRAM/power, disk temperatures, ACPI
  thermal zones, CPU core temps when a LibreHardwareMonitor bridge is running (it says so
  honestly when one isn't).
- **GPU stability & throttle** — **Check** runs live clocks, the *reason* the GPU is throttling
  now, and a 30-day history of driver resets (TDRs). The honest "is my overclock stable?"
- **Display refresh** — flags a monitor left below its best refresh rate (the "144 Hz panel
  parked at 60").
- **Virtualization** — WSL distros + memory cap, ballooning WSL/Docker `.vhdx` files (with an
  optional non-destructive compact), Hyper-V switches, hardware-virtualization state.
- **Battery & power efficiency** *(the energy trace needs admin)* — wear, cycle count, and a
  `powercfg /energy` trace naming what's hurting efficiency.
- **Environment & PATH** — flags every PATH entry pointing at a missing folder, a duplicate, or
  a stray quote; **Clean** removes the broken/duplicate entries (prior value backed up first).
- **Installed runtimes** — the .NET / VC++ / DirectX a program quietly needs, in one place.

## 6. Storage

- **Physical disks** — model, bus, and **real SMART health**: temperature, wear, power-on hours
  *(wear and hours need admin)*.
- **SMART attributes** *(on demand)* — the raw self-monitoring counters, reallocated/pending/
  uncorrectable sectors flagged. SATA/ATA mostly; NVMe rarely exposes them.
- **Drive health forecast** — **trends** wear and creeping read/write errors over time and scores
  each drive's risk, so you swap a dying disk before it takes the data. A small history lives in
  `%APPDATA%\Benchly\history`.
- **Advanced storage health** *(some fields admin)* — whether TRIM is running, Storage Spaces
  pool health, reliability counters, shadow-copy space in use, the filesystem dirty bit.
- **Volumes + space analyzer** — capacity and file system per volume. Click **analyze** for a
  **treemap** (folders sized by disk use and tinted by content type), a **File types** by-
  extension view, and a **List** view with reveal-in-Explorer on every row.

## 7. Network

Adapter and Wi-Fi detail, **Show public IP** on request, quick-target chips for gateway/DNS.

- **Tools** (each logs to a copyable console): **ping · traceroute · DNS lookup · port test ·
  active connections · flush DNS**, plus a WAN **speed test** (Cloudflare).
- **Bufferbloat test** — **Run** measures latency idle vs. saturated and grades the gap (why a
  call stutters when someone starts a download).
- **Domain & website lookup** — type any domain/URL, **Look up** returns a trust verdict:
  WHOIS/RDAP (registrar, age, expiry, abuse contact), DNS with SPF/DMARC, the resolved IP's host
  and country, a live TLS certificate read, and optional VirusTotal reputation. Only the domain
  name leaves the machine.
- **URL / redirect unmasker** — expands a shortened link hop-by-hop to show where it really
  lands, **without running the page's scripts**.
- **Wi-Fi analyzer** — nearby networks with signal (%/dBm), band, and 2.4 GHz channel congestion.
- **LAN toolkit** — subnet scanner (ping sweep + ARP + reverse DNS + vendor lookup), saved-
  machine Wake-on-LAN, DHCP/DNS health.
- **Sharing & firewall** — spot a connection left on **Public** and flip it to **Private** in a
  click; the firewall's per-profile state and enabled inbound *allow* rules (anything running
  from a user-writable folder is flagged; a rule can be disabled, confirmed and reversible);
  mapped network drives and Credential Manager entries (**names/types only — passwords are never
  read**); the DNS resolver cache and the Winsock/LSP catalog (third-party layered providers
  flagged).

## 8. Processes

A live table you can sort by any column and **filter** as you type, with **end-task on hover**.
Click a row for a Process-Explorer-style drawer: loaded modules, open handles, the network
connections it owns, and the full command line. **Pause** freezes the refresh for reading.

## 9. Software

Installed apps (read straight from the registry), in tabs:

- **Installed** — every app with version, publisher, install date, size.
- **Startup** — Run-key and Startup-folder entries with on/off state and an estimated boot impact.
- **Services** — running first, then automatic-but-stopped.
- **Hotfixes** — installed updates (falls back to the Windows Update history when QFE is empty).
- **Scheduled tasks** — non-Microsoft tasks, failures first.
- **Browser extensions** — across Chrome/Edge/Brave/Firefox.
- **Pending updates** — what Windows Update has queued.
- **App updates** — **Check** finds newer versions of your installed apps via **winget** and
  updates them individually or all at once, with live output. (For machines where winget is
  blocked, use **Cleanup → App remnants**' sibling: the winget-free **Software updates** check in
  the Toolbox — §17 — which checks official sources instead.)

## 10. Devices

- **Problem devices** — the yellow-bang list, with Configuration-Manager error codes decoded
  into plain English.
- **Driver audit** — third-party drivers, old/duplicate flagged.
- **USB device history** — everything ever plugged in, serials and all.
- **Printer doctor** — catches "offline" printers, spots one that grabbed a new DHCP IP (it
  pings to check), flags duplicate drivers; **bring back online** or **print a test page**.
- **Audio device doctor** — playback/recording endpoints with state, the two audio services, and
  a one-click **restart** of them.

## 11. Security

The trust hub, in tabs:

- **Overview** — every registered antivirus via Security Center (so a third-party AV shows
  active, not "nothing's protecting this PC"), plus firewall / BitLocker / UAC / Secure Boot /
  TPM at a glance.
- **Autoruns** — the full autostart map (Run keys, Winlogon, IFEO, services, scheduled tasks,
  WMI consumers…), each target signature-checked, unsigned entries in dodgy paths floated up.
  One-click **VirusTotal** on any of them (hash only).
- **Browser hijack** — hosts-file tampering, system proxy/PAC, and per-browser homepage and
  default-search hijacks.
- **Remote access** — installed/running remote-access tools and the local admin accounts worth
  reviewing after a suspected scam.
- **Root certificates** — audits the trusted-root store for interception/adware roots and
  unrecognised self-signed CAs, with weak-key/old-signature notes. Runs on open; **Re-scan** to
  refresh.
- **Listening ports** — every port the machine accepts connections on, the process behind it, and
  whether it's signed; unsigned listeners on a network interface are flagged. *(The full
  process map is richest with admin.)*
- **Persistence & exclusions** *(some reads admin)* — the hiding spots a plain autoruns view
  misses: WMI event subscriptions, services/tasks running from suspicious places or encoded
  PowerShell, the **Defender exclusion list**, and what's run recently (Prefetch). Ranked
  context, never a verdict — nothing is auto-removed.
- **Hardening** — a scorecard of high-value checks (LLMNR, SMBv1, AutoRun, NLA, PowerShell
  logging, Guest account, PUA protection…) scored out of 100, each with a reversible one-click
  fix that spells out what it changes *(applying needs admin)*. Alongside it, the key **Attack
  Surface Reduction** rules can be set to **Audit** (log-only) then **Block**.
- **Email headers** — paste raw headers, **Analyze** rebuilds the delivery path, finds the
  originating IP, reads SPF/DKIM/DMARC and points out the classic spoofing tells. All local.
- **VirusTotal** — hash a local file or paste a hash; the file never leaves, only its SHA-256.

## 12. Health audit

Fourteen weighted checks across **Security / Maintenance / Resources**, rolled into a score out
of 100 and a grade. A pass earns full marks, a warning half, a fail nothing; anything that
can't run (no admin, no battery) is left out rather than counted against you. Each failure has a
one-click jump to the right Windows setting. **Refresh** re-runs it.

## 13. Event log

- **Triage summary** — events grouped by source and explained in plain English ("your disk
  reported three bad sectors", not "Event ID 7"), with remediation links.
- **Raw log** — with level filters and a time-range selector.
- **Crashes & BSODs** — bugchecks with the Stop code named, dirty shutdowns, app crashes grouped
  by faulting module, plus the minidump suspects.
- **Reliability timeline** — Windows' own stability index charted against crashes and updates.
- **Boot time** *(the detailed breakdown needs admin)* — how long recent boots took, the apps/
  drivers/services Windows blamed, Fast Startup state, and a trend.

## 14. Toolbox

The repair bench.

- **Restore point** — **Create restore point** *(admin)* before making changes; **Open System
  Restore**.
- **Backup posture** — **Check**: a red/amber/green audit of OneDrive backup, File History,
  restore points and system image. Audits; never backs up.
- **Pending restart** — **Check** reads every signal Windows leaves when a reboot is owed (and
  why updates keep failing); **Restart now** *(with a warning)* when ready.
- **Update doctor** — **Check** shows recent Windows Update history with the cryptic `0x800f…`
  codes decoded, the last successful scan/install, and the health of the services updates rely on.
- **Software updates (no winget)** — **Scan** reads installed apps and checks a curated list of
  common apps against their **official** sources (vendor endpoints / GitHub Releases) for a newer
  version — no winget, nothing installed. **Get x.y.z** opens the vendor's official download page.
- **Error-code decoder** — paste any Windows status code (`0x8007…`, an NTSTATUS, a Stop code, a
  decimal) for plain English.
- **User profile health** — **Check** reads ProfileList for corrupted (`.bak`) and temporary
  profiles. Read-only.
- **What's locking this file?** — enter a path; **Find lockers** lists the processes holding an
  open handle.
- **File hash** — **Pick a file** for MD5/SHA-1/SHA-256, computed locally.
- **Hosts file** — **View** the active mappings, non-default ones flagged. Read-only.
- **Performance snapshot** — **Capture 30s snapshot**: the top CPU/memory/disk offenders + system
  pressure, ready to **Copy** into a ticket.
- **Power, sleep & wake doctor** — **Check**: plain-English answers to "why won't it sleep",
  "what woke it at 3 AM", "what's armed to wake it"; reversible toggles to disarm a wake device
  or a wake-capable task.
- **Gremlin hunters** — *Disk / CPU culprit* (what's hammering it when "nothing" is), *USB drops*
  (devices that keep reconnecting), and *Mark the freeze* (hit it the instant something hiccups
  and Benchly scoops up the logs around that moment).
- **Repair tools** *(admin)* — SFC, DISM scan/repair, chkdsk, winsock reset, Windows Update cache
  reset, full network reset, component-store (WinSxS) cleanup, re-register Store & built-in apps
  — each streams its output live and spells out exactly what it touches.
- Plus a **memory diagnostic** launcher and a paste-ready **ticket summary**.

## 15. Fix-It

Symptom-first runbooks — *no internet, no sound, Windows Update stuck, can't print, running
slow* — that chain the right diagnostics together and offer safe, confirm-first fixes as they
go. There's also **Recover from a scam**: one guided, read-only pass after a remote-access
incident that checks remote-access tools, persistence, Defender exclusions and admin accounts,
then hands you an ordered checklist. It only ever flags things — it never deletes anything.

## 16. Cleanup

Tabs: **Junk files · Large & duplicate · Debloat apps · App remnants · Tweaks · Repair.**

- **Junk files** — **Scan** measures and clears temp files, caches, Update leftovers, crash dumps
  and the Recycle Bin. File-scoped; won't follow junctions.
- **Large & duplicate** — the biggest files over a threshold, plus a byte-for-byte duplicate
  finder. Deletions go to the **Recycle Bin** (undoable).
- **Debloat apps** *(per-user)* — curated, reversible removal of preinstalled Store apps; obvious
  bloat is pre-ticked; system packages are never touched.
- **App remnants** — **Scan for remnants** finds the leftovers uninstalled/half-removed **Store /
  UWP (AppX)** apps leave behind: **orphaned per-user data folders** (`%LOCALAPPDATA%\Packages`,
  with the space each uses) and **broken package registrations** Windows still lists but whose
  files are gone. **Remove selected → Recycle Bin** is reversible and scoped so only folders under
  your `Packages` directory are ever touched; **Reveal** opens one in Explorer; **Clear
  registration** *(admin)* clears a ghost package with `Remove-AppxPackage`. Browser/IE
  AppContainer sandbox folders are filtered out so they're never mistaken for remnants.
- **Tweaks** — a shelf of documented, reversible toggles across Performance / Gaming / Network &
  power / Privacy / Interface / Ads & noise, plus one-click **power plans**. Each toggle shows the
  exact registry key it writes; flip it off to restore the Windows default. Some interface tweaks
  offer **Restart Explorer to apply**. *(Machine-scope tweaks need admin and are hidden until
  elevated.)*
- **Repair** — the cosmetic-breakage fixes (blank icons, dead Store, broken Start search); it
  rebuilds caches and restarts the shell without touching your files.

## 17. Helper

The page for when *you're* the family's IT person — big friendly buttons, plain language.

- **Text my tech person** — a plain-English summary of what looks wrong, ready to paste.
- **Calm this computer down** — silences ads, widgets, tips and Start suggestions in one click
  (all reversible from Cleanup → Tweaks).
- **Make it normal again** — instant, reversible text-size presets.
- **Camera & microphone doctor** — the "works everywhere but Zoom" fix: checks the privacy
  permission and which app holds the device; allow a blocked app in a click.
- **BitLocker recovery key** *(reveal needs admin)* — shows which drives are encrypted and reveals
  the key so you can save it before a repair demands it. Never logged, cached or sent anywhere.
- **Rescue my photos & documents** — copies Desktop/Documents/Pictures onto a drive you plug in.
  It only ever **copies**, never moves — a failing source disk is never written to.
- **Is this a scam?** — paste a suspicious email or link for a simple red/amber/green read.

## 18. Fleet

For more than one machine: compare exported report JSONs side by side to spot drift, and pull
**remote snapshots over WinRM** (credentials you type, passed through the environment for that
one call and **never written to disk**).

## 19. Workplace

The corporate / small-business page, in four tabs — three read-only, one that configures.

- **Posture** *(some fields admin)* — activation & licensing (read via CIM, no slmgr pop-ups),
  identity & domain join (`dsregcmd`: Entra-joined / hybrid / AD / workgroup, plus SSO/PRT and
  tenant), Group Policy results, and clock/time-sync with a one-click **resync**.
- **Applied policies** — every Group Policy / MDM setting actually in force, grouped by area, each
  with its registry key, type and value. The receipts for what your management pushed.
- **Corporate IT** — the management/security agents present and their state (SCCM, Intune, MDM
  enrolment, Defender for Endpoint, third-party EDR, VPN/ZTNA, backup) plus how Windows Update is
  managed (WSUS / Update for Business), the proxy and the managed network.
- **Managed baseline** *(applying needs admin)* — for a *standalone* PC, set the policies an admin
  would push via GPO/Intune: Windows Update deferrals, a BitLocker startup PIN, telemetry, auto-
  lock, UAC. Each is opt-in, shows the exact key, and is reversible (**Clear** returns it to the
  Windows default). Warns if the machine is already centrally managed.

## 20. Export Report

**Export report** (title bar) builds a clean, standalone **HTML** report and a **PDF** in the
background with stage-by-stage progress, plus a machine-readable **JSON twin** saved alongside.
Hand the HTML or PDF to a client; keep the JSON — it's what Fleet compares.

---

## 21. What needs administrator rights

Run everything as a standard user first; elevate only when you need one of these (they stay
hidden until you do):

- **Reads:** SMART wear & power-on hours, TPM / Secure Boot / BitLocker detail, advanced storage
  health, the full listening-port→process map, the Defender exclusion list, recent-execution
  (Prefetch), the detailed boot breakdown, live power/energy trace.
- **Actions:** the Toolbox repair tools, machine-scope tweaks and hardening/ASR fixes, removing a
  Defender exclusion, creating a restore point, clearing a broken AppX registration, revealing the
  BitLocker key, the Workplace managed baseline, and app updates that install machine-wide.

Use **Run as admin** in the title bar; Benchly relaunches elevated and returns you to the same
page. It never escalates on its own.

## 22. The safety model (read before pressing anything destructive)

- **Read-first.** Most of Benchly is read-only; the parts that change Windows show the change
  first.
- **Reversible.** Tweaks restore the Windows default when toggled off; file deletions go to the
  Recycle Bin; the AppX-remnant and cleanup removals are Recycle-Bin and path-scoped.
- **Named egress.** Nothing leaves by default. VirusTotal gets a hash; a domain lookup the domain
  name; a remote snapshot the credentials you typed (never stored). The email and URL tools read
  and resolve — they never run anything.
- **Secrets.** The VirusTotal API key is DPAPI-encrypted at rest; the BitLocker recovery key is
  only ever shown to you, never logged or sent.

If a button changes something and *doesn't* tell you where — that's a bug. The full line-by-line
version is in [privacy-and-safety.md](privacy-and-safety.md).
