# Benchly v2.4–v2.7 build plan — Bundles E–H

Working spec for the next four releases, sequenced. Same conventions as the v2 plan:
backend module per area; batched PowerShell/CIM via `ps_json()` (wrap multi-statement in
`& { }`); long/streamed ops via `JobStore`; every `Api` method auto-instrumented; UI =
vanilla HTML/CSS/JS following existing tab/card patterns; **read-first, document what+where,
reversible, disclose egress, degrade without admin**. Each feature lists: module · key
Windows mechanism · bridge · UI placement · risk · effort.

These four bundles deliberately target the *second tier* of bench problems — the recurring
"won't update / won't boot right / disk's mysteriously full / won't sign in / can't see the
printer" complaints that the big rocks (already shipped in v1–v2.3) don't cover. Everything
here is read-only fact-finding or one-click, reversible, documented changes, using only
PowerShell/CIM, registry reads, and standard in-box Windows CLIs.

Sequencing:
- **v2.4** — Bundle E (Won't update, won't boot, disk's full) — *lead with this*
- **v2.5** — Bundle F (Identity, licensing & policy) — opens the IT-pro / corporate audience
- **v2.6** — Bundle G (Network & sharing deep)
- **v2.7** — Bundle H (Power, storage & runtime forensics)

Reuses the v2 shared engines: `history.py` (boot-time + storage trends) and the streamed
`JobStore` pattern (DISM component-store ops, energy traces).

---

## Bundle E — v2.4 "Won't update, won't boot, disk's full"

The everyday bench killers. Highest value-to-effort in the whole plan; each item slots next
to something that already exists.

### E1. Pending-reboot detector — `backend/pendingreboot.py` (new)
- **Mechanism (registry/CIM, read-only):** key-exists checks on
  `…\Component Based Servicing\RebootPending` and `…\RebootInProgress`;
  `…\WindowsUpdate\Auto Update\RebootRequired`; the `PendingFileRenameOperations` value under
  `HKLM\SYSTEM\CurrentControlSet\Control\Session Manager`; pending computer-rename
  (`Control\ComputerName\ActiveComputerName` ≠ `…\ComputerName\ComputerName`); CBS
  `…\WindowsUpdate\Services\Pending`. If an SCCM client exists, `root\ccm\ClientSDK`
  `CCM_ClientUtilities::DetermineIfRebootPending` (skip silently if absent).
- **Why it matters:** explains a whole class of "updates fail / installs hang / nothing
  sticks" in one glance. Tiny, registry-only.
- **Bridge:** `pending_reboot()` → which signals are set + plain-English meaning of each;
  optional confirmed "restart now."
- **UI:** Toolbox card + a Dashboard chip ("Reboot pending") + a new Health Audit check.
- **Risk:** very low (read). **Effort:** Easy.

### E2. Windows Update history & error decoder — `backend/wuhistory.py` (new)
- **Mechanism:** `Microsoft.Update.Session` COM → `IUpdateSearcher.QueryHistory` → Title,
  Date, Operation, ResultCode (0–5), HResult, UpdateIdentity. **Decode** ResultCode and the
  cryptic HResults into plain English (curated map: `0x80073712`, `0x800f0922`, `0x80070020`,
  `0x8024200D`, `0x80240034`, `0x80070bc9`, …). Last successful scan/install date; service
  state for `wuauserv`/`bits`/`usosvc`/`dosvc`. Richer detail from
  `Microsoft-Windows-WindowsUpdateClient/Operational`.
- **Why it matters:** you can *reset* the WU cache today but can't *see why* it's stuck.
- **Bridge:** `wu_history(limit)`, `wu_health()`.
- **UI:** Software → Updates tab, new "History" sub-view (next to the existing pending list);
  cross-link to the existing WU-cache reset in Toolbox.
- **Risk:** low (read). **Effort:** Medium (COM history walk + code map).

### E3. Component store / WinSxS analyzer + cleanup — extend `backend/repair.py`
- **Mechanism:** `DISM /Online /Cleanup-Image /AnalyzeComponentStore` (parse actual size,
  shared-with-Windows, backups/disabled features, cache, **reclaimable**, "Cleanup
  Recommended: Yes/No"). Action: `DISM /Online /Cleanup-Image /StartComponentCleanup`
  (optional `/ResetBase` — flagged: blocks uninstalling already-installed updates). Plus
  reserved storage via `DISM /Online /Get-ReservedStorageState`. Streamed through `JobStore`
  exactly like the existing SFC/DISM repair cards.
- **Why it matters:** the honest answer to "where did 12 GB on C: go?" — pairs with the
  existing space analyzer.
- **Bridge:** `component_store_analyze()`, `component_store_cleanup(reset_base=False)`.
- **UI:** Toolbox → Repair tools (new card beside DISM) and a Cleanup cross-link.
- **Risk:** low (cleanup is a supported, safe operation; `/ResetBase` explicitly warned).
  **Effort:** Easy.

### E4. Boot-time breakdown — `backend/boottime.py` (new)
- **Mechanism:** `Microsoft-Windows-Diagnostics-Performance/Operational` Event **100**
  (BootDuration, MainPathBootTime, BootPostBootTime, degradation flag) and **101/102/103/109**
  (the specific apps/drivers/services *degrading* boot). Plus `Win32_OperatingSystem`
  LastBootUpTime + uptime, and Fast Startup state (`…\Power\HiberbootEnabled`). Trend boot
  durations over time via `history.py`.
- **Why it matters:** "it takes four minutes to boot — what's the holdup?" named, not guessed.
- **Bridge:** `boot_performance()`.
- **UI:** Event Log → new "Boot" view (sits naturally with Crashes / Reliability).
- **Risk:** low (read). **Effort:** Easy–Medium.

---

## Bundle F — v2.5 "Identity, licensing & policy"

The highest-leverage *new audience* — turns Benchly into something an IT pro reaches for on a
corporate/domain machine. Nothing here exists today.

### F1. Activation & licensing — `backend/licensing.py` (new)
- **Mechanism (CIM, no slmgr popups):** `SoftwareLicensingProduct` (filtered to the Windows
  app ID with a partial key) → LicenseStatus (0 Unlicensed … 1 Licensed … 2 OOB grace …),
  Description (channel: OEM_DM / Retail / Volume:MAK / Volume:GVLK), GracePeriodRemaining,
  PartialProductKey. `SoftwareLicensingService` → OA3xOriginalProductKey (the embedded OEM
  key — the user's own, shown with copy) and KMS host if volume-licensed. Windows edition +
  digital-license vs product-key activation.
- **Why it matters:** "is Windows actually activated / genuine, and on what kind of licence?"
- **Bridge:** `licensing_status()`.
- **UI:** System → new "Activation" card (or a Security tile).
- **Risk:** low (read; the embedded key is the machine's own). **Effort:** Easy.

### F2. Identity & domain join — `backend/identity.py` (new)
- **Mechanism:** `dsregcmd /status` (parse AzureAdJoined / EnterpriseJoined / DomainJoined /
  WorkplaceJoined, DeviceId, TenantName, the AzureAdPrt + SSO state, NgcSet/Windows Hello).
  `Win32_ComputerSystem` (Domain, PartOfDomain, DomainRole). `whoami /upn`, `whoami /groups`.
- **Why it matters:** the "why won't Outlook / Teams / SSO sign in" answer; tells you instantly
  whether a machine is Entra-joined, hybrid, or workgroup.
- **Bridge:** `identity_status()`.
- **UI:** System or Security → "Identity & domain" card.
- **Risk:** low (read; tenant/device IDs are local identifiers — shown, not transmitted).
  **Effort:** Easy–Medium (`dsregcmd` text parse).

### F3. Group Policy results — `backend/grouppolicy.py` (new)
- **Mechanism:** `gpresult /r /scope:computer` and `/scope:user` (applied GPOs, last refresh,
  security-group membership); optional `gpresult /x <tmp>.xml` for the full applied-settings
  tree. Flag GPOs that were *denied/filtered* and the last-refresh age. (User scope works as a
  standard user; computer scope needs admin → degrade.)
- **Why it matters:** "which policies are actually hitting this machine, and did any fail?"
- **Bridge:** `gpo_results()`.
- **UI:** System or Security → "Group Policy" card.
- **Risk:** low (read). **Effort:** Medium (gpresult / XML parse).

### F4. Time sync health — `backend/timesync.py` (new)
- **Mechanism:** `w32tm /query /status` (source, stratum, last sync, poll interval),
  `/query /source`, `/query /configuration`, and `w32tm /stripchart /computer:time.windows.com
  /samples:3 /dataonly` for the live offset. W32Time service state. Flag an offset of more than
  a few seconds (quietly breaks HTTPS, Kerberos, MFA, licensing). Action: `w32tm /resync`.
- **Why it matters:** clock drift is a silent root cause of cert errors and auth failures.
- **Bridge:** `time_status()`, `time_resync()`.
- **UI:** System or Network → "Clock & time sync" card; a Fix-It hook for "certificate errors
  everywhere / can't sign in."
- **Risk:** low (resync is safe). **Effort:** Easy.

---

## Bundle G — v2.6 "Network & sharing deep"

The silent-auth-failure and "can't see the other machines" cluster.

### G1. Firewall profile + rules audit — `backend/firewall.py` (new)
- **Mechanism:** `Get-NetFirewallProfile` (Domain/Private/Public — enabled, default in/out
  action, logging). `Get-NetFirewallRule -Enabled True -Direction Inbound -Action Allow`
  joined to `Get-NetFirewallApplicationFilter` / `Get-NetFirewallPortFilter` → app · port ·
  profile · remote scope. Flag broad inbound allows (Any remote address, especially on the
  Public profile) and allows for programs in user-writable paths.
- **Why it matters:** today you show firewall on/off but not *what's been opened* — the part
  that actually matters on a suspect machine.
- **Bridge:** `firewall_overview()`, `firewall_inbound_allows()`; optional confirmed
  `disable_firewall_rule(name)` (reversible).
- **UI:** Security → new "Firewall" tab (or a Network card).
- **Risk:** low to read; rule changes reversible + confirmed. **Effort:** Medium.

### G2. Network profile (Public/Private) fixer — extend `backend/network.py`
- **Mechanism:** `Get-NetConnectionProfile` (NetworkCategory per interface). The classic
  "printer / file-sharing / discovery fails because the network got set to Public." Action:
  `Set-NetConnectionProfile -NetworkCategory Private` (confirm; explain it enables discovery).
- **Bridge:** fold category into adapter info + `set_network_category(iface, category)`.
- **UI:** Network → adapter card chip, and a Fix-It runbook ("can't see other PCs / printer").
- **Risk:** low–medium (changes discovery exposure → confirm + explain). **Effort:** Easy.

### G3. Mapped drives + Credential Manager — `backend/credentials.py` (new)
- **Mechanism:** `Get-SmbMapping` / `net use` (mapped drives + status: OK / Unavailable /
  Disconnected), `Get-PSDrive`. Credential Manager via `cmdkey /list` — **target names and
  types only; secrets are never read or shown**. Flag stale/disconnected mappings and stored
  credentials for hosts that no longer resolve.
- **Why it matters:** stale mappings and orphaned saved credentials are a constant source of
  silent auth prompts and "drive's got a red X" calls.
- **Bridge:** `mapped_drives()`, `stored_credentials()`; optional confirmed removal of a stale
  mapping / credential entry.
- **UI:** Network → "Drives & credentials" card.
- **Risk:** low (`cmdkey /list` exposes no passwords); removal confirmed. **Effort:** Easy–Medium.

### G4. DNS cache viewer + Winsock/LSP catalog — extend `backend/network.py`
- **Mechanism:** `Get-DnsClientCache` (resolver cache — host, type, TTL; flag an unexpected A
  record for a well-known domain = hijack hint). `netsh winsock show catalog` (layered service
  providers — flag third-party LSPs, a classic adware/malware foothold). Pairs with the
  existing flush-DNS and winsock-reset buttons.
- **Bridge:** `dns_cache()`, `winsock_catalog()`.
- **UI:** Network tools console (new read buttons next to flush/reset).
- **Risk:** low (read). **Effort:** Easy.

---

## Bundle H — v2.7 "Power, storage & runtime forensics"

Deep diagnostics for the harder calls.

### H1. Power efficiency reports — extend `backend/power.py`
- **Mechanism:** `powercfg /energy /output <tmp>.html /duration 60` (60-second trace → parse
  errors/warnings: selective-suspend off, devices blocking sleep, processor utilisation,
  problem drivers). `powercfg /sleepstudy /output <tmp>.html` (modern-standby drain sessions +
  top offenders). `powercfg /batteryreport /output <tmp>.html` (design vs full-charge capacity,
  cycle count, recent usage). Parse the HTML/XML and present natively (don't just dump the
  report).
- **Why it matters:** goes beyond the existing wake/sleep doctor to "why is the battery
  draining in the bag / dying so fast / why won't it idle low."
- **Bridge:** `energy_report()`, `sleepstudy_report()`, `battery_report()` (via `JobStore` —
  the energy trace takes ~60 s).
- **UI:** System battery/power area (or Toolbox), with a clear "this runs a 60-second trace."
- **Risk:** low (read; time-boxed trace). **Effort:** Medium (HTML parse).

### H2. Storage deep health — extend `backend/storage.py`
- **Mechanism:** TRIM (`fsutil behavior query DisableDeleteNotify` — 0 = enabled);
  optimization/defrag state (`Optimize-Volume -Analyze` / `defrag /A` parse, last-run);
  Storage Spaces (`Get-StoragePool`, `Get-VirtualDisk`, `Get-PhysicalDisk` health + usage);
  `Get-PhysicalDisk | Get-StorageReliabilityCounter` (wear, temperature, read/write error
  counts — richer than the base SMART card); VSS/restore-point allocation (`vssadmin list
  shadowstorage`); filesystem dirty bit (`fsutil dirty query C:`); reserved storage
  (`DISM /Online /Get-ReservedStorageState`).
- **Why it matters:** "is TRIM actually running on this SSD," "how much is System Restore
  eating," "is this a Storage Spaces pool and is it healthy."
- **Bridge:** `storage_deep()` (or split: `trim_status`, `storage_spaces`, `vss_usage`).
- **UI:** Storage → new "Advanced" card cluster under the existing SMART/volumes view.
- **Risk:** low (read). **Effort:** Medium.

### H3. Environment & PATH audit — `backend/envaudit.py` (new)
- **Mechanism:** read Machine + User `Path` from the registry
  (`…\Session Manager\Environment` and `HKCU\Environment`), split, and check each entry:
  missing/deleted directory, duplicate, trailing-space/quote breakage, total length nearing the
  limit, System32 shadowed by an earlier entry. List the other env vars (TEMP, JAVA_HOME, …)
  and flag any pointing at a missing path.
- **Why it matters:** a broken/bloated PATH is a constant, baffling source of "command not
  found / tool won't launch / wrong version runs."
- **Bridge:** `env_audit()`; optional confirmed "clean broken & duplicate PATH entries"
  (backs up the prior value first → reversible).
- **UI:** System or Toolbox → "Environment & PATH" card.
- **Risk:** low to read; any PATH edit is backed up + reversible + confirmed. **Effort:** Easy–Medium.

### H4. Runtime inventory — `backend/runtimes.py` (new)
- **Mechanism:** .NET Framework via `…\NET Framework Setup\NDP` (4.x Release DWORD → version
  map; 3.5 presence) and .NET 5+/Core via `dotnet --list-runtimes` + `%ProgramFiles%\dotnet\
  shared` when present; VC++ redistributables from the uninstall registry keys (filtered to
  "Visual C++"); DirectX + feature levels via `dxdiag /t <tmp>.txt` parse; installed optional
  features / capabilities (`Get-WindowsOptionalFeature -Online`, `Get-WindowsCapability
  -Online` — e.g. .NET 3.5, RSAT).
- **Why it matters:** the "app won't start — missing runtime" diagnosis, done in one place.
- **Bridge:** `runtimes_inventory()`.
- **UI:** Software → new "Runtimes" tab.
- **Risk:** low (read). **Effort:** Medium.

### H5. Audio device doctor — `backend/audio.py` (new)
- **Mechanism:** endpoint state from `…\CurrentVersion\MMDevices\Audio\Render|Capture` (device
  state, default role) and `Get-PnpDevice -Class AudioEndpoint`; default playback/recording
  device, disabled/unplugged endpoints, exclusive-mode flag, sample-rate, and the Audiosrv /
  AudioEndpointBuilder service state. The "no sound / wrong output / crackling / can't pick a
  device" triage.
- **Bridge:** `audio_status()`; optional confirmed restart of the audio services (reversible).
- **UI:** Devices → "Audio" card, and/or extend the Fix-It "no sound" runbook.
- **Risk:** low. **Effort:** Medium.

---

## Cross-cutting (applies to all four bundles)
- **Read-first; every change shows what+where; reversible (back up / restore, not destroy);
  confirm anything that alters config with the affected item named.**
- **Degrade gracefully without admin** — computer-scope GPO, full firewall detail, energy
  traces and some licensing fields want elevation; show the partial picture and say so.
- **Disclose egress.** Almost everything here is purely local; the only outbound calls are the
  optional `w32tm /stripchart` NTP sample (F4) and any VirusTotal hash reuse — named up front,
  hash-only, consistent with the existing policy.
- **Present heuristics as ranked context, not verdicts** (firewall broad-allows, suspicious
  PATH/credential/DNS entries) — plenty of legitimate setups trip them.
- **New Health Audit inputs** worth wiring as they land: pending-reboot (E1), large time
  offset (F4), Windows not activated (F1), TRIM disabled on an SSD (H2).
- Reuse `history.py` for the boot-time (E4) and storage-reliability (H2) trends; reuse the
  streamed `JobStore` pattern for the DISM (E3) and `powercfg /energy` (H1) long ops.
