# FAQ

Quick answers to the things people actually ask. The fuller version of the privacy answers
is over in [privacy-and-safety.md](privacy-and-safety.md).

### Is it safe to run on a client's machine?

That's exactly what it's for. Benchly is read-only until you tell it otherwise, and the
things that *do* change Windows show you what they're touching before you confirm. Nothing
goes anywhere unless you use a feature that's explicitly a network lookup — and those are all
[listed here](privacy-and-safety.md#what-leaves-the-machine). No telemetry, no background
service.

### Do I have to install it?

Nope. The portable `.exe` is a single file — run it off a desktop, a share, or a USB stick
and it leaves nothing behind except its settings in `%APPDATA%\Benchly`. The installer's
there if you'd rather have a Start-menu entry and an uninstaller, but it's optional.

### Why does it want admin rights?

To see the privileged stuff (SMART wear, BitLocker, TPM, the full port→process map) and to
run the repair tools and machine-wide tweaks. It works fine without — those specific bits are
just greyed out until you click **Run as admin** in the title bar. Nothing escalates on its
own.

### Does it work offline?

Totally, for everything local. The whole UI ships inside the exe — no CDN, no framework
downloads. Only the explicit network features (domain lookup, VirusTotal, speed test, update
check) need a connection, and they fail quietly when there isn't one.

### Where do my settings and my VirusTotal key live?

In `%APPDATA%\Benchly`. The VirusTotal key is encrypted at rest with Windows DPAPI (tied to
your user account), never in plaintext. Delete that folder and Benchly forgets the lot.

### Are the Tweaks and Cleanup safe? Can I undo them?

Yes — that's the whole design. Every tweak is a reversible registry change that shows you the
exact key it writes, so flipping it back off restores the Windows default. File cleanup sends
deletions to the Recycle Bin and won't follow directory junctions. Debloat only removes
per-user Store apps you can reinstall, and never touches system packages. The handful of
riskier items (page file, hibernation) are flagged as such.

### How does Benchly update itself — and is that safe?

When a newer release is published, **Check for updates** (click the version number, or
Ctrl + K → "Check for Benchly updates") offers a one-click **Download & install**. Benchly
pulls the new build, **verifies it against the release's published SHA-256** before running
anything, then quits, lets a tiny helper swap the new program file in over the old one, and
relaunches into it — with a progress bar the whole time. It's the same single click whether
you're on the portable exe or an installed copy; an install under `Program Files` adds one
UAC prompt so the helper can write there. Nothing is downloaded or changed unless you click.

### "Check for updates" says there's nothing — but I know there's a newer version.

If the repository's **private**, GitHub's Releases API hands back a "not found" to anonymous
requests, so the in-app check stays quiet. Make the repo public (or point `update_repo` at a
public one) and it springs to life with no other change. There's a bit more on this in
[building.md](building.md#a-few-things-learned-the-hard-way).

### My antivirus shows as "inactive," or there are two AV entries — is that wrong?

Probably not. Benchly reads Windows Security Center, which lists every registered product. A
third-party AV (Bitdefender, ESET…) shows **active** while Windows Defender sits next to it
showing **inactive** — that's Defender correctly standing down, not a problem.

### The Wi-Fi analyzer finds nothing on my desktop.

It needs a wireless adapter, and on Windows 11 it needs **Location** switched on (Microsoft
gates Wi-Fi scan data behind it, because BSSIDs can pin down where you are). Benchly spots
both cases and gives you a one-click jump to the Location setting.

### Why a hash for VirusTotal instead of just uploading the file?

So your files never leave the machine. A SHA-256 is enough to look up something VirusTotal
has already seen, which covers the known-good and the known-bad. If a file's genuinely new to
VT the hash just won't match — and Benchly won't quietly upload it to find out.

### Can I use the Managed Baseline to set policies on a standalone PC?

Yes — that's exactly what the **Workplace → Managed baseline** tab is for: the Windows Update
deferrals, BitLocker startup-PIN policy, telemetry, auto-lock and UAC settings an admin would
normally push via GPO or Intune, set here on an unmanaged machine. Every change shows the exact
registry key, needs admin, and is reversible (**Clear** returns it to the Windows default). If
Benchly sees the machine is *already* centrally managed it warns you first, because real
GPO/MDM would overwrite anything you set locally — so this is meant for standalone PCs without
Intune.

### Can I run it on Windows Server or an older build?

It targets Windows 10 and 11 (64-bit) and needs the WebView2 runtime. It'll *run* on Server
editions that have WebView2, but a few checks assume a desktop SKU. Bare LTSC images without
WebView2 will get prompted to install it once.

### It's closed-source — can I still build it?

The source isn't published, but if you've got it, [building.md](building.md) is the whole
runbook: one `pip install`, one script for the portable exe, one for the installer.
