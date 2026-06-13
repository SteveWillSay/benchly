# Benchly v1.6.0

**Put any PC on the bench.** — one-stop Windows diagnostics, triage and repair.

Released 2026-06-12 · git tag `v1.6.0`

## Downloads

| File | What it is |
|------|-----------|
| `Benchly-1.6.0-portable.exe` | Single-file portable app. No install — run from anywhere (USB stick, etc.). |
| `Benchly-Setup-1.6.0.exe` | Inno Setup installer (Start-menu shortcut, uninstaller). |

Verify integrity against `SHA256SUMS.txt`:

```powershell
Get-FileHash .\Benchly-1.6.0-portable.exe -Algorithm SHA256
```

## Highlights

- **Tweaks** — reversible Performance / Privacy / Interface registry toggles +
  one-click power plans, each documenting the exact registry location it changes.
- **In-app changelog** — click the version number (or Ctrl+K → "What's new").
- **Full change-transparency** — every action that changes Windows now spells out
  what it does and where (paths, services, registry keys).

## Security & stability

Shipped after a senior peer review and a SOC security review. Hardening:

- Strict content-security-policy on the UI.
- VirusTotal API key encrypted at rest with Windows DPAPI.
- File open/reveal restricted to web links and report files (no arbitrary
  execution via the JS↔Python bridge).
- Junction-safe cleanup deletion; secure temp-file creation.
- Subprocess / stream-leak fixes; poll retry caps; job-read race fixes.

See `CHANGELOG.md` for the complete history.

## Requirements

- Windows 10/11 (x64). WebView2 runtime (preinstalled on current Windows 11).
- Some checks (SMART counters, BitLocker, TPM, Secure Boot, HKLM tweaks) require
  running as administrator — the app prompts where needed.
