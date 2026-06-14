# Privacy & safety

Benchly is meant to be run on machines you don't own — a client's PC, a friend's laptop,
the reception desk. That only works if you can answer two questions without hand-waving:
**what does it change, and what leaves the machine?** This page answers both, plainly.

The short version: Benchly has no analytics, no crash reporting to us, no account, and no
background service. It does nothing on its own — every action is something you clicked.

---

## What leaves the machine

By default, **nothing**. Benchly reads the local machine and renders it. The only time
data goes out is when *you* use a feature that is, by its nature, a network lookup — and
in every case it's the minimum needed and named up front.

| Feature | What goes out | What does **not** |
|---|---|---|
| **VirusTotal** (file check, autoruns, domains) | The **SHA-256 hash** of the file, or the domain name | The file itself is **never uploaded**. It's hashed locally; only the hash travels. |
| **Domain & website lookup** | The **domain name** (to rdap.org and, if you've added a key, VirusTotal) and a normal **TLS handshake** to the host | Nothing about your browsing, history, or other domains. |
| **URL / redirect unmasker** | HTTP requests to the URL and each redirect it points to | No page scripts run. Benchly resolves links; it does not render or execute them. |
| **Public IP** | A request to a public IP-echo service | — |
| **Speed test** | Transfer to/from speed.cloudflare.com | — |
| **Fleet remote snapshot** | A WinRM connection to the host **you specify**, with credentials **you type** | The credentials are passed through the environment for that one call and **never written to disk**. |
| **Check for updates** | A request to the GitHub Releases API for the configured repo | Only the version tag is read. It's a read-only check; it downloads nothing on its own. |

A VirusTotal API key, if you add one, is stored **encrypted at rest** with Windows DPAPI
(bound to your user profile) — never in plaintext.

There is no telemetry. Benchly does not report usage, errors, or anything else back to its
author.

## What it changes — and how you always know

Most of Benchly is read-only. The parts that *do* change Windows follow one rule: **the
change is documented in the interface before you make it.**

- **Repair tools** (Toolbox) show the exact paths and services each one touches before you
  run it — e.g. "deletes `C:\Windows\SoftwareDistribution`, then restarts wuauserv & bits."
- **Tweaks** (Cleanup) show the precise registry key, value and hive each toggle writes,
  and every tweak is **reversible** — flipping it off restores the Windows default.
- **Destructive actions** — junk cleanup, debloat, printer-queue purge, file deletion —
  list the files or packages they'll affect in the confirmation dialog. File deletions go
  to the **Recycle Bin** by default, so they're undoable.
- **Cleanup is junction-safe.** It refuses to follow reparse points / directory junctions,
  so it can't wander out of a temp folder and delete the target of a symlink.

If a button changes the system and *doesn't* tell you where, that's a bug — report it.

## Why it asks for administrator rights

Benchly runs fine as a standard user; it just can't see or do everything. Elevation
unlocks the things Windows gates behind admin:

- **Read-only but privileged:** SMART drive wear and power-on hours, BitLocker status, TPM
  and Secure Boot detail, the complete listening-port → process map, machine-wide
  certificate stores.
- **Changes:** the repair tools, machine-scope tweaks (HKLM), restore-point creation, and
  app updates that install machine-wide.

Anything that needs elevation says so, and is disabled until you elevate. Use **Run as
admin** in the title bar — Benchly relaunches elevated and returns you to the same page.
Nothing silently escalates.

## Where your data lives

- **Settings** (including the encrypted VirusTotal key) and the **configuration baseline**
  live in `%APPDATA%\Benchly`.
- **Exported reports** go wherever you save them.
- The **portable exe** keeps nothing beside itself; it uses `%APPDATA%` like the installed
  version. Delete that folder and Benchly forgets everything.

## A short, honest list of caveats

- **The tweaks are real registry changes.** They're reversible and documented, but "faster
  shutdown" really does shorten how long Windows waits for a hung app — read the help text.
- **Editing the page file or disabling hibernation** affects crash dumps and Fast Startup.
  Benchly flags the higher-risk ones; don't bulk-toggle without reading.
- **The email and URL tools are triage aids, not verdicts.** They surface signals. A
  "looks fine" result on a URL still means *open it carefully* — and merely requesting a
  link can tip off the sender or burn a one-time link. Benchly warns you of this in place.
- **No magic.** Benchly won't remove malware for you; it shows you where to look (unsigned
  autoruns, rogue roots, suspicious listeners) and gives you the tools to act.
