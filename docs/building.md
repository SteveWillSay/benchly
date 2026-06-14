# Building & releasing

Mostly notes to myself — the exact steps that turn the source into a release I'm happy to
ship. Windows only, and everything below assumes PowerShell from the repo root.

## One-time setup

```powershell
python -m venv .venv
.venv\Scripts\pip install pywebview psutil pyinstaller pillow
```

You'll want [Inno Setup 6](https://jrsoftware.org/isdl.php) for the installer — it lands at
`%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`. The [GitHub CLI](https://cli.github.com/)
(`gh`) is only needed when you're publishing a release.

## Running from source

```powershell
.venv\Scripts\python app.py
```

A few flags that come in handy while you're working on it:

| Flag | What it does |
|---|---|
| `--page <name>` | Open straight onto a page (`dashboard`, `security`, `network`, …) |
| `--theme frost` | Start in the Frosted Glass theme |
| `--turbo` | Run the live loop at 20× — handy for soak-testing the dashboard |

There's a rotating watchdog log at `%APPDATA%\Benchly\benchly.log` with a 30-second
heartbeat, which is the first place to look when you're chasing a hang.

## Building the binaries

```powershell
# Portable single-file exe  →  dist\Benchly.exe
.\build_portable.ps1

# …or the raw PyInstaller line it wraps:
pyinstaller --noconfirm --clean --onefile --windowed --name Benchly `
  --icon assets\icon.ico --version-file version_info.txt `
  --add-data "ui;ui" --add-data "assets\icon.ico;assets" --distpath dist app.py

# Installer  →  dist_installer\Benchly-Setup-<version>.exe
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" installer.iss
```

The frontend has no build step — `ui/` ships as-is and gets bundled in via `--add-data`.

## Cutting a release

1. **Bump the version in all four spots** (they have to agree):
   - `app.py` → `APP_VERSION`
   - `version_info.txt` → `filevers`, `prodvers`, and the `FileVersion` / `ProductVersion`
     strings
   - `installer.iss` → `#define AppVersion`
   - `ui/js/app.js` → a fresh entry at the top of the `CHANGELOG` array (that's the in-app
     "What's new")
2. **Update `CHANGELOG.md`** with the same notes.
3. **Build** both binaries (above) and **actually launch the portable exe** to confirm it
   boots — don't skip this.
4. **Stage the release folder and checksums:**
   ```powershell
   $rel = "release\v<version>"
   New-Item -ItemType Directory -Force $rel | Out-Null
   Copy-Item dist\Benchly.exe "$rel\Benchly-<version>-portable.exe"
   Copy-Item dist_installer\Benchly-Setup-<version>.exe $rel
   Get-ChildItem $rel -File -Exclude SHA256SUMS.txt |
     ForEach-Object { "$((Get-FileHash $_ -Algorithm SHA256).Hash.ToLower())  $($_.Name)" } |
     Out-File "$rel\SHA256SUMS.txt" -Encoding ascii
   ```
5. **Commit, *then* tag, then push** — in that order. The tag has to point at the finished
   release commit, and the repo's tag-protection rule won't let you move or delete a tag
   once it's pushed, so a tag placed on the wrong commit is a mess to unpick.
   ```powershell
   git add -A
   git commit -F _commitmsg.txt    # write the message to a file first — see below
   git tag v<version>
   git push origin master
   git push origin v<version>
   ```
   Write the commit message into a throwaway file and use `git commit -F`. **Don't** pass a
   multi-line message inline with `git commit -m` in PowerShell — `&`, `->` and embedded
   double-quotes get mangled by the shell and the commit fails (or worse, half-succeeds).
6. **Publish the GitHub release** with the binaries **and `SHA256SUMS.txt`** attached —
   the in-app updater verifies downloads against that checksum file, so don't skip it:
   ```powershell
   gh release create v<version> `
     release\v<version>\Benchly-<version>-portable.exe `
     release\v<version>\Benchly-Setup-<version>.exe `
     release\v<version>\SHA256SUMS.txt `
     --title "Benchly v<version>" --notes-file release\v<version>\RELEASE.md --latest
   ```

The release `.exe` files are **git-ignored** on purpose — binaries belong on the GitHub
release, not in the tree. `SHA256SUMS.txt`, `RELEASE.md` and `CHANGELOG.md` are tracked.

## A few things learned the hard way

- **Never** rewrite a UTF-8 source file with PowerShell `Get-Content` / `-replace` /
  `Set-Content` — it quietly mangles em-dashes and other non-ASCII. Edit those files directly.
- **Kill any leftover `dist\Benchly.exe` before rebuilding.** PyInstaller will report "Build
  complete" but silently fail to overwrite `dist\Benchly.exe` if a previous run is still holding
  it — so the new exe keeps the *old* FileVersion. After boot-testing the dist exe, kill its
  whole tree by **PID** (`taskkill /F /T /PID <pid>`), never `/IM Benchly.exe` (that also kills
  any *installed* copy that's running). Then confirm `(Get-Item dist\Benchly.exe).VersionInfo.
  FileVersion` is fresh before you compile the installer (the installer bundles that exe).
- **Sanity-check `ui/js/app.js` before shipping.** There's no Node here, so a quick
  `pip install py_mini_racer` then `ctx.eval('new Function(<source>)')` forces a full V8 parse —
  it catches any syntax error (which would blank the *whole* page, not just the new handler)
  without running the DOM code. Uninstall it after; it's not an app dependency.
- In `backend/ps.py`, multi-statement PowerShell has to be wrapped in `& { … }`, not `( … )`.
  `ps_json()` already handles that for you.
- Don't go stripping CSS rules as "unused" too eagerly — a couple have come back to bite a
  release later.
- The in-app updater reads its release source from the `update_repo` setting, falling back to
  the default baked into `backend/selfupdate.py`. A **private** repo answers the anonymous
  Releases API with a 404, so "Check for updates" stays quiet until the repo's public.
- The updater **always swaps the portable exe in place** now — for both the portable build
  and an installed copy. It downloads the portable asset, quits, and a detached helper waits
  for the lock to clear, moves the new file over the old one, and relaunches. (Earlier
  installed-copy updates handed off to the Inno installer, whose "close the running app" step
  could hang on this onefile/pywebview app — that's fixed as of v2.3.1.) Because the fix lives
  in the *running* version, any change to the update mechanic only takes effect from the next
  update onward — so test a mechanic change by shipping it once, then updating *from* it.
- That helper writes a `.cmd` into `%TEMP%` with `encoding="mbcs"`, so non-ASCII characters in
  a username/path don't corrupt it.
