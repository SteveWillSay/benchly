# Benchly v1.7.0

**Put any PC on the bench.** — one-stop Windows diagnostics, triage and repair.

Released 2026-06-13 · git tag `v1.7.0`

## Downloads

| File | What it is |
|------|-----------|
| `Benchly-1.7.0-portable.exe` | Single-file portable app. No install — run from anywhere. |
| `Benchly-Setup-1.7.0.exe` | Inno Setup installer (Start-menu shortcut, uninstaller). |

Verify integrity against `SHA256SUMS.txt`.

## What's new

**Domain & website lookup** (Network page) — type any domain or URL and get a
one-screen trust check before you decide to trust a site:

- **Registration (WHOIS / RDAP)** — registrar, registration / update / expiry
  dates, domain age, registry status flags, registrant org and abuse contact.
- **DNS** — A / AAAA / NS / MX records, plus SPF and DMARC email-spoofing checks.
- **Hosting** — resolved IP, reverse DNS, and the owning network / organisation
  and country.
- **TLS certificate** — issuer, validity window, expiry countdown, hostname
  validation, and the names it covers.
- **Reputation** — VirusTotal domain verdict when an API key is configured.
- **Trust verdict** — plain-English flags for young domains, invalid
  certificates and bad reputation.

Privacy: only the domain name leaves the machine (to rdap.org, and to VirusTotal
if enabled), plus a TLS handshake to the host. No browsing data is sent.

See `CHANGELOG.md` for the full history.
