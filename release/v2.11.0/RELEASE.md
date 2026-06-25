# Benchly v2.11.0 — Hardening: elevated tools hidden until elevated

A hardening pass on the UI. Anything that needs administrator rights to run is now hidden from
the standard (non-elevated) view and only appears once you Run as admin — repair tools, admin
tweaks, hardening/ASR fixes, Defender exclusion management, restore points, the managed baseline,
take-ownership, print-queue purge, and more. Command-palette entries for those tools are filtered
out too.

Privileged read-only data that can't load without elevation is hidden as well (rather than a
"needs admin" placeholder): SMART attributes, TPM / Secure Boot / BitLocker, advanced storage
health, the Defender exclusion list, recent-execution, and the full boot breakdown.

The Standard badge explains elevated tools are hidden; Run as admin reveals them all. The Health
Audit and hardening scorecard stay visible and degrade honestly.

## Downloads
- `Benchly-2.11.0-portable.exe` — portable
- `Benchly-Setup-2.11.0.exe` — installer
- `SHA256SUMS.txt` — checksums

See CHANGELOG.md for the full history.
