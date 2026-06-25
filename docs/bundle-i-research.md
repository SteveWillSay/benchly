# Bundle I — research findings

Research backing the next feature bundle. Goal: well-documented, common Windows triage
problems Benchly doesn't yet cover, depth for pages it does, the accessibility work from the
design critique, and honest competitive-parity gaps.

> **On verification.** This came out of the `/deep-research` harness. Its search + fetch
> phases ran fine and pulled **23 sources, overwhelmingly primary** (Microsoft Learn, W3C,
> MDN, MITRE ATT&CK, NN/g, Sysinternals docs). Its automated adversarial-verification phase
> did **not** run — every verifier vote hit a session rate limit and abstained (0-0), which
> the harness records as "refuted." That's a false negative, not a refutation. Each claim
> below has been vetted by hand against its cited primary source and known Windows behaviour.
> Two sources are explicitly lower-confidence and flagged inline (⚠️).

## 1. Net-new diagnostics / fixes

| Fix | What & why | How (safe path) | Risk | Source |
|---|---|---|---|---|
| **Full TCP/IP stack reset** | The "internet works for nothing" reset, beyond the Winsock reset + flush-DNS Benchly already has. Rewrites `Tcpip\Parameters` and `DHCP\Parameters` — equivalent to removing/reinstalling TCP/IP. | `netsh int ip reset [logfile]` (elevated) + reboot; pair with the existing winsock reset / flushdns into one runbook. | Med (reboot) | [MS Learn — reset TCP/IP](https://learn.microsoft.com/en-us/troubleshoot/windows-server/networking/reset-tcp-ip-net-shell) |
| **Temp/corrupt user-profile recovery** | "You've been signed in with a temporary profile." Detection is read-only (ProfileList `.bak` keys); the fix is guided migration to a new account. | Read `HKLM\…\ProfileList` for `.bak`/duplicate SIDs (detect); guide create-new-account + copy `C:\Users\<old>`. Don't auto-edit SIDs. | Detect: low / Fix: guided | [MS Support — corrupted profile](https://support.microsoft.com/en-us/windows/fix-a-corrupted-user-profile-9e32ab2b-fa4d-40da-a78e-d294c1c94145) |
| **Microsoft Store / UWP re-registration** | Broken Start menu / Store / built-in apps — a top consumer fix. | `Get-AppxPackage … \| Add-AppxPackage -Register …Manifest.xml` per package; offer per-app or all. | Med | (Store troubleshooting; verify exact cmdlet set before shipping) |
| **Windows Search index rebuild** | "Search finds nothing / Outlook search broken." | Rebuild via Search settings / `sc stop wsearch` → delete `Windows.edb` → restart; or the documented registry `SetupCompletedSuccessfully=0`. | Med | (MS Search troubleshooting — verify) |
| **Office Click-to-Run repair** | Office apps won't start / crash — Quick vs Online repair. | `OfficeClickToRun.exe`/`OfficeC2RClient.exe` repair invocation. ⚠️ steps from a **forum** source — verify against MS Learn before building. | Med | ⚠️ [MS Q&A (forum)](https://learn.microsoft.com/en-us/answers/questions/5226425/) |
| **WMI repository repair** | "WMI broken" → tools that read CIM (incl. parts of Benchly) fail. | **Read-only check is safe:** `winmgmt /verifyrepository`. Repair/reset (`/salvagerepository`, `/resetrepository`) is **destructive** — gate hard. ⚠️ steps from a source flagged **unreliable**; confirm on MS Learn. | Check: low / Reset: **high** | ⚠️ [MS TechCommunity](https://techcommunity.microsoft.com/t5/ask-the-performance-team/wmi-rebuilding-the-wmi-repository/ba-p/373846) |
| Font/icon cache rebuild, .NET repair, Bluetooth stack reset | Lower-frequency but well-known. | Delete font cache service files / `FNTCACHE.DAT`; .NET repair tool; restart Bluetooth support service. | Low–Med | (secondary; lower priority) |

## 2. Deepen existing pages

- **Authoritative WU / HRESULT error-code translation** (Update Doctor / Event Log). Microsoft
  publishes a **component-organized** WU error reference and the **WUA code table in
  `wuerror.h`** (`0x8024xxxx` = errors, `0x0024xxxx` = success), each with a `WU_E_*` constant
  and plain-English text — a ready-made dataset to replace folklore. Examples: `0x80240034
  WU_E_DOWNLOAD_FAILED`, `0x80240020 WU_E_NO_INTERACTIVE_USER`, `0x80240FFF WU_E_UNEXPECTED`.
  Sources: [WU error reference](https://learn.microsoft.com/en-us/windows/deployment/update/windows-update-error-reference),
  [WUA codes](https://learn.microsoft.com/en-us/windows/win32/wua_sdk/wua-success-and-error-codes-).
- **A general HRESULT/error decoder** (great as a Ctrl+K tool). The HRESULT **facility** field
  identifies the responsible service (`FACILITY_WIN32=7`, `FACILITY_WINDOWS=8`, etc.); a
  `FACILITY_WIN32` HRESULT's low 16 bits decode as a standard Win32 error. This is exactly what
  Microsoft's **Err.exe** does (reads `winerror.h`, `ntstatus.h`, `bugcodes.h`, …). Sources:
  [COM error structure](https://learn.microsoft.com/en-us/windows/win32/com/structure-of-com-error-codes),
  [Error Lookup Tool](https://learn.microsoft.com/en-us/windows/win32/debug/system-error-code-lookup-tool).
- **Event ID 41 (Kernel-Power) parsing** for the Crashes/BSOD tab. Logged on next boot after an
  unclean shutdown; embeds the bug-check code + 4 parameters when a Stop error caused it.
  **Nitty-gritty correctness:** the `BugcheckCode` is stored in **decimal** while Stop-error
  docs use 8-digit **hex** (decimal 159 = `0x0000009f`) — so convert + zero-pad before naming.
  Source: [MS Learn — Event ID 41](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/event-id-41-restart).
- **Autostart/persistence breadth** (Security → Autoruns). Beyond Run/RunOnce/RunOnceEx, also
  scan legacy `RunServices(Once)` and `Policies\Explorer\Run`, and the wider Autoruns classes:
  boot-execute, AppInit DLLs, image hijacks (IFEO), LSA security providers, Winsock providers,
  print-monitor DLLs, WMI event subscriptions, Winlogon, shell extensions, BHOs. Sources:
  [MITRE T1547.001](https://attack.mitre.org/techniques/T1547/001/),
  [Autoruns](https://learn.microsoft.com/en-us/sysinternals/downloads/autoruns).
- **SMART attribute depth** (Storage). Surface the specific predictive attributes by name/ID
  (reallocated-sector 0x05, pending 0xC5/197, uncorrectable 0xC6/198, etc.) rather than a bare
  health flag. ⚠️ source is a tech blog — corroborate IDs before labelling. Source:
  ⚠️ [XDA — SMART attributes](https://www.xda-developers.com/smart-attributes-that-predict-drive-failure/).

## 3. UX / accessibility (folds in the design critique)

- **Contrast — WCAG SC 1.4.3:** normal text needs **≥ 4.5:1**, large text (≥ 18pt, or 14pt
  bold) needs **≥ 3:1**. Benchly's `--text-3` (#62666d) on the dark surfaces falls short for the
  small-caps headers/hints it's used for — lift it or darken surfaces. Source:
  [WCAG 1.4.3](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum).
- **`prefers-reduced-motion`:** maps directly to the native Win10/11 "show animations /
  animation effects" setting, so honouring it respects the user's existing OS choice with no
  custom toggle. Values: `no-preference` / `reduce`. Source:
  [MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion).
- **`aria-label` on icon-only buttons:** an icon-only control's accessible name must come from
  `aria-label`/`aria-labelledby` (it's otherwise computed from text content). Sources:
  [ARIA14](https://www.w3.org/WAI/WCAG21/Techniques/aria/ARIA14),
  [APG button pattern](https://www.w3.org/WAI/ARIA/apg/patterns/button/).
- **Auto-run safe read-only checks on page load:** Nielsen's #1 heuristic — *visibility of
  system status*. Pages that sit blank behind manual "Check" buttons violate it; auto-run the
  cheap/safe checks with a loading state. Source:
  [NN/g](https://www.nngroup.com/articles/visibility-system-status/).

## 4. Competitive parity (genuine gaps)

- **Process Explorer-style handle / DLL search** — the "*which process has this file/folder
  locked?*" answer. The single highest-value parity gap for a bench tool. Process Explorer lists
  per-process open handles (files, keys, objects) and loaded DLLs, with search. Benchly has a
  process table but no handle inspection. Source:
  [Process Explorer](https://learn.microsoft.com/en-us/sysinternals/downloads/process-explorer).
- **TCPView-style live connections** — Benchly already shows active connections (netstat-style);
  parity gap is *live-updating* per-connection + owning process. Partial; low effort to close.
  Source: [TCPView](https://learn.microsoft.com/en-us/sysinternals/downloads/tcpview).
- **BlueScreenView / WhoCrashed-style minidump analysis** — Benchly groups BSODs from event
  data; the next level is parsing `C:\Windows\Minidump\*.dmp` to name the faulting driver.
  Higher effort (dump parsing); high payoff.
- **Out of scope (deliberate):** Snappy Driver Installer-style third-party driver packs —
  downloading/applying driver packages is risky and off-mission for a read-first triage tool.
  Note it as a non-goal. Source: ⚠️ [blog](https://www.glenn.delahoy.com/snappy-driver-installer-origin/).

See [bundle-i-plan.md](bundle-i-plan.md) for the prioritized build proposal drawn from this.
