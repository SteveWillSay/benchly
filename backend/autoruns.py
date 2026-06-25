"""Autostart persistence map — the 'Autoruns' surface, with signature + VirusTotal triage.

Enumerates the autostart locations malware actually uses, resolves each to a file
on disk, checks its Authenticode signature, and (on demand) hashes it for a
VirusTotal lookup. Unsigned entries in temp/AppData/random paths float to the top.
"""

import os
import re

from .ps import ps_json, as_list


# Categories are queried in one PS round-trip. Each emits {Name, Command, Location}.
_AUTORUNS_PS = r"""
$out = New-Object System.Collections.ArrayList
function Add-Entry($cat, $name, $cmd) {
    if ($cmd) { [void]$out.Add([pscustomobject]@{ Category=$cat; Name=$name; Command=[string]$cmd }) }
}
$runKeys = @(
    @('Run (HKLM)','HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run'),
    @('Run (HKLM WOW64)','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run'),
    @('Run (HKCU)','HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run'),
    @('RunOnce (HKLM)','HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce'),
    @('RunOnce (HKCU)','HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce'),
    @('RunOnceEx (HKLM)','HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnceEx'),
    @('RunServices (HKLM)','HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunServices'),
    @('RunServices (HKCU)','HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunServices'),
    @('RunServicesOnce (HKLM)','HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunServicesOnce'),
    @('RunServicesOnce (HKCU)','HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunServicesOnce'),
    @('Policies\Explorer\Run (HKLM)','HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer\Run'),
    @('Policies\Explorer\Run (HKCU)','HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer\Run')
)
foreach ($k in $runKeys) {
    $p = Get-ItemProperty -Path $k[1] -ErrorAction SilentlyContinue
    if ($p) { $p.PSObject.Properties | Where-Object { $_.Name -notlike 'PS*' } | ForEach-Object { Add-Entry $k[0] $_.Name $_.Value } }
}
# Winlogon
$wl = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' -ErrorAction SilentlyContinue
if ($wl) {
    if ($wl.Userinit -and $wl.Userinit -notlike '*userinit.exe,') { Add-Entry 'Winlogon\Userinit' 'Userinit' $wl.Userinit }
    if ($wl.Shell -and $wl.Shell -ne 'explorer.exe') { Add-Entry 'Winlogon\Shell' 'Shell' $wl.Shell }
}
# AppInit_DLLs (classic injection)
$ai = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Windows' -ErrorAction SilentlyContinue
if ($ai -and $ai.AppInit_DLLs) { Add-Entry 'AppInit_DLLs' 'AppInit_DLLs' $ai.AppInit_DLLs }
# Image File Execution Options debuggers (hijack)
Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options' -ErrorAction SilentlyContinue | ForEach-Object {
    $d = (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).Debugger
    if ($d) { Add-Entry 'IFEO Debugger' ($_.PSChildName) $d }
}
# Active Setup
Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Active Setup\Installed Components' -ErrorAction SilentlyContinue | ForEach-Object {
    $s = (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).StubPath
    if ($s) { Add-Entry 'Active Setup' ($_.PSChildName) $s }
}
# Services with non-system binaries (auto-start, third-party path)
Get-CimInstance Win32_Service -ErrorAction SilentlyContinue | Where-Object {
    $_.PathName -and $_.StartMode -eq 'Auto' -and $_.PathName -notlike '*\system32\*' -and $_.PathName -notlike '*\Systemroot\*'
} | ForEach-Object { Add-Entry 'Service (auto)' $_.Name $_.PathName }
# WMI permanent event consumers (advanced persistence)
Get-CimInstance -Namespace root/subscription -ClassName CommandLineEventConsumer -ErrorAction SilentlyContinue | ForEach-Object {
    Add-Entry 'WMI consumer' $_.Name ($_.CommandLineTemplate)
}
# LSA security/authentication providers (DLLs loaded by lsass)
$lsaKeys = @(
    @('LSA Security Packages','HKLM:\SYSTEM\CurrentControlSet\Control\Lsa','Security Packages'),
    @('LSA Authentication Packages','HKLM:\SYSTEM\CurrentControlSet\Control\Lsa','Authentication Packages'),
    @('LSA OSConfig Security Packages','HKLM:\SYSTEM\CurrentControlSet\Control\Lsa\OSConfig','Security Packages')
)
foreach ($k in $lsaKeys) {
    $p = Get-ItemProperty -Path $k[1] -ErrorAction SilentlyContinue
    if ($p) { ($p.($k[2])) | Where-Object { $_ } | ForEach-Object { Add-Entry $k[0] $_ $_ } }
}
# Print monitor DLLs (non-default monitors are a known persistence vector)
$defaultMonitors = @('Local Port','Standard TCP/IP Port','USB Monitor','WSD Port','BJ Language Monitor','Microsoft Shared Fax Monitor','LPR Port','AppMon')
Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Control\Print\Monitors' -ErrorAction SilentlyContinue | ForEach-Object {
    $drv = (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).Driver
    if ($drv -and ($defaultMonitors -notcontains $_.PSChildName)) { Add-Entry 'Print Monitor' ($_.PSChildName) $drv }
}
$out
"""


def _extract_path(command):
    """Pull the executable/DLL path out of a registry command string."""
    if not command:
        return None
    cmd = command.strip()
    m = re.match(r'"([^"]+)"', cmd)               # quoted path
    if m:
        return os.path.expandvars(m.group(1))
    m = re.search(r'([A-Za-z]:\\[^",]+?\.(?:exe|dll|sys|bat|cmd|vbs|ps1|scr))', cmd, re.IGNORECASE)
    if m:
        return os.path.expandvars(m.group(1))
    first = os.path.expandvars(cmd.split(",")[0].split()[0]) if cmd.split() else None
    return first


_SUSPECT_DIRS = ("\\temp\\", "\\tmp\\", "\\appdata\\local\\temp\\", "\\downloads\\",
                 "\\programdata\\", "\\users\\public\\", "\\appdata\\roaming\\")


def _path_exists(p):
    """Existence check that never blocks on a disconnected UNC path."""
    if not p:
        return False
    if p.startswith("\\\\"):
        return True   # don't stat UNC — a dead \\server\... can hang for tens of seconds
    try:
        return os.path.exists(p)
    except OSError:
        return False


def _suspicion(path, signed, category, exists):
    """signed: signer string if validly signed, False if not, None if unknown.
    A valid signature from a publisher clears the heuristic flags — those target
    unsigned droppers, not legit software that happens to live in ProgramData."""
    score = 0
    reasons = []
    low = (path or "").lower()
    validly_signed = isinstance(signed, str)

    if signed is False:
        score += 2; reasons.append("unsigned")
    if not validly_signed:
        if any(d in low for d in _SUSPECT_DIRS):
            score += 2; reasons.append("runs from a temp/profile folder")
        name = os.path.basename(low)
        if re.match(r"^[a-z0-9]{8,}\.(exe|dll)$", name) and not re.search(r"[aeiou]", name[:6]):
            score += 1; reasons.append("random-looking name")
    # missing target only matters for categories that should resolve to a file
    if (not path or not exists) and category not in ("Active Setup", "WMI consumer"):
        score += 1; reasons.append("target missing")
    return score, reasons


def get_autoruns():
    rows = as_list(ps_json(_AUTORUNS_PS, timeout=90, depth=3))
    entries = []
    # resolve + stat each unique path exactly once (stats can be slow)
    paths = []
    exists_cache = {}
    for r in rows:
        p = _extract_path(r.get("Command"))
        r["_path"] = p
        if p not in exists_cache:
            exists_cache[p] = _path_exists(p)
        r["_exists"] = exists_cache[p]
        if p and r["_exists"]:
            paths.append(p)
    sigs = _signatures(paths)

    for i, r in enumerate(rows):
        path = r.get("_path")
        signed = sigs.get((path or "").lower()) if path else None
        score, reasons = _suspicion(path, signed, r.get("Category"), r["_exists"])
        entries.append({
            "id": i,
            "category": r.get("Category"),
            "name": r.get("Name") or "",
            "command": r.get("Command") or "",
            "path": path or "",
            "exists": r["_exists"],
            "signer": signed if isinstance(signed, str) else None,
            "signed": signed is not False and signed is not None,
            "suspicion": score,
            "reasons": reasons,
        })
    entries.sort(key=lambda e: (-e["suspicion"], e["category"], e["name"].lower()))
    return {"entries": entries, "flagged": sum(1 for e in entries if e["suspicion"] >= 2)}


def _signatures(paths):
    """path(lower) -> signer name (str) if validly signed, False if not, None if unknown."""
    if not paths:
        return {}
    uniq = sorted(set(paths))
    # build a PS array literal safely
    arr = ",".join("'" + p.replace("'", "''") + "'" for p in uniq)
    rows = as_list(ps_json(
        f"@({arr}) | ForEach-Object {{ $s = Get-AuthenticodeSignature -LiteralPath $_ -ErrorAction SilentlyContinue; "
        "[pscustomobject]@{ Path=$_; Status=[string]$s.Status; Signer=$s.SignerCertificate.Subject } }",
        timeout=90, depth=3))
    out = {}
    for r in rows:
        p = (r.get("Path") or "").lower()
        if r.get("Status") == "Valid":
            subj = r.get("Signer") or ""
            m = re.search(r"CN=([^,]+)", subj)
            out[p] = m.group(1).strip() if m else "Signed"
        else:
            out[p] = False
    return out
