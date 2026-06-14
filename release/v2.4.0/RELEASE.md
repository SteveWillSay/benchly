# Benchly v2.4.0 — Won't update, won't boot, disk's full

Bundle E of the v2.4–v2.7 roadmap — the everyday bench killers, all read-first and
documented.

- **Pending restart check** (Toolbox) — reads every signal Windows leaves when it's
  waiting on a reboot (component servicing, Windows Update, files queued to move, a
  queued rename, ConfigMgr) and explains why updates and installers might be quietly
  failing. One-click restart when you're ready.
- **Update doctor** (Toolbox) — recent Windows Update history with the cryptic
  `0x800f…` / `0x80070…` codes decoded into plain English and what to do, plus the
  last successful scan/install and the health of the services updates rely on.
- **Component store cleanup** (Toolbox → repair tools) — analyzes WinSxS, shows what's
  reclaimable, and cleans it up (optional, clearly-warned `/ResetBase`). The honest
  answer to "where did the space on C: go?"
- **Boot-time breakdown** (Event Log → Boot time) — how long recent boots took, the
  specific apps/drivers/services Windows blamed for slowing them, Fast Startup state,
  uptime, and a trend over time.

## Downloads
- `Benchly-2.4.0-portable.exe` — portable
- `Benchly-Setup-2.4.0.exe` — installer
- `SHA256SUMS.txt` — checksums

See CHANGELOG.md for the full history.
