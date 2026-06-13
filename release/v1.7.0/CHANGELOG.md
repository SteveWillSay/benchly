# Changelog

All notable changes to Benchly. Dates are when each release was built.
Versioning is semantic-ish: minor versions add features, patch versions fix/polish.

## [1.7.0] — 2026-06-13

The "know who you're dealing with" release — domain & website intelligence.

### Added
- **Domain & website lookup** (Network) — type any domain or URL and get a
  one-screen trust check, with a plain-English verdict that flags young
  domains, invalid certificates and poor reputation:
  - *Registration (WHOIS/RDAP)* — registrar, registration / update / expiry
    dates, domain age, registry status flags, registrant org and abuse contact.
  - *DNS* — A / AAAA / NS / MX records, plus SPF and DMARC checks for how
    spoofable the domain's email is.
  - *Hosting* — the resolved IP, reverse DNS, and the owning network /
    organisation and country (via RDAP, no API key needed).
  - *TLS certificate* — issuer, validity window, an expiry countdown, whether
    it validates against the hostname, and the names it covers.
  - *Reputation* — VirusTotal domain verdict when an API key is configured.
  - Privacy: only the domain name leaves the machine (to rdap.org, and to
    VirusTotal if enabled), plus a TLS handshake to the host.

## [1.6.0] — 2026-06-12

Windows tweaks and full change-transparency.

### Added
- **Tweaks** tab (Cleanup) — reversible toggles across three groups:
  - *Performance*: Game Mode, hardware-accelerated GPU scheduling, stop background
    Store apps, and one-click power plans (Balanced / High / Ultimate).
  - *Privacy*: turn off advertising ID, tailored experiences, Start suggestions,
    tips, web results in Search, Copilot, Recall, location, and minimise telemetry.
  - *Interface*: left-align the taskbar, show file extensions / hidden files,
    seconds in the clock, dark mode — with a one-click Explorer restart.
- **In-app changelog** — click the version number (or Ctrl+K → "What's new") to see
  every release; a dot marks unseen updates.

### Changed
- **Every action that changes Windows now documents what it does and where** — repair
  tools show the exact paths/services they touch, each tweak shows its registry
  location, and destructive confirmations spell out the files/keys affected.

### Security & stability
- Full senior peer review and SOC security review before release. Hardening applied:
  a strict content-security-policy on the UI; the VirusTotal API key is now encrypted
  at rest with Windows DPAPI; file open/reveal is restricted to web links and report
  files (no arbitrary execution via the bridge); junction-safe cleanup deletion;
  secure temp-file creation; subprocess/stream-leak fixes; and many correctness/robustness
  fixes (poll retry caps, list-snapshot races, error-path handling).

## [1.5.0] — 2026-06-12

The "safety, cleanup & triage" release — 13 new features plus a glass-themed
appearance overhaul.

### Added — Security & malware triage
- **Autostart persistence map** (Security → Autoruns) — enumerates the full
  autostart surface (Run keys, Winlogon, IFEO, AppInit_DLLs, Active Setup,
  auto-start services, WMI consumers), Authenticode-checks each target, floats
  unsigned entries in temp/profile folders to the top, and checks any entry on
  **VirusTotal** with one click (hash-only, never uploads the file).
- **Browser hijack scan** (Security → Browser hijack) — hosts-file tampering,
  system proxy/PAC, and per-browser homepage & default-search hijacks.
- **Remote-access / scam aftermath check** (Security → Remote access) — detects
  installed/running remote-access tools (AnyDesk, TeamViewer, ScreenConnect…),
  lists local administrators and enabled accounts to review after a scam.

### Added — Cleanup & optimization (new Cleanup page)
- **Safe junk cleanup** — measures and clears temp files, browser/Windows
  caches, Update leftovers, crash dumps and the Recycle Bin. File-scoped only.
- **Large & duplicate file finder** — largest-N over a threshold, plus a
  byte-identical duplicate finder (size → SHA-1). Deletions go to the Recycle
  Bin (reversible).
- **Debloat** — curated, reversible per-user AppX removal; recommended bloat
  pre-ticked, system packages never touched.
- **Privacy & telemetry toggles** — documented, reversible switches (advertising
  ID, tailored experiences, Start suggestions, tips, telemetry level, activity
  history) showing current state.

### Added — Repair & guidance
- **Guided Fix-It runbooks** (new Fix-It page) — symptom-first wizards for
  No internet / No sound / Windows Update stuck / Can't print / Running slow,
  chaining diagnostics and safe, confirm-first fixes.
- **Restore-point safety net** (Toolbox) — one-click checkpoint before changes,
  list of existing points, and a shortcut to System Restore.
- **Backup posture audit** (Toolbox) — red/amber/green review of OneDrive folder
  backup, File History, restore points and system image. Audits, never backs up.

### Added — Deep inspection
- **Per-process deep inspect** (Processes → click a row) — a Process-Explorer /
  TCPView style drawer: loaded modules, open file handles, owning network
  connections, full command line, with open-location and end-task.
- **Reliability timeline** (Event log → Reliability) — Windows' stability index
  over time correlated with crashes, WHEA hardware errors and updates.
- **USB device history** (Devices) — every USB device ever connected, with serials.
- **Startup impact estimate** (Software → Startup) — High/Medium/Low boot-impact
  rating alongside each entry.

### Added — Appearance
- **iCloud theme polish** — pronounced frosted-glass translucency, a customizable
  gradient background (presets + custom colours, persisted), and fully rounded
  Win11 window corners. The Graphite theme stays flat and solid.
- **Appearance menu** in the title bar to switch theme and background live.

### Changed
- Reusable Recycle Bin helper so all file deletions are reversible by default.

## [1.4.2] — 2026-06-12

### Added
- **iCloud appearance** — an optional glass-and-gradient theme as a pure CSS
  skin (purple wash, frosted cards, colourful squircle nav icons, Apple-blue
  accent). Switchable live from the title bar, via `--theme icloud`, or saved as
  default. One codebase, two looks — no fork.

## [1.4.1] — 2026-06-12

### Fixed
- **Dashboard "Not Responding" after ~20–30 minutes idle.** The live loop used
  `setInterval` with an `await` inside, so on display-sleep/throttle the queued
  ticks piled up and flooded the WebView2 message pump. Polling now self-chains
  with `setTimeout` (one pending tick max, paused while hidden).

### Added
- Crash logging + a liveness watchdog (`%APPDATA%\Benchly\benchly.log`):
  uncaught-exception hooks and a 30 s heartbeat (memory, threads, bridge age).
  Verified stable over a 7-hour-equivalent soak (memory flat, no leaks).
- `--turbo` soak-test mode (20× polling).

## [1.4.0] — 2026-06-12

The "Field Kit" release — 11 advanced technician tools.

### Added
- **LAN toolkit** (Network) — subnet scanner (ping sweep + ARP + reverse DNS +
  vendor lookup), saved-machine Wake-on-LAN, and DHCP/DNS health.
- **Port profile scan** — TCP-connect sweep of 25 common service ports + banners.
- **Fleet** page — remote machine snapshots over WinRM (credentials passed via
  environment, never stored) and cross-machine report comparison.
- **Live sensors** (System) — NVIDIA GPU temp/load/VRAM/power, disk temps,
  ACPI zones, LibreHardwareMonitor bridge for CPU cores when present.
- **Driver audit** (Devices) — third-party drivers with old/duplicate flags.
- **Memory diagnostic** launcher + past-results reader (Toolbox).
- **Battery health trend** (System) — one reading/day charted over time.
- **Ticket summary** (Toolbox) — paste-ready plain-text triage block.
- Report export now also writes a machine-readable **JSON twin** (powers Fleet
  comparison).

## [1.3.0] — 2026-06-12

Field-testing fixes plus the Security hub.

### Fixed
- **Report export hang** — generation moved to a background job with
  stage-by-stage progress and proper error surfacing; also renders a **PDF**.
- **Third-party antivirus mis-reported** — now reads Security Center, so
  Bitdefender/ESET/etc. are detected correctly (was Defender-only).
- **Dashboard slowdown** — visibility-aware polling and diffed DOM updates;
  fixed a stacked-interval bug on re-selecting the Processes page.
- **Hotfixes tab never populated** — falls back to Windows Update history.
- **Event log range change** — now reloads with a wider window and clear note.

### Added
- **Security hub** with antivirus products, defenses, and **VirusTotal** file
  reputation (local SHA-256, never uploads files).
- **Event-log triage summary** — events grouped by source with plain-English
  explanations and one-click remediation links; plus a Crashes/BSOD tab.
- Editorial title-bar meta cluster replacing the pill chips.

### Changed
- Full peer review of the codebase (36 findings): shared job store, single CIM
  date parser, thread-safe caches, removed dead code.

## [1.2.0] — 2026-06-12

Power-tools release.

### Added
- **Toolbox** — streamed repair tools (SFC, DISM scan/repair, chkdsk, winsock
  reset, Windows Update cache reset) and a **configuration baseline** snapshot +
  diff.
- **Devices** — problem-device (yellow-bang) audit with decoded error codes, and
  printer triage with stuck-queue purge.
- **Software** — scheduled-task audit, browser-extension audit, pending Windows
  Updates.
- **Event log** — BSOD/crash summary grouped by faulting module + minidump list.
- **Network** — WAN speed test (Cloudflare).
- **Command palette** (Ctrl+K) across every page and action.

### Changed
- Applied the typeui "Perspective" design language: vivid green accent, condensed
  display typeface (Bahnschrift), elevation-on-hover.

## [1.1.0] — 2026-06-12

Premium visual overhaul.

### Changed
- Rebuilt the UI to a flat, senior-grade dark design system (one accent, hairline
  borders, real type scale) — replacing the first-draft look.
- Elegant feature improvements: dashboard vitals strip, space-analyzer drill-down,
  sortable process table, health-audit remediation links, click-to-copy values,
  startup enabled/disabled state.

### Added
- Cached/pre-warmed collectors so deep pages open instantly.

## [1.0.0] — 2026-06-12

Initial release.

### Added
- Live dashboard (CPU/RAM/disk/network), full hardware/firmware inventory,
  SMART disk health + space analyzer, network adapter detail and tools
  (ping/traceroute/DNS/port/connections), process manager, installed software /
  startup / services / hotfixes, weighted health-score audit, event log, and a
  standalone HTML report.
- Single portable exe (PyInstaller) and an Inno Setup installer.
