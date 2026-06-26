# Getting started with Benchly

This is the friendly walkthrough — from "I just downloaded it" to actually fixing something —
in the order you'll want it. No prior tour needed. If you'd rather have the exhaustive,
page-by-page reference, that's [features.md](features.md); the "is this button safe?" answers
live in [privacy-and-safety.md](privacy-and-safety.md); and the quick one-liners are in the
[FAQ](faq.md).

---

## 1. Get it running (about a minute)

Grab a build from the [**Releases**](../../releases/latest) page:

- **`Benchly-x.y.z-portable.exe`** — one file, nothing installed. Run it off your desktop, a
  network share, or a USB stick. This is the one to keep on your toolkit drive.
- **`Benchly-Setup-x.y.z.exe`** — a tidy install with a Start-menu entry and an uninstaller, if
  you'd rather Benchly live on this machine properly.

Double-click and, about a second later, you're looking at the Dashboard. There's no account to
make and nothing to configure first.

> **Windows 10 or 11, 64-bit.** Benchly rides on the WebView2 runtime, which is already present
> on every Windows 11 and current Windows 10. On a stripped-down LTSC image that's missing it,
> Benchly will point you at the quick one-time download.

## 2. Your first minute on the bench

The **Dashboard** is the ten-second glance: live CPU, RAM, disk and network graphs that tick
once a second, a per-core grid, a **health-score ring**, and whatever's hogging the machine
right now. It's the "is anything obviously on fire?" view.

Three things make the rest of the app quick to learn:

- **The left rail is everything.** Each page is one click. Or tap a **number key** (`1`–`9`,
  and `0` for the Toolbox) to jump straight there.
- **Ctrl + K opens the command palette** — start typing and it fuzzy-searches every page *and*
  every action by name. If you know what you want but not where it lives, this is the fastest
  way to it.
- **When in doubt, hover.** Every page, button and toggle has a **plain-English tooltip** that
  says what it does before you click. Nothing in Benchly is a mystery you have to click to
  understand.

And anything you'd otherwise be copying down by hand — a serial, a MAC, an IP, a hash — is
**click-to-copy**.

## 3. When (and why) to click "Run as admin"

Benchly runs perfectly as a standard user — most of it is read-only and works straight away.
But Windows keeps some things behind administrator rights: SMART drive wear, BitLocker, TPM and
Secure Boot detail, the full listening-port-to-process map, the repair tools, and the
machine-wide tweaks.

Until you elevate, **those features are simply hidden** — not greyed out and teasing. So the
standard view only ever shows what you can actually use. When you want the rest, click **Run as
admin** in the title bar: Benchly relaunches elevated, reveals everything that was gated, and
drops you right back on the page you were reading. It never escalates on its own.

A quick way to tell where you stand: the title bar shows a **Standard** or **Elevated** session
badge.

## 4. The jobs people actually open Benchly for

You don't need to learn every page. Here are the common calls and exactly where to go.

### "This PC feels slow."

1. **Dashboard** first — is something pegging CPU, RAM or disk right now? The top-processes
   card names it.
2. **Toolbox → Performance snapshot** takes a 30-second capture of the worst CPU, memory and
   disk offenders and overall pressure — paste-ready for a ticket.
3. If it's *intermittent*, the **Toolbox → gremlin hunters** catch what's gone by the time you
   look: the disk/CPU culprit when "nothing" is running, USB devices that keep dropping, and a
   "mark the freeze" button that scoops up the logs around the exact moment it hiccuped.
4. **Software → Startup** shows what's loading at boot and its estimated impact, so you can trim
   the launch.

### "Is this thing safe — did someone get scammed on it?"

Head to **Security**. The **Overview** reads Windows Security Center, so a real third-party AV
shows as active (not "nothing's protecting this PC"). Then work down the tabs: **Autoruns**
maps the whole autostart surface with signatures, **Persistence & exclusions** hunts the quiet
spots (WMI subscriptions, encoded-PowerShell services, Defender exclusions, what's run
recently), **Root certificates** surfaces the roots that quietly intercept HTTPS, and
**Listening ports** shows what's accepting connections and whether it's signed.

For a phishing email or a dodgy link, paste them into **Security → Email headers** and the
**Network → URL / redirect unmasker** — both read and resolve locally without ever *running*
anything. And if there's been a remote-access incident, **Fix-It → Recover from a scam** walks
one guided, read-only pass and hands you an ordered checklist of what to do next.

> Benchly won't remove malware *for* you — it shows you exactly where to look and hands you the
> tools. Everything it flags is context, never an automatic verdict.

### "Where did all my disk space go?"

**Storage → space analyzer** drills into any folder with a visual treemap, drive chips and a
reveal-in-Explorer on every row — "where did 200 GB go?" is about four clicks. Then **Cleanup →
Junk** clears temp files, caches, Update leftovers and the Recycle Bin (deletions go *to* the
Recycle Bin, so they're undoable), and **Cleanup → Large & duplicate** finds the big files and
byte-for-byte duplicates. For a swollen `C:\Windows`, **Toolbox → component-store analyzer**
measures WinSxS and cleans the reclaimable part.

### "Something's broken — printing, sound, no internet, Update stuck."

Start at **Fix-It**: pick the symptom and it chains the right diagnostics together with
safe, confirm-first fixes. When you'd rather drive it yourself, the **Toolbox** has the heavy
hitters streaming their output live — SFC, DISM, chkdsk, winsock reset, Windows Update cache
reset — each spelling out exactly what it touches. Two Toolbox cards answer the everyday "why":
**Pending restart** (the breadcrumbs Windows leaves when a reboot is owed — often why updates
keep failing) and the **Update doctor** (it decodes those cryptic `0x800f…` codes into plain
English). For cosmetic breakage — blank icons, dead Store, broken Start search — there's
**Cleanup → Shell & cache repair**.

### "I'm the family's IT person and I'm fixing a relative's laptop."

The **Helper** page is built for exactly this — big friendly buttons, plain language:

- **Text my tech person** — a plain-English summary of what looks wrong, ready to paste into a
  message.
- **Calm this computer down** — silences ads, widgets, tips and Start suggestions in one click
  (all reversible).
- **Rescue my photos & documents** — copies Desktop, Documents and Pictures onto a drive you
  plug in. It only ever *copies*, never moves, so a failing source disk is never written to.
- **BitLocker recovery key** — reveals it (with admin) so you can save it somewhere safe
  *before* a repair ever demands it. It's never logged, cached or sent anywhere.
- **Make it normal again** and the **Camera & microphone doctor** handle the "everything's
  suddenly huge" and "works everywhere except Zoom" calls.

### "I need to hand the client something."

**Export Report** (top-right) builds a clean, standalone **HTML** report and a **PDF** in the
background, with a machine-readable **JSON twin** saved alongside. Hand over the HTML or PDF;
keep the JSON — it's what **Fleet** uses to compare machines later.

### "It's a work machine — what's managing it, and is it set up right?"

**Workplace** has four tabs. **Posture** tells you if Windows is activated, whether it's
Entra/domain-joined or a workgroup PC, and whether the clock is drifting (a silent cause of
sign-in failures). **Applied policies** lists every Group Policy / MDM setting actually in
force, each with its registry key and value. **Corporate IT** detects the management and
security agents present (SCCM, Intune, Defender for Endpoint, third-party EDR, VPN, backup) and
how Windows Update is managed. Those three are read-only. The fourth, **Managed baseline**, lets
you set GPO-style policies on a *standalone* PC — each one opt-in, reversible, and showing the
exact key it writes.

### "More than one machine."

**Fleet** lines up exported report JSONs side by side to spot drift, and pulls **remote
snapshots over WinRM** using credentials you type (passed through for that one call, never
written to disk).

## 5. Make it yours

Click the **appearance** button in the title bar to switch themes live — **Graphite** (the flat
dark default), **Frosted Glass** (a smoked-glass skin over a gradient you can recolour), or
**Chevron** (warm amber, squared). Your choice sticks. You can also boot straight into one with
`--theme frost` on the command line.

## 6. Keeping Benchly current

Click the **version number** in the corner (or Ctrl + K → "Check for Benchly updates"). When
there's a newer build, Benchly downloads it, **verifies it against the release's published
SHA-256**, swaps itself in place and relaunches — with a progress bar the whole way. Same single
click whether you're portable or installed; an install under `Program Files` just adds one UAC
prompt. Nothing downloads or changes unless you click.

## 7. The promise underneath all of it

Benchly is built to run on machines you don't own — a client's PC, a relative's laptop — so two
rules run right through it:

- **Every change is spelled out before it happens.** A repair tool names the paths and services
  it'll touch; a tweak shows the exact registry key it writes; a destructive action lists what
  it'll remove *before* you confirm.
- **Nothing leaves the machine quietly.** By default nothing leaves at all. The handful of
  network features (VirusTotal sends a *hash*, never your file; a domain lookup sends the domain
  name) are each named where you use them.

The honest, line-by-line version is in [privacy-and-safety.md](privacy-and-safety.md) — worth a
skim before you press anything destructive.

## Where to next

- **[features.md](features.md)** — the full page-by-page tour, every tool and what it reads.
- **[faq.md](faq.md)** — the quick "is it safe / why admin / does it work offline" answers.
- **[privacy-and-safety.md](privacy-and-safety.md)** — exactly what changes and what leaves.
- **[CHANGELOG.md](../CHANGELOG.md)** — what landed in each release.
