# Benchly v2.6.0 — Network & sharing deep

Bundle G of the roadmap — a new **Sharing & firewall** section on the Network page,
for the silent "can't see the printer / keeps asking me to sign in" problems.

- **Network profile** — catches a connection left on **Public** (which blocks file/
  printer sharing and discovery) and flips it to **Private** in one click.
- **Firewall audit** — per-profile state plus the enabled inbound **allow** rules
  (app/port/scope), flagging anything running from a user-writable folder.
- **Drives & credentials** — mapped network drives (stale ones flagged) and the
  Credential Manager entries — names and types only, **passwords are never read**.
- **DNS & Winsock** — the live DNS resolver cache (an odd address for a known site is
  a hijack hint) and the Winsock/LSP catalog, flagging third-party layered providers.

## Downloads
- `Benchly-2.6.0-portable.exe` — portable
- `Benchly-Setup-2.6.0.exe` — installer
- `SHA256SUMS.txt` — checksums

See CHANGELOG.md for the full history.
