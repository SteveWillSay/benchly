# Benchly v1.8.0

**Put any PC on the bench.** — one-stop Windows diagnostics, triage and repair.

Released 2026-06-13 · git tag `v1.8.0`

## Downloads

| File | What it is |
|------|-----------|
| `Benchly-1.8.0-portable.exe` | Single-file portable app. No install — run from anywhere. |
| `Benchly-Setup-1.8.0.exe` | Inno Setup installer (Start-menu shortcut, uninstaller). |

Verify integrity against `SHA256SUMS.txt`.

## What's new — eight new technician tools

**Updates & maintenance**
- **App updates** (Software) — find and install updates for your apps via winget,
  one-by-one or all at once.
- **Check for updates** — Benchly can check a GitHub release source for a newer build.
- **More tweaks** — Win11 classic right-click menu, faster shutdown, hibernation,
  kill lock-screen/Settings ads, verbose sign-in, Explorer → This PC.

**Security & phishing triage**
- **Trusted root certificate audit** — flags interception/adware roots and
  unrecognised self-signed CAs.
- **Listening ports** — every listener → owning process → signature; unsigned
  network listeners flagged.
- **Email header analyzer** — paste raw headers to trace the path, originating IP and
  SPF/DKIM/DMARC, and catch spoofing. Parsed entirely locally.
- **URL / redirect unmasker** — expand short links and reveal the real destination,
  every hop, without running page scripts.

**Diagnostics**
- **Wi-Fi analyzer** — nearby networks, signal/band, 2.4 GHz channel congestion.
- **Performance snapshot** — a 30-second "why is it slow right now?" capture of the
  top CPU/memory/disk offenders.

See `CHANGELOG.md` for the full history.
