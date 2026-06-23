# Benchly v2.7.1 — Security & maintenance

A maintenance and security-hardening patch — no feature changes.

- **Domain TLS inspector** now requires **TLS 1.2 or better** explicitly when reading a
  site's certificate. It already negotiated 1.2+ in practice; this makes the floor
  unambiguous and clears a static-analysis (CodeQL) finding.
- **Page navigation** dispatches through a fixed set of known page loaders, so a page name
  can never resolve to anything but a real loader — clears a second CodeQL finding.
- Behind the scenes: pinned build dependencies (`requirements.txt`) and a documented
  dependency/CVE audit routine, so the toolchain stays clean release to release.

## Downloads
- `Benchly-2.7.1-portable.exe` — portable
- `Benchly-Setup-2.7.1.exe` — installer
- `SHA256SUMS.txt` — checksums

See CHANGELOG.md for the full history.
