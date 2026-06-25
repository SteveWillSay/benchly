# Benchly v2.8.0 — The repair bench

"Bundle I" — deeper fixes, error decoding, and an accessibility pass.

- **Error-code decoder** (Toolbox / Ctrl+K) — paste any `0x8007…`, NTSTATUS, Stop code or
  decimal for plain English: the meaning, the HRESULT breakdown, and update-specific advice.
- **What's locking this file?** (Toolbox) — enter a path, see which processes hold it open.
- **Full network reset** (Toolbox) — Winsock + TCP/IP stack reset, flush DNS, release/renew in
  one guided run, plus a standalone TCP/IP stack reset.
- **User profile health** (Toolbox) — read-only detection of corrupted (`.bak`) and temporary
  user profiles.
- **Re-register Store & built-in apps** (Toolbox) — the standard broken-Start-menu/Store fix.
- **Blue screens now name the Stop code** (Event Log → Crashes), and Kernel-Power 41 events
  that carried a bugcheck are shown as the crashes they were.
- **Wider autostart/persistence coverage** (Security → Autoruns) — RunServices, policy Run
  keys, RunOnceEx, LSA providers, print monitors.
- **Accessibility** — WCAG AA text contrast, the OS "reduce motion" setting honoured, and
  accessible labels on icon-only buttons.

## Downloads
- `Benchly-2.8.0-portable.exe` — portable
- `Benchly-Setup-2.8.0.exe` — installer
- `SHA256SUMS.txt` — checksums

See CHANGELOG.md for the full history.
