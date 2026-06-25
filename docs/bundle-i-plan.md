# Bundle I — proposed build plan

Drawn from [bundle-i-research.md](bundle-i-research.md) and the design critique. This is a
**proposal for review** — nothing here is built yet. Benchly is already broad, so Bundle I is
about *depth and repair muscle*, not surface area.

Proposed theme: **"Won't fix itself" — deeper repairs + error decoding**, with a small
accessibility pass shipped first as its own patch.

## Sequencing — DECIDED (2026-06-23)

Accessibility is **folded into v2.8.0** (no separate v2.7.2). Building the **full** bundle —
all P1 + P2 + the accessibility/design-system work. A further **Tweaks** expansion is deferred
to **after v2.8.0** (separate exploration).

---

## v2.7.2 — accessibility & polish patch

| Item | Change | Effort | Risk |
|---|---|---|---|
| Contrast | Lift `--text-3` (and/or darken surfaces) to clear WCAG **4.5:1** normal / **3:1** large | S | None |
| Reduced motion | `@media (prefers-reduced-motion: reduce)` — drop sparkline easing & transitions; honours the OS setting | S | None |
| Icon-button names | `aria-label` on every icon-only button (~the 228 audited) | S–M | None |
| Auto-run safe checks | On page load, auto-run the **cheap, read-only** checks (pending-restart, update history); keep manual "Check" only for slow/privileged ones | M | Low |
| Design-system tidy | Tokenise the type scale (`--fs-*`), add `--r-pill`, promote `.btn.danger.solid` colours to tokens | S | None |

---

## v2.8.0 — Bundle I

Priorities: **P1** = high frequency × reliable × on-mission; **P2** = strong but heavier or
narrower; **P3** = nice-to-have / higher risk.

### P1 — do these
| Feature | Page | Why | Effort | Risk |
|---|---|---|---|---|
| **Error-code decoder** (Ctrl+K + Update Doctor) | Toolbox / palette | Paste any hex code → facility + Win32/NTSTATUS/bugcheck name, using the authoritative `wuerror.h` / WU reference tables. Replaces folklore; tiny, pure-data, read-only. | M | None |
| **Full network reset runbook** | Network / Fix-It | One guided flow: `netsh int ip reset` + winsock reset (exists) + flushdns + release/renew + reset proxy, with a clear reboot prompt. The "nothing connects" bench staple. | M | Med (reboot) |
| **Temp/corrupt profile detector** | Health / Security | Read-only detect of temp-profile / `.bak` ProfileList state + a guided migration runbook. Detection ships value even without auto-fix. | M | Low |
| **Autostart/persistence breadth** | Security → Autoruns | Extend the existing map to the fuller Autoruns/MITRE class set (IFEO image-hijacks, LSA providers, Winsock providers, print monitors, WMI subscriptions, legacy RunServices, Policies\Explorer\Run). Pure read, high security value. | M | Low |
| **Event 41 bugcheck correctness** | Event Log → Crashes | Parse Kernel-Power Event ID 41, convert decimal `BugcheckCode` → 8-digit hex → bug-check name. Small correctness win on an existing tab. | S | None |

### P2 — strong, schedule next
| Feature | Page | Why | Effort | Risk |
|---|---|---|---|---|
| **Handle / "what's locking this file?"** | Processes | Process Explorer's killer feature — find which process holds a file/folder handle. Top bench request ("can't delete, in use"). | L | Med |
| **Store/UWP re-registration** | Fix-It | Common Start-menu/Store repair; per-app or all. Confirm exact cmdlet set first. | M | Med |
| **Minidump analysis** | Event Log → Crashes | Parse `C:\Windows\Minidump\*.dmp` to name the faulting driver (BlueScreenView-level), beyond event grouping. | L | Med |
| **SMART attribute depth** | Storage | Name the predictive attributes (reallocated/pending/uncorrectable) instead of a bare flag. Corroborate IDs. | M | Low |

### P3 — opportunistic / gated
| Feature | Note |
|---|---|
| Search-index rebuild, Office C2R repair, font-cache rebuild, .NET repair, Bluetooth reset | Well-known but lower frequency; verify each against MS Learn before building. |
| **WMI repository repair** | `winmgmt /verifyrepository` (read-only) is safe and worth surfacing; `/resetrepository` is **destructive** — gate behind a hard confirmation or defer. |

### Explicitly out of scope
- Third-party **driver packs** (Snappy-style) — risky, off-mission for a read-first tool.

---

## Suggested cut line for v2.8.0
Ship **all P1** (the decoder, network reset, profile detector, autostart breadth, Event-41 fix)
+ the **handle search** from P2 if effort allows — that's a coherent, demoable "repair & decode"
bundle. Everything else rolls to a later bundle.

## Open questions for you
1. Split as proposed (a11y patch **v2.7.2**, then **v2.8.0** Bundle I), or fold a11y into one v2.8.0?
2. Is the **handle-search** feature worth pulling into P1? It's the strongest parity gap but the heaviest P1-adjacent item.
3. Any of these you'd *not* want Benchly doing (e.g. anything that writes to profiles/WMI), to keep it read-first?
