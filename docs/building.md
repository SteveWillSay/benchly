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
5. **Commit, tag, push:**
   ```powershell
   git add -A
   git commit -m "Benchly v<version> — <headline>"
   git tag -a v<version> -m "Benchly v<version>"
   git push origin master --tags
   ```
6. **Publish the GitHub release** with the binaries attached:
   ```powershell
   gh release create v<version> `
     release\v<version>\Benchly-<version>-portable.exe `
     release\v<version>\Benchly-Setup-<version>.exe `
     --title "Benchly v<version>" --notes-file release\v<version>\RELEASE.md --latest
   ```

The release `.exe` files are **git-ignored** on purpose — binaries belong on the GitHub
release, not in the tree. `SHA256SUMS.txt`, `RELEASE.md` and `CHANGELOG.md` are tracked.

## A few things learned the hard way

- **Never** rewrite a UTF-8 source file with PowerShell `Get-Content` / `-replace` /
  `Set-Content` — it quietly mangles em-dashes and other non-ASCII. Edit those files directly.
- In `backend/ps.py`, multi-statement PowerShell has to be wrapped in `& { … }`, not `( … )`.
  `ps_json()` already handles that for you.
- Don't go stripping CSS rules as "unused" too eagerly — a couple have come back to bite a
  release later.
- The in-app updater reads its release source from the `update_repo` setting, falling back to
  the default baked into `backend/selfupdate.py`. A **private** repo answers the anonymous
  Releases API with a 404, so "Check for updates" stays quiet until the repo's public.
