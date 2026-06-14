# Benchly v2.x build plan — Bundles A–D

Working spec for the next four releases, sequenced. Conventions to follow throughout:
backend module per area; batched PowerShell/CIM via `ps_json()` (wrap multi-statement in
`& { }`); long ops via `JobStore`; every `Api` method auto-instrumented; UI = vanilla
HTML/CSS/JS following existing tab/card patterns; **read-first, document what+where,
reversible, disclose egress, degrade without admin**. Each feature lists: module · key
Windows mechanism · bridge · UI placement · risk · effort.

Sequencing:
- **v2.0** — Bundle A (Everyday Fixes & Gremlins) **+ the two shared engines**
- **v2.1** — Bundle B (Security & IR v2)
- **v2.2** — Bundle C (Family & Helper)
- **v2.3** — Bundle D (Home Lab & Power User)
- **Later/halo** — deep-trace DPC attribution, coil-whine listener, timer-resolution drain

---

## Shared foundations (build first, in v2.0)

These are force-multipliers — several later features depend on them.

### `backend/history.py` — time-series store
- Append-only JSONL per series at `%APPDATA%\Benchly\history\<series>.jsonl`
  (`smart_<serial>`, `mem_<pid>`, `thermal`, `devices`, …). Each line: `{"t": iso, ...}`.
- API: `append(series, sample)`, `read(series, since=None, limit=N)`, `delta(series, attr)`,
  `rotate(series, max_lines)`. Size-cap + rotate to avoid unbounded growth.
- Consumed by: SMART death-predictor (D4), memory-leak finder (halo), thermal timeline (D3),
  "what changed?" device/driver diff (A4).

### `backend/capture.py` — rolling ring-buffer + arm-and-snapshot
- In-process `collections.deque(maxlen=~300)` of vitals samples (CPU/mem/disk/net/top procs),
  fed by a small 1 s sampler thread (reuse the diag watchdog cadence; pause when idle).
- `mark_event()` → freezes the ±60 s window and pulls correlated Event Log entries
  (System/Application/Kernel-Power/Disk/Display-4101/WHEA) into one report.
- Foundation for: freeze correlator (A5b), and later the WPR-trace "arm and capture" (halo DPC).

---

## Bundle A — v2.0 "Everyday Fixes & Gremlins"

### A1. Power / Sleep / Wake doctor — `backend/power.py`
- **Mechanism:** `powercfg /requests` (live sleep blockers → process/driver, by SYSTEM/
  DISPLAY/AWAYMODE/EXECUTION); `powercfg /lastwake` + `/waketimers` (armed timers — flag
  `UpdateOrchestrator`); `powercfg /devicequery wake_armed`; `powercfg /a` (S0 modern-standby
  vs S3); `powercfg /sleepstudy /output <tmp>.html` → parse embedded data for standby drain +
  top offenders; wake history via `Get-WinEvent -LogName System` Kernel-Power **Event ID 1**
  (wake source) + Power-Troubleshooter.
- **Actions (reversible, documented):** disarm a task's "wake the computer" (`Set-ScheduledTask`
  / `schtasks /change`); `powercfg /devicedisablewake "<name>"`; disable USB selective suspend
  per device.
- **Bridge:** `power_overview`, `power_wake_history`, `set_wake_device(name, on)`, `disarm_wake_task(path)`.
- **UI:** new **"Power & Sleep"** card group — best as a tab on **System**, or a Fix-It runbook
  ("won't sleep / wakes by itself / dies in the bag"). Plain-English verdicts.
- **Risk:** low (read-first; toggles reversible). Some detail needs admin → degrade.
- **Effort:** Easy–Medium (all in-box; sleepstudy HTML parse is the fiddly bit).

### A2. Printer "wake up" doctor — extend `backend/devices.py` (printer triage exists)
- **Mechanism:** stop spooler → count+name+**back up** stuck jobs → clear
  `%SystemRoot%\System32\spool\PRINTERS\*` → start; `Get-PrinterDriver`/`Get-PrinterPort`
  (flag duplicate/conflicting drivers, orphaned ports, v3/v4 mismatch); detect "Use Printer
  Offline" flag and clear it; re-resolve the printer's current IP and compare to the port
  (DHCP-changed-address case) → offer to repoint port or suggest a DHCP reservation; test page.
- **Bridge:** `printer_doctor(name)`, `printer_fix(name, actions[])`, `printer_testpage(name)`.
- **UI:** enhance **Devices → printers**, plus a one-button **"Wake up my printer"** in Fix-It.
- **Risk:** low (jobs backed up before purge; documented).
- **Effort:** Easy–Medium.

### A3. Cache & shell repair — `backend/shellrepair.py`
- **Mechanism (each an individual, documented toggle):** icon cache (`ie4uinit.exe -show`, then
  delete `%LocalAppData%\IconCache.db` + `…\Explorer\iconcache_*`); thumbnail cache
  (`…\Explorer\thumbcache_*.db`); font cache (stop `FontCache` svc → delete `FNTCACHE.DAT` +
  `…\ServiceProfiles\LocalService\…\FontCache\*` → start); Store cache (`wsreset.exe`); search
  index rebuild (`SearchIndexer` reset); DNS (`ipconfig /flushdns` — already have). Single
  Explorer restart at the end.
- **Bridge:** `list_cache_repairs`, `run_cache_repair(key)`.
- **UI:** **Cleanup → new "Repair" tab** (or Toolbox cards), each with "what this fixes / you
  lose nothing permanent."
- **Risk:** low (caches regenerate; no user data). Warn that Explorer restarts.
- **Effort:** Easy.

### A4. "What changed?" detective — extend `backend/baseline.py` + `history.py`
- **Mechanism:** baseline already snapshots software/services/startup. Add watched state:
  display language/region, default-app associations, default browser, taskbar position, device
  instance IDs + driver versions/dates. Diff in plain English ("Display language → Spanish";
  "Realtek audio driver 6.0.9388 → 6.0.9415, 2 AM via Windows Update"). Timestamp device/driver
  changes from `Kernel-PnP`/`Setup` logs. One-click "put it back" where reversible.
- **Bridge:** `whats_changed(since=baseline|date)`, `revert_change(id)`.
- **UI:** friendly **"What's different since it was working?"** view in Toolbox (beside baseline
  compare); encourage taking a baseline "while healthy."
- **Risk:** low (read; undo gated + confirmed).
- **Effort:** Easy–Medium.

### A5. Gremlin culprit finders — `backend/gremlins.py`
- **A5a Disk-100%/CPU idle culprit:** `Get-Counter \LogicalDisk(*)\% Idle Time`,
  `\Avg. Disk Queue Length`, per-process `\Process(*)\IO Data Bytes/sec` + psutil `io_counters`
  deltas; name the usual suspects (SysMain, SearchIndexer, MsMpEng, MoUsoCoreWorker,
  CompatTelRunner) and cross-ref SMART (high active-time + reallocated sectors = dying disk).
- **A5b USB disconnect tracker:** `Get-WinEvent` `Microsoft-Windows-Kernel-PnP` + USB
  operational logs (surprise-removal/arrival), tally per device, read selective-suspend state →
  "Logitech receiver dropped 23× today; Selective Suspend is ON — here's where to turn it off."
- **A5c "Mark the freeze" correlator (uses `capture.py`):** big button / global hotkey → pull
  ±60 s across logs + the ring-buffer vitals into one ranked report.
- **Bridge:** `disk_culprit_snapshot`, `usb_drop_history`, `mark_freeze`.
- **UI:** new **"Gremlins"** card cluster in Toolbox (or a small new page).
- **Risk:** low (read-only).
- **Effort:** Easy–Medium (A5c needs the ring buffer).

**v2.0 also delivers** the in-box half of the **DPC-latency hunter (Tier A)** via Get-Counter
`% DPC Time`/`% Interrupt Time`/`DPCs Queued/sec` — flag a hot core; defer per-driver WPR
attribution (Tier B) to the halo tier.

---

## Bundle B — v2.1 "Security & IR v2"

### B1. Defender exclusions & tamper audit — `backend/defender.py`
`Get-MpPreference` (Exclusion{Path,Extension,Process,IpAddress}) + registry mirror
`HKLM\SOFTWARE\Microsoft\Windows Defender\Exclusions`; flag broad/user-writable/scripting-host/
`*.exe`; cross-ref recently-modified files inside each; show tamper-protection, RTP, signature
age, ASR state. `Remove-MpPreference` (reversible, logs prior value). **Risk:** low FP but some
exclusions are legit (dev/backup) — flag, never auto-remove; don't egress paths (leak usernames).
**Effort:** Easy.

### B2. WMI persistence hunter — `backend/persistence.py`
CIM enumerate `__EventFilter`, `CommandLineEventConsumer`/`ActiveScriptEventConsumer`,
`__FilterToConsumerBinding` across **`root\subscription` + `root\default` + sub-namespaces**
(the common miss). Decode payloads + trigger query to English; Authenticode/VT the target.
**Export MOF before removal.** **Risk:** low FP (SCOM/OEM consumers exist); removal is
destructive → gate behind export + restore point. **Effort:** Medium.

### B3. Task/service persistence deep-map — `backend/persistence.py`
`Get-ScheduledTask` + raw task XML (hidden tasks) + `Win32_Service`; score on user-writable
path, `-enc`/base64, `cmd /c`, recently-created, signer mismatch, runs-as-SYSTEM, unquoted
service path, binary in `%TEMP%`. Authenticode + VT. **Disable (not delete) + XML export.**
**Risk:** medium FP (vendor tasks use odd paths) → rank, don't alarm. **Effort:** Easy–Medium.

### B4. "What ran recently" timeline — `backend/execevidence.py`
Parse Prefetch `*.pf` (run count, last-run times) **[start here — easy, high value]**, then
Amcache.hve (SHA1 + first-seen), then ShimCache/AppCompatCache (hardest). Merge into one
execution timeline; flag `%TEMP%`/`%APPDATA%`/Downloads/deleted-but-executed/unsigned; VT by
hash (Amcache has SHA1); date-window filter. **Risk:** evidence not verdict; reveals user
activity → strictly local, hash-only egress. **Effort:** Medium–Hard (Prefetch alone = Medium).

### B5. Post-scam guided runbook — `backend/runbooks.py` (extend) — *shared with C*
Orchestrate, IR-ordered, elder-readable: detect/kill remote-access tools → new accounts/admin
(`Get-LocalUser` + Security log 4720/4732, 4624 Type 10 RDP, 4625 bursts) → persistence
(autoruns + B2 + B3) → Defender exclusions (B1) → recent execution (B4) → breach/password
(C-tier HIBP) → BitLocker key reminder (C7) → plain-English "what we found / do this next"
report. **Risk:** don't promise "100% clean"; frame as triage + bank/pro steps; flag, don't
auto-delete. **Effort:** Easy–Medium (mostly orchestration).

### B6. CIS-lite scorecard + ASR roller — `backend/hardening.py`
Score curated ~25–40 high-value controls: ASR rules (Office-child, obfuscated-script, USB),
SMBv1 off, LLMNR/NetBIOS off, ScriptBlock logging (4104), NLA, guest disabled, AutoRun off,
macro defaults, PS v2 removed. `Get-MpPreference`/registry/policy reads; reversible one-click
per fix (logs exact key + where); re-score; before/after report. **ASR audit→block roller:**
set rules to audit, surface what *would* block over N days, then promote. **Risk:** real config
edits → audit-first, opt-in per fix, never auto-apply, snapshot/restore-point; some controls
break niche software. **Effort:** Medium.

*Present B3/firewall/LOLBIN-lineage as ranked context, never verdicts (heavy FP).*

---

## Bundle C — v2.2 "Family & Helper"

### C1. "Text my tech person" — `backend/helpercard.py`
Friendly one-pager (top 3 issues in plain English) + technical appendix; share via local
file/QR + 6-char pairing code to pull the JSON report. Reuses report/ticket engines. **Risk:**
report leaves machine → preview-before-send, default local, disclose contents. **Effort:** Medium.

### C2. "Make it normal again" — `backend/display.py`
`QueryDisplayConfig`/CCD API (ctypes) current vs native res/scaling/refresh; set with a **15 s
auto-revert** (Windows-style "keep these changes?"); text-size +/-; detect phantom display
grabbing windows, browser zoom ≠ 100% (advise). **Risk:** low w/ auto-revert. **Effort:** Medium.

### C3. Camera/mic doctor — `backend/avcheck.py`
`HKCU/HKLM …\CapabilityAccessManager\ConsentStore\{webcam,microphone}` per-app permission;
which process holds the camera; default input/output vs plugged-in; mute state; driver presence;
3-second self-test. One-button permission flip. **Risk:** low (privacy toggles documented).
**Effort:** Medium.

### C4. Browser un-hijack — extend `backend/threats.py` (hijack scan exists)
One-click reset: default search/homepage/new-tab across Chrome/Edge/Firefox, malicious
extensions, hijacked `.lnk` shortcut targets (the `chrome.exe http://bad` trick), leftover
enforced policies. Snapshot + before→after + confirm each. **Risk:** medium (multi-browser
config) → back up first. **Effort:** Medium.

### C5. "Quiet mode" — extend `backend/tweaks.py`
One panel to silence: taskbar widgets/news, tips & suggestions, lock-screen ads, "finish setup"
nags, and **revoke browser web-push site permissions** (source of fake "you're infected"
desktop pop-ups). Tally "silenced N sources." Reversible. **Risk:** low (don't disable security
alerts). **Effort:** Easy–Medium.

### C6. Panic photo backup — `backend/rescue.py`
Auto-find Pictures/Documents/Desktop + stray photo folders; size; robocopy-with-verify to
plugged-in external; **SMART-aware** (sequential, low-stress, never *move*, resumable); prioritise
by recency if disk failing; done/failed report. **Risk:** medium (copying off a dying disk) →
read-only source, warn a truly failing disk may need a pro. **Effort:** Medium.

### C7. BitLocker recovery-key reminder — `backend/bitlocker.py`
`Get-BitLockerVolume` / `manage-bde -protectors -get`; escrow status (AAD/MS-account/AD vs
local-only); display/save key; warn before repair ops that can trigger recovery. **Risk:** the
recovery key is the **most sensitive value in the app** — never log/cache/screenshot/transmit;
big disclosure banner. **Effort:** Easy.

### C8. "Is this a scam?" traffic-light — wrap `mailcheck`/`urlcheck`/`vt`
Senior-readable paste box → red/yellow/green + one-line plain reasons; never auto-open links;
phrase as "looks risky / no obvious red flags, still be careful" (no false green). **Risk:**
low–medium. **Effort:** Easy.

---

## Bundle D — v2.3 "Home Lab & Power User"

### D1. Link & Negotiation audit — `backend/links.py`
Unified **negotiated-vs-capable** surface: **PCIe** LnkCap vs LnkSta width/speed (config-space
offsets — needs a small user-space PCI config reader or vendor-tool parse; flag x16→x4, Gen4→
Gen1, explain M.2 lane-sharing); **USB** negotiated vs capable speed (SetupAPI/`Win32_USBController`
+ speed descriptors, topology/shared-controller); **display** current vs native refresh (CCD).
**Risk:** low (read-only). **Effort:** Medium–Hard (PCIe config space is the hard bit).

### D2. LAN throughput + bufferbloat lab — `backend/netperf.py`
Bundle/launch `iperf3`, or **Benchly-to-Benchly** over the existing Fleet/WinRM channel;
bidirectional TCP/UDP MB/s + retransmits + expected-vs-actual for both NIC link speeds;
**bufferbloat grade** = idle latency vs latency-under-load (A–F + added ms). **Risk:** low
(saturation maxes link briefly — warn, time-box). **Effort:** Medium.

### D3. GPU throttle/OC forensics — extend `backend/temps.py` + `history.py`
NVML perf-cap/throttle reasons (thermal/power/voltage/util) + clocks + VRAM + hotspot/junction
temp; correlate Display-4101 TDR + LiveKernelEvent 141; optional **capped** stability soak
(hard temp ceiling + abort). **Risk:** medium (soak heats card) → read-only default, never touch
clocks/voltage. **Effort:** Medium.

### D4. SMART death-predictor — extend `backend/storage.py` + `history.py`
Trend reallocated/pending/uncorrectable sector **deltas** (not absolutes); SSD TBW-used vs
rated; flag drives past their cohort age in a set; pool-level risk score ("Disk 3: pending 0→14
in 30 days — replace before resilver"). **Risk:** low (read-only; local history). **Effort:** Medium.

### D5. WSL/Hyper-V/Docker health — `backend/virt.py`
`wsl --status/--list`, vmmem RAM ceiling vs `.wslconfig` default, bloated `ext4.vhdx` (+optional
non-destructive compact), `Get-VMSwitch` (external vSwitch hijacking the NIC), `docker system df`,
VT-x/AMD-V + nested-virt flags. Degrades if a feature isn't installed. **Risk:** low to read;
vhdx compaction is the only write → optional + reversible. **Effort:** Medium.

---

## Halo tier (future showcase additions)
- **DPC/ISR latency hunter — Tier B:** in-box `wpr.exe` start/stop → parse `xperf -a dpcisr`/
  WPA for per-driver attribution → translate `.sys` to friendly culprit. Admin + large ETL.
- **Coil-whine acoustic listener:** mic (explicit consent) → FFT → correlate tone with load.
- **Timer-resolution drain detector:** `powercfg /energy` parse (names the offending process) +
  `NtQueryTimerResolution` ctypes.
- **Memory-leak-over-hours:** `history.py` per-process Private Bytes/handles/GDI + kernel pool.
- **GPU TDR miner:** folds into D3 (LiveKernelReports mining).

---

## Cross-cutting risk policy (applies to all)
- Read-first; every change shows what+where; reversible (disable/export, not delete); confirm
  destructive actions with the affected list.
- **Present as ranked context, not verdicts** (heavy FP): LOLBIN lineage, task/service/firewall
  heuristics.
- **Privacy / dual-use — explicit consent + disclosure, hash/k-anonymity egress only, never
  display-then-leak:** browser password-store checks, BitLocker recovery key, Prefetch/Amcache/
  USB history, the helper-card share.
- No offensive/evasion tooling anywhere — defensive & cleanup only.
