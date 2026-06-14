# Benchly v2.5.0 — Workplace

Bundle F of the roadmap — for the corporate and small-business machines an IT pro
looks after. A new **Workplace** page with two tabs.

## Posture (read-only)
- **Activation & licensing** — activated or not, the licence channel (OEM / Retail /
  Volume), and the firmware-embedded product key.
- **Identity & domain** — Entra (Azure AD) joined / hybrid / AD domain / workgroup,
  plus SSO and tenant detail. The "why won't Teams/Outlook sign in" answer.
- **Group Policy** — which GPOs actually applied (computer + user), last refresh,
  filtered-out GPOs.
- **Time sync** — current clock offset, source, service state, one-click resync.

## Managed baseline
Set the policies an admin normally pushes via GPO/Intune, on a standalone PC:
Windows Update for Business deferrals & restart behaviour, BitLocker startup-PIN
policy, telemetry level, auto-lock, and UAC. Every control is read first; applying is
opt-in per item, shows the exact registry key, and is reversible (**Clear** = back to
the Windows default). Warns when the machine is already centrally managed; aware of
SKU/TPM limits. Password & lockout policy shown read-only. Needs admin to change.

## Downloads
- `Benchly-2.5.0-portable.exe` — portable
- `Benchly-Setup-2.5.0.exe` — installer
- `SHA256SUMS.txt` — checksums

See CHANGELOG.md for the full history.
