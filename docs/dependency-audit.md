# Dependency & security audit

Notes to myself on keeping Benchly's Python dependencies clean — no known CVEs, and not so
far behind that an update becomes a rewrite. Benchly ships as an exe that runs on other
people's machines, so a vulnerability in a bundled library isn't abstract: it travels in the
binary. This is the routine that keeps that honest.

## What Benchly actually depends on

Deliberately small. Pinned in [`requirements.txt`](../requirements.txt):

| Package | Why it's here | Surface that matters |
|---|---|---|
| `pywebview` | The app shell (WebView2 window) | Renders the local UI; handles the JS↔Python bridge |
| `psutil` | Live telemetry — CPU, RAM, disk, net, processes | Reads local system state |
| `pillow` | Icon generation / image handling | **Image parsing** — historically the most CVE-prone of the set |
| `pyinstaller` | Builds the portable exe (build-time only) | Not shipped *in* the app, but a poisoned build chain still matters |
| `pip-audit` | The audit tool itself (dev only) | — |

The frontend has no dependencies at all — `ui/` is vanilla HTML/CSS/JS with no CDN and no
build step, so there's no npm tree to audit. This is a Python-only concern.

## Running an audit by hand

From the repo root, in the venv:

```powershell
# Known-vulnerability scan (PyPI advisory DB + OSV)
.venv\Scripts\python -m pip_audit

# What's behind the latest release
.venv\Scripts\python -m pip list --outdated

# And confirm the app still imports after any bump
.venv\Scripts\python -c "import app"
```

`pip-audit` exits non-zero when it finds something, so it slots into CI or a hook cleanly if
that's ever wanted.

## Judging a finding

Not every CVE that names a package is a real problem *for Benchly* — it depends on whether we
touch the vulnerable code path:

- A **Pillow** image-parsing flaw is relevant — Benchly decodes images for the icon.
- A flaw in a **server framework** path of some transitive dep usually isn't — Benchly runs no
  server (the UI is loaded from local files, not served).
- A **build-time** issue in PyInstaller affects whoever builds the release, not end users — but
  it's still worth fixing before the next build.

So the verdict is "does this affect how *we* use it," not just "is there a CVE." When in doubt,
treat it as relevant and bump.

## The automatic check

A scheduled audit runs **every 3 days**: it pulls latest, refreshes the venv from
`requirements.txt`, runs the two commands above, judges the findings, and confirms `import app`
still works. When it finds a real, relevant vulnerability or a worthwhile update it opens a
**GitHub issue** (label [`dependencies`](https://github.com/SteveWillSay/benchly/labels/dependencies))
with the affected/fixed versions and the exact `requirements.txt` change to make. When
everything's clean it stays quiet — no noise.

It only ever *recommends*; it never edits `requirements.txt` or pushes on its own. Bumping a
pin is a human decision, because a "safe" minor bump still wants the `import app` smoke test and
ideally a real launch before it ships in a build.

> The automation currently runs locally (a Claude Code scheduled task on the dev machine), so
> it only fires while that's running. The audit *itself* — the commands above — is fully
> portable and is the part that matters; the scheduler is just what pokes it on a timer.

## Tracking findings

Audit findings live as GitHub issues under the **`dependencies`** label, using the
*Dependency / CVE audit finding* issue template. One issue per finding (or per audit batch when
several land together); close it when the pin is bumped and shipped. That gives a paper trail of
"what was vulnerable, when, and what we did" without it getting lost in a changelog.
