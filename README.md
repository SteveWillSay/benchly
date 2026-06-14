<div align="center">

<img src="assets/icon.png" width="96" alt="Benchly">

# Benchly

**Put any PC on the bench.**

A single-window diagnostics, triage and repair bench for Windows —
the one tool that replaces the USB stick full of half-trusted freeware
you've been carrying around since 2014.

<br>

<img src="assets/screens/dashboard.png" width="820" alt="Benchly dashboard — live vitals, health score and top processes">

</div>

---

One portable executable. No installer required, no account, nothing phoning home.
It opens in about a second and shows you the whole machine: live vitals, the deep
hardware inventory, disk health, the network, what's autostarting, what's listening,
what's wrong, and how to fix it — in a UI that doesn't look like it was built in 2009.

The thing that makes Benchly different from a launcher full of separate utilities
isn't that it bundles them. It's that **every action that touches Windows tells you
exactly what it changes and where**, and **anything that leaves the machine is named
out loud**. You can hand it to a client's PC and know precisely what it did.

## Quick start

Grab the latest build from the [**Releases**](../../releases/latest) page:

| You want… | Download | Notes |
|---|---|---|
| **The no-fuss option** | `Benchly-x.y.z-portable.exe` | One file. Run it from a desktop, a network share, or a USB stick. Nothing is installed. |
| **A proper install** | `Benchly-Setup-x.y.z.exe` | Start-menu entry, optional desktop shortcut, clean uninstaller. |

Double-click and you're in. Some checks — SMART drive wear, BitLocker, TPM, Secure
Boot, machine-wide tweaks — need elevation; hit **Run as admin** in the title bar and
Benchly relaunches elevated and drops you back on the same page.

> **Windows 10 or 11**, 64-bit. Benchly rides on the WebView2 runtime, which ships
> with Windows 11 and every current Windows 10. On a stripped LTSC image without it,
> the app will point you at the one-time Microsoft download.

## A quick tour

Benchly is organised as pages down the left rail. Press a number key to jump straight
to one, or hit **Ctrl + K** for a command palette over every page and action.

**See the machine.** The **Dashboard** is your triage glance — live CPU / RAM / disk-I/O
/ network graphs that actually update every second, a per-core grid, a health-score
ring, and the noisiest processes. **System** is the full inventory down to each RAM
module's part number and the monitor's EDID. **Storage** reads real SMART health,
temperature and wear, then lets you drill into what's eating the disk. **Processes**
is a live, sortable, end-task-on-hover table.

**Work the network — and the web.** Beyond adapters, Wi-Fi and the usual
ping / traceroute / DNS / port tools, Benchly can **look up any domain** (registration
age, TLS certificate, hosting, reputation — to judge a site before you trust it),
**unmask a shortened URL** by following every redirect without opening it, and
**analyze nearby Wi-Fi** for signal and channel congestion.

**Judge what you can trust.** **Security** shows your real antivirus (it reads Security
Center, so third-party AVs aren't mistaken for "off"), maps the full **autostart
persistence** surface, audits the **trusted root certificates** for interception or
adware roots, lists every **listening port** with the signed/unsigned process behind
it, and parses **raw email headers** to catch phishing — all of it with a VirusTotal
check that only ever sends a hash.

**Fix it and tidy it.** The **Toolbox** streams the heavy repair tools (SFC, DISM,
chkdsk, winsock, Windows Update reset) live, snapshots a configuration **baseline** to
diff against later, and captures a 30-second **"why is it slow right now?"** snapshot.
**Fix-It** walks guided runbooks for the everyday complaints. **Cleanup** clears junk,
finds large and duplicate files, debloats preinstalled apps, and offers a shelf of
documented, reversible **Windows tweaks**. **Software** can even update your installed
apps through winget.

**Report and scale.** One click exports a clean, client-ready **HTML + PDF report**
(generated in the background, with a machine-readable JSON twin). **Fleet** compares
those reports across machines and pulls remote snapshots over WinRM.

The full, page-by-page reference lives in **[docs/features.md](docs/features.md)**.

<table>
<tr>
<td width="50%"><img src="assets/screens/domain-lookup.png" alt="Domain & website lookup with a trust verdict"><br><sub><b>Domain & website lookup</b> — a plain-English trust verdict for any site, before you trust it.</sub></td>
<td width="50%"><img src="assets/screens/email-headers.png" alt="Email header phishing analysis"><br><sub><b>Email header analyzer</b> — paste raw headers; every spoofing tell, lit up. Parsed locally.</sub></td>
</tr>
<tr>
<td width="50%"><img src="assets/screens/security-certs.png" alt="Trusted root certificate audit"><br><sub><b>Root certificate audit</b> — interception and adware roots, surfaced and explained.</sub></td>
<td width="50%"><img src="assets/screens/listeners.png" alt="Listening ports mapped to signed processes"><br><sub><b>Listening ports</b> — every open port, the process behind it, and whether it's signed.</sub></td>
</tr>
<tr>
<td width="50%"><img src="assets/screens/tweaks.png" alt="Reversible Windows tweaks, each showing the registry key it writes"><br><sub><b>Tweaks</b> — reversible, and each one shows the exact registry key it writes.</sub></td>
<td width="50%"><img src="assets/screens/dashboard-icloud.png" alt="The iCloud glass theme"><br><sub><b>iCloud theme</b> — the same app, in frosted glass. Switch live from the title bar.</sub></td>
</tr>
</table>

<details>
<summary><b>More screenshots</b> — system, storage, health, events, processes, app updates, toolbox</summary>

<table>
<tr>
<td width="50%"><img src="assets/screens/system.png" alt="System inventory"><br><sub><b>System</b> — the deep inventory, down to each RAM module's part number.</sub></td>
<td width="50%"><img src="assets/screens/storage.png" alt="Storage and SMART health"><br><sub><b>Storage</b> — real SMART health, temperature and wear, with a space analyzer.</sub></td>
</tr>
<tr>
<td width="50%"><img src="assets/screens/health.png" alt="Health audit score and weighted checks"><br><sub><b>Health audit</b> — 14 weighted checks → a score, each failure with a one-click fix.</sub></td>
<td width="50%"><img src="assets/screens/events.png" alt="Event log triage summary"><br><sub><b>Event log</b> — events grouped and explained in plain English, not Event IDs.</sub></td>
</tr>
<tr>
<td width="50%"><img src="assets/screens/processes.png" alt="Live process table"><br><sub><b>Processes</b> — a live, sortable table; click a row for a Process-Explorer-style drawer.</sub></td>
<td width="50%"><img src="assets/screens/app-updates.png" alt="App updates via winget"><br><sub><b>App updates</b> — newer versions of your installed apps, updated through winget.</sub></td>
</tr>
<tr>
<td width="50%"><img src="assets/screens/toolbox.png" alt="Toolbox repair tools"><br><sub><b>Toolbox</b> — streamed repair tools, a config baseline, and a perf snapshot.</sub></td>
<td width="50%"></td>
</tr>
</table>

</details>

## The part most tools skip: transparency

Benchly is built for a context where trust matters — you're often working on someone
else's machine. So two promises are wired through the whole app:

- **Every change is documented in place.** A repair tool tells you the exact paths and
  services it touches. A tweak shows the precise registry key it writes. A destructive
  action spells out the files it will remove before you confirm.
- **Nothing leaves the machine quietly.** VirusTotal checks send a **SHA-256 hash, never
  the file**. A domain lookup sends the **domain name** to public registries and a TLS
  handshake to the host — nothing about your browsing. Remote snapshots use credentials
  passed through the environment **once**, never written to disk. The email and URL tools
  parse and resolve; they never execute anything.

The honest, line-by-line version is in **[docs/privacy-and-safety.md](docs/privacy-and-safety.md)** —
worth a read before you run anything destructive.

## Power-user notes

| Key | Does |
|---|---|
| **Ctrl + K** | Command palette — every page and action, fuzzy-searchable |
| **1 – 9** | Jump to a page; **0** → Toolbox |
| **/** | Focus the current page's filter · **Esc** clears it |
| `--page <name>` | Launch straight onto a page |
| `--theme icloud` | Launch in the glass theme |

Values you'd otherwise hand-type — serials, MACs, IP addresses, hashes — are
click-to-copy throughout. There are two looks: **Graphite** (the default flat dark) and
**iCloud** (frosted glass with a customizable gradient), switchable live from the title
bar. Click the version number any time for the in-app changelog.

## Build from source

```powershell
python -m venv .venv
.venv\Scripts\pip install pywebview psutil pyinstaller pillow
.venv\Scripts\python app.py            # run it straight from source

.\build_portable.ps1                   # → dist\Benchly.exe
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" installer.iss   # → dist_installer\
```

The full build-and-release runbook — versioning, tagging, publishing a GitHub release —
is in **[docs/building.md](docs/building.md)**.

## How it's built

- **Shell** — a [pywebview](https://pywebview.flowrl.com/) window on Windows' WebView2
  runtime. Native window, web front-end, no browser bundled.
- **Backend** (`backend/`) — Python. `psutil` for the fast one-second telemetry; batched
  PowerShell / CIM queries for the deep inventory (one round-trip per domain, JSON back
  over stdout); direct registry reads for software and startup. Long jobs stream to the
  UI through a small background-job store. Everything degrades gracefully without admin
  rights instead of erroring out.
- **Frontend** (`ui/`) — hand-written HTML, CSS and JavaScript. No framework, no CDN, no
  build step — it runs fully offline. Canvas sparklines, a strict content-security-policy,
  and a dark theme tuned for long sessions at the bench.

A solo project, so the code is closed-source and the releases are for the maintainer's
own bench use — but the architecture notes above are the honest shape of it.

## Questions

Common ones — "is it safe to run on a client's PC?", "why does it need admin?", "does it
work offline?", "where's my data stored?" — are answered in **[docs/faq.md](docs/faq.md)**.
Per-release history is in **[CHANGELOG.md](CHANGELOG.md)**.
