# Benchly v2.11.1 — Reliable self-update for installed builds

Fixes the self-update path for the machine-wide (Program Files) install — the case that
"closed but never installed".

Updating a Program Files copy must write into a protected folder, which needs elevation. The
old flow fired a hidden cmd.exe UAC prompt *after* the window closed — easy to miss or decline.
Now the freshly-downloaded build performs the swap itself, the elevation prompt is branded
**Benchly** and **expected** (the app tells you to click Yes), and the helper logs to
`%TEMP%\benchly-update.log`. Portable builds (no elevation) are unchanged.

**Note:** the updater that runs is the one inside your *installed* version, so a copy already
stuck on an older build (e.g. v2.7.0) needs one manual install of this version to get onto the
fixed path — then self-update is reliable.

## Downloads
- `Benchly-2.11.1-portable.exe` — portable
- `Benchly-Setup-2.11.1.exe` — installer
- `SHA256SUMS.txt` — checksums

See CHANGELOG.md for the full history.
