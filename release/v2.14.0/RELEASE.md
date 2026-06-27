# Benchly v2.14.0 — Software updates, without winget

A new Toolbox card that answers "is my installed software up to date?" — without going
anywhere near winget.

It reads what's installed locally (straight from the registry) and cross-references a
**curated list of common apps** — browsers, IT and dev tools, media, utilities — against their
**official** sources: the vendor's own version endpoint, or that project's GitHub Releases. When
something's behind, you get the installed-vs-latest gap and a button to open the **official
download page** in your browser.

**Why winget-free matters here:** only plain HTTPS "what's the latest version?" lookups go out,
each one straight to the single vendor. There's no package-manager process for a tight endpoint
protection / AV policy to terminate, and **no list of your installed software is sent anywhere**.
It's read-only — Benchly never downloads or installs anything for you. (This was built in
response to corporate AV terminating winget's behaviour.)

Coverage is the curated catalogue, matched against what you actually have installed, and grows
over time — apps it doesn't recognise are left out rather than guessed at. Lookups are cached for
six hours so re-checks don't re-hit the network. Reachable from the command palette too:
"Check for app updates (no winget)".

## Downloads
- `Benchly-2.14.0-portable.exe` — portable
- `Benchly-Setup-2.14.0.exe` — installer
- `SHA256SUMS.txt` — checksums

See CHANGELOG.md for the full history.
