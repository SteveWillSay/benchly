# Benchly v2.1.0

**Put any PC on the bench.** — the "security & incident response" release (Bundle B of v2).

## What's new

- **Persistence & exclusions** (Security) — maps the hiding spots autoruns misses: WMI
  event subscriptions (fileless persistence), services and scheduled tasks with suspicious
  paths, Microsoft Defender exclusions, and what's executed recently (from Prefetch).
  Findings are ranked context, not verdicts.
- **Hardening scorecard** (Security) — high-value Windows hardening checks scored out of
  100, each with a reversible one-click fix that documents exactly what it changes.
- **Attack Surface Reduction rules** — set the key anti-ransomware rules to Audit, then
  Block, from the app.
- **Recover from a scam** (Fix-It) — one guided pass after a remote-access incident, then a
  clear, ordered checklist of what to do next. It flags things to review; it never deletes
  anything for you.

## Downloads

| File | What it is |
|------|-----------|
| `Benchly-2.1.0-portable.exe` | Portable single-file app |
| `Benchly-Setup-2.1.0.exe` | Installer |
| `SHA256SUMS.txt` | Checksums (the in-app updater verifies against this) |

Already on Benchly? **Check for updates** will offer to download and install this — and
you'll see the new progress bar from v2.0.1 onward. See `CHANGELOG.md` for the full history.
