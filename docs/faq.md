# FAQ

Short answers to the things people actually ask. The fuller version of the privacy
answers lives in [privacy-and-safety.md](privacy-and-safety.md).

### Is it safe to run on a client's machine?

That's exactly what it's built for. Benchly is read-only until you tell it otherwise, and
the actions that *do* change Windows document what they touch before you confirm. Nothing
is sent anywhere unless you use a feature that's explicitly a network lookup (and those are
listed [here](privacy-and-safety.md#what-leaves-the-machine)). There's no telemetry and no
background service.

### Does it need to be installed?

No. The portable `.exe` is a single file — run it from a desktop, a network share, or a
USB stick and it leaves nothing behind except its settings in `%APPDATA%\Benchly`. The
installer is there if you'd rather have a Start-menu entry and an uninstaller.

### Why does it want administrator rights?

To see the privileged stuff (SMART wear, BitLocker, TPM, the full port→process map) and to
run the repair tools and machine-wide tweaks. It works fine without admin — those specific
items are just disabled until you click **Run as admin** in the title bar. Nothing escalates
on its own.

### Does it work offline?

Completely, for everything local. The UI ships inside the exe with no CDN or framework
downloads. Only the explicit network features — domain lookup, VirusTotal, speed test,
update check — need a connection, and they fail gracefully when there isn't one.

### Where are my settings and my VirusTotal key stored?

In `%APPDATA%\Benchly`. The VirusTotal API key is encrypted at rest with Windows DPAPI
(tied to your user account), never stored in plaintext. Delete that folder and Benchly
forgets everything.

### Are the Tweaks and Cleanup safe? Can I undo them?

Yes, by design. Every tweak is a reversible registry change and shows you the exact key it
writes — toggling it off restores the Windows default. File cleanup sends deletions to the
Recycle Bin and refuses to follow directory junctions. Debloat only removes per-user Store
apps you can reinstall, and never touches system packages. The few higher-risk items (page
file, hibernation) are flagged as such.

### "Check for updates" says there's nothing — but I know there's a newer version.

If Benchly's repository is **private**, GitHub's Releases API returns "not found" to
anonymous requests, so the in-app check stays quiet. Make the repo public (or set
`update_repo` to a public one) and it starts working with no other change. See
[building.md](building.md#house-rules-learned-the-hard-way).

### My antivirus shows as "inactive" or there are two AV entries — is that wrong?

Probably not. Benchly reads Windows Security Center, which lists every registered product.
A third-party AV (Bitdefender, ESET…) will show **active** and Windows Defender will show
**inactive** alongside it — that's Defender correctly standing down, not a problem.

### The Wi-Fi analyzer finds nothing on my desktop.

It needs a wireless adapter, and on Windows 11 it needs **Location** enabled (Microsoft
gates Wi-Fi scan data behind it, because BSSIDs can locate you). Benchly detects both cases
and gives you a one-click jump to the Location setting.

### Why a hash for VirusTotal instead of uploading the file?

So your files never leave the machine. A SHA-256 is enough to look up a file VirusTotal has
already seen, which covers known-good and known-bad. If a file is genuinely unknown to VT,
the hash simply won't match — Benchly won't quietly upload it to find out.

### Can I use it on Windows Server / an older build?

It targets Windows 10 and 11 (64-bit) and needs the WebView2 runtime. It'll *run* on
Server editions that have WebView2, but some checks assume a desktop SKU. Bare LTSC images
without WebView2 will be prompted to install it once.

### It's closed-source — can I still build it?

The source isn't published, but if you have it, [building.md](building.md) is the complete
runbook: one `pip install`, one script for the portable exe, one for the installer.
