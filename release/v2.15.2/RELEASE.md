# Benchly v2.15.2 — Security hardening

A security-review patch from the recurring audit. **No feature or UI changes** — if you're on
2.15.1 everything looks and works exactly the same.

All three fixes are the same underlying class: a working file for something Benchly does **as an
administrator** sat at a name that could be predicted in advance. Anything else running as you
could have claimed one of those names first and redirected the write somewhere it shouldn't go —
or, in the worst case, swapped the file's contents in the moment between Benchly writing it and
Windows acting on it.

- **Compact a virtual disk** wrote the script it hands to `diskpart` to a fixed name in your temp
  folder, then ran it elevated. That was the sharpest of the three: winning the race meant
  attacker-chosen `diskpart` commands with administrator rights. The script now gets an
  unpredictable name created exclusively for it, and is always cleaned up — including when
  something goes wrong partway through.
- **Battery and energy reports** did the same with `powercfg`'s output. Same fix. As a bonus, the
  battery XML the app parses is now guaranteed to be a file Benchly created itself rather than one
  that could have been left there for it to read.
- **The self-updater's log** moved out of the temp folder to `%APPDATA%\Benchly\update.log`, and
  refuses to follow a shortcut planted at that path — that part of the updater can run elevated.

Also: **Pillow** was listed as something Benchly needs to run. It never was — only a build-time
script that redraws the app icon uses it, and it was never part of the shipped app. It has been
moved to the developer tooling list and updated, so the version you download has one less thing
in it.

None of these were remotely exploitable — they all needed something already running on your PC —
but they were real, and they're gone.

## Downloads
- `Benchly-2.15.2-portable.exe` — portable
- `Benchly-Setup-2.15.2.exe` — installer
- `SHA256SUMS.txt` — checksums

See CHANGELOG.md for the full history.
