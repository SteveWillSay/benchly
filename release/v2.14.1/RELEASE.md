# Benchly v2.14.1 — Security hardening

A hardening patch from a NIST SSDF / pentest-style review — no feature changes. None of these
were remotely exploitable (the JS↔Python bridge is local-only and the UI is consistently
HTML-escaped), but they were real defects worth removing. Filed and tracked as issues #3–#6.

- **Self-update authenticity (#3).** The updater now refuses any release that has no published
  `SHA256SUMS.txt` — previously a missing checksum silently *skipped* verification and ran the
  unverified exe. And an installed build now only ever updates from Benchly's baked-in official
  source: the user-writable `update_repo` override is honoured only when running from source.
  Together these close a local privilege-escalation path. *(Authenticode code-signing of the
  released exe remains an open follow-up, pending a code-signing certificate.)*
- **Scoped cleanup deletes (#4).** The Recycle-Bin delete behind the large-file / duplicate finders
  is now constrained to folders you actually scanned this session, and refuses system /
  Program Files locations — bounding the blast radius of a privileged delete primitive.
- **Credential-removal escaping (#5).** Removing a saved credential now passes the target as a
  PowerShell literal, so an entry whose name contains a `$(...)` subexpression can't execute.
- **No cleartext secret fallback (#6).** If Windows DPAPI encryption ever fails, the VirusTotal API
  key is now refused with an error rather than silently written to `settings.json` in cleartext.

## Downloads
- `Benchly-2.14.1-portable.exe` — portable
- `Benchly-Setup-2.14.1.exe` — installer
- `SHA256SUMS.txt` — checksums

See CHANGELOG.md for the full history.
