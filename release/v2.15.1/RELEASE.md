# Benchly v2.15.1 — Find old Store-app (AppX) remnants

A new **Cleanup → App remnants** tab finds the leftovers that uninstalled or half-removed
Store / UWP (AppX) apps leave behind — read-first, as always.

- **Orphaned per-user data folders** — `%LOCALAPPDATA%\Packages\<PackageFamilyName>` directories
  whose package is no longer registered, each with the space it's using and when it was last
  touched. Send them to the **Recycle Bin** (reversible) — and the removal is scoped so only folders
  under your `Packages` directory are ever touched (a reparse point can't escape it).
- **Broken package registrations** — packages Windows still lists via `Get-AppxPackage` but whose
  install files are gone or whose status isn't "Ok". Clear the leftover registration with
  `Remove-AppxPackage` (all-users when you Run as admin).
- **No false positives** — browser and IE **AppContainer** sandbox folders (`cr.sb.*`,
  `windows_ie_ac_001`, …) that also live under `Packages` are filtered out, so they're never
  mistaken for app remnants.

Nothing is removed until you choose. Reachable from the command palette too:
"Find Store-app (AppX) remnants".

## Downloads
- `Benchly-2.15.1-portable.exe` — portable
- `Benchly-Setup-2.15.1.exe` — installer
- `SHA256SUMS.txt` — checksums

See CHANGELOG.md for the full history.
