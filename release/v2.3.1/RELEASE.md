# Benchly v2.3.1 — Reliable self-update

A focused fix for the in-app updater.

Updating an **installed** copy used to hand off to the installer, which had to close
the running app before swapping files. On this app that step could hang — the
installer would stick on *Closing application…* and then vanish without finishing.

Both update paths now use the same mechanic the portable build already used and that
was tested working: download the new program file, quit Benchly, and a tiny helper
waits for the file to unlock, moves the new version into place, and relaunches it.
Installs under `Program Files` get a single UAC prompt; the usual per-user install
(under AppData) needs none.

**Install this one by hand.** The fix lives in the version doing the updating, so it
only takes effect from the next update onward. Grab v2.3.1 below once, and every
update after it applies itself.

## Downloads
- `Benchly-2.3.1-portable.exe` — portable
- `Benchly-Setup-2.3.1.exe` — installer
- `SHA256SUMS.txt` — checksums

See CHANGELOG.md for the full history.
