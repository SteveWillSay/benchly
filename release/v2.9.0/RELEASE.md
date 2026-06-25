# Benchly v2.9.0 — One-stop tools, deeper diagnostics & UI polish

"Bundle J" — more tools, deeper forensics, and a full design + accessibility sweep.

### New tools
- **File hash** (Toolbox) — MD5 / SHA-1 / SHA-256 of any file, computed locally.
- **Hosts file viewer** (Toolbox) — active host overrides with non-default entries flagged
  (a redirect/hijack check). Read-only.
- **SMART attributes** (Storage) — the raw drive self-monitoring counters, with reallocated /
  pending / uncorrectable sectors flagged. SATA/ATA mostly; NVMe rarely exposes them.
- **Crash-dump suspects** (Event Log → Crashes) — the third-party drivers loaded in your
  minidumps, the usual BSOD culprits.

### Tweaks (now 53)
- New **Network & power** group (disable IPv6, show Hibernate), plus **Take ownership**
  right-click, **This PC** on the desktop, and **drive letters before names**.

### UI & accessibility
- Sidebar number shortcuts now read as a clean **1–0** sequence.
- Tweak toggles and inputs are properly labelled for screen readers (WCAG 2.1 AA).

## Downloads
- `Benchly-2.9.0-portable.exe` — portable
- `Benchly-Setup-2.9.0.exe` — installer
- `SHA256SUMS.txt` — checksums

See CHANGELOG.md for the full history.
