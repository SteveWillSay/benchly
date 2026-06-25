# Benchly v2.13.0 — Hover tips on every control

Benchly now explains itself. Hover (or keyboard-focus) almost any interactive piece and a small,
plain-English tooltip says what it does — so nothing is a guess before you click.

- **Sidebar** — each page button describes what you'll find there (e.g. *Network* → "Adapters,
  Wi-Fi, public IP, ping / traceroute / DNS, and a LAN toolkit").
- **Title bar** — appearance, run-as-admin, export-report and the version "what's new" control.
- **Tweaks** — every toggle says what flipping it does, including whether it needs a reboot or
  restarts Explorer.
- The ~40 existing native hints (repair-tool descriptions, copy buttons, printer actions, …) were
  folded into the same styled component, so everything looks and behaves consistently.

It's one shared, design-system-themed component (it fits graphite, Frosted Glass and Chevron
alike): it opens after a short delay so it never gets in the way, flips above/below to stay on
screen, hides on scroll or click, honours `prefers-reduced-motion`, and is exposed as
`role="tooltip"` to assistive tech.

## Downloads
- `Benchly-2.13.0-portable.exe` — portable
- `Benchly-Setup-2.13.0.exe` — installer
- `SHA256SUMS.txt` — checksums

See CHANGELOG.md for the full history.
