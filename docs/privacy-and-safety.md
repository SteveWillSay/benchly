# Privacy & safety

Benchly is meant to run on machines you don't own — a client's PC, a mate's laptop, the
reception desk. That only works if you can answer two questions without any hand-waving:
**what does it change, and what leaves the machine?** So here are both, straight.

The short version: there's no analytics, no crash reporting back to me, no account, and no
background service. Benchly doesn't do anything on its own — everything that happens is
something you clicked.

---

## What leaves the machine

By default? Nothing. Benchly reads the local machine and shows it to you. The only time
anything goes out is when *you* use a feature that's inherently a network lookup — and even
then it's the bare minimum, and it's named up front.

| Feature | What goes out | What stays put |
|---|---|---|
| **VirusTotal** (files, autoruns, domains) | The **SHA-256 hash** of the file, or the domain name | The file itself is **never uploaded**. It's hashed locally; only the hash travels. |
| **Domain & website lookup** | The **domain name** (to rdap.org, and VirusTotal if you've added a key) and a normal **TLS handshake** with the host | Nothing about your browsing, your history, or any other domain. |
| **URL / redirect unmasker** | HTTP requests to the URL and wherever it redirects | No page scripts run. It resolves links — it doesn't render or execute them. |
| **Public IP** | A request to a public IP-echo service | — |
| **Speed test** | Some transfer to and from speed.cloudflare.com | — |
| **Fleet remote snapshot** | A WinRM connection to the host **you name**, using credentials **you type** | Those credentials are passed through the environment for that one call and **never written to disk**. |
| **Check for updates** | A request to the GitHub Releases API for the configured repo | Just the version tag is read. It's read-only — it downloads nothing on its own. |

If you add a VirusTotal API key, it's stored **encrypted at rest** with Windows DPAPI (tied
to your user profile), never as plaintext.

And there's no telemetry. Benchly doesn't report usage, errors, or anything else back to me.

## What it changes — and how you'll always know

Most of Benchly is read-only. The parts that *do* change Windows follow one rule: **you see
the change spelled out before you make it.**

- **Repair tools** (Toolbox) tell you the exact paths and services each one touches before it
  runs — e.g. "deletes `C:\Windows\SoftwareDistribution`, then restarts wuauserv & bits."
- **Tweaks** (Cleanup) show you the precise registry key, value and hive each toggle writes,
  and every tweak is **reversible** — flip it back off and you're at the Windows default.
- **Destructive actions** — junk cleanup, debloat, printer-queue purge, deleting files — list
  exactly what they'll affect in the confirmation. File deletions go to the **Recycle Bin** by
  default, so you can walk them back.
- **Cleanup won't wander.** It refuses to follow reparse points and directory junctions, so it
  can't slip out of a temp folder and delete whatever a symlink was pointing at.

If a button changes something and *doesn't* tell you where — that's a bug. Tell me.

## Why it asks for admin

Benchly runs perfectly well as a standard user; it just can't see or do *everything*.
Elevation unlocks the things Windows keeps behind admin:

- **Read-only, but privileged:** SMART drive wear and power-on hours, BitLocker status, TPM
  and Secure Boot detail, the complete listening-port → process map, the machine-wide
  certificate stores.
- **Actual changes:** the repair tools, machine-scope tweaks (HKLM), creating a restore point,
  and app updates that install machine-wide.

Anything that needs elevation says so, and stays disabled until you give it. Use **Run as
admin** in the title bar — Benchly relaunches elevated and pops you back on the same page.
Nothing ever escalates behind your back.

## Where your stuff lives

- **Settings** (including that encrypted VirusTotal key) and the **configuration baseline**
  sit in `%APPDATA%\Benchly`.
- **Exported reports** go wherever you save them.
- The **portable exe** keeps nothing next to itself — it uses `%APPDATA%` just like the
  installed version. Delete that folder and Benchly forgets everything.

## A few honest caveats

- **The tweaks are real registry edits.** Reversible and documented, yes, but "faster
  shutdown" genuinely does shorten how long Windows waits for a frozen app — read the help
  text first.
- **Touching the page file or hibernation** affects crash dumps and Fast Startup. Benchly
  flags the riskier ones; don't bulk-toggle without reading.
- **The email and URL tools are triage aids, not verdicts.** They surface signals. A
  "looks fine" on a URL still means *open it carefully* — and just requesting a link can tip
  off the sender or burn a one-time link. Benchly warns you about that right where you do it.
- **No magic.** Benchly won't remove malware for you. It shows you where to look — unsigned
  autoruns, rogue roots, suspicious listeners — and hands you the tools to deal with it.
