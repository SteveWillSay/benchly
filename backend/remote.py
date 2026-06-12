"""Remote machine snapshot over WinRM (Invoke-Command).

Requires WinRM enabled on the target (`Enable-PSRemoting` / GPO) and either the
current user having rights there or explicit credentials. Credentials travel to
PowerShell through environment variables — never the command line — and are not
persisted anywhere.
"""

import re

from .ps import ps_json, run_ps

# Runs ON THE TARGET inside Invoke-Command — keep it self-contained and fast.
_SNAPSHOT_BLOCK = r"""
    $os  = Get-CimInstance Win32_OperatingSystem
    $cs  = Get-CimInstance Win32_ComputerSystem
    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
    $c   = Get-PSDrive -Name C -ErrorAction SilentlyContinue
    $stopped = Get-Service | Where-Object { $_.StartType -eq 'Automatic' -and $_.Status -ne 'Running' }
    $qfe = Get-CimInstance Win32_QuickFixEngineering | Sort-Object { $_.InstalledOn } -Descending | Select-Object -First 1
    $reboot = (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending') -or
              (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\WindowsUpdate\Auto Update\RebootRequired')
    $av = $null
    try { $av = (Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct |
                 Where-Object { $_.productState -band 0x1000 } | Select-Object -First 1).displayName } catch {}
    [pscustomobject]@{
        Host     = $env:COMPUTERNAME
        OS       = $os.Caption
        Build    = $os.BuildNumber
        Boot     = $os.LastBootUpTime.ToString('yyyy-MM-dd HH:mm')
        Model    = ($cs.Manufacturer + ' ' + $cs.Model).Trim()
        CPU      = $cpu.Name
        RamGB    = [math]::Round($cs.TotalPhysicalMemory / 1GB, 1)
        CFreeGB  = if ($c) { [math]::Round($c.Free / 1GB, 1) } else { $null }
        CTotalGB = if ($c) { [math]::Round(($c.Free + $c.Used) / 1GB, 1) } else { $null }
        Stopped  = @($stopped | Select-Object -First 6 | ForEach-Object { $_.DisplayName })
        StoppedN = ($stopped | Measure-Object).Count
        LastKB   = if ($qfe) { $qfe.HotFixID } else { $null }
        Reboot   = $reboot
        AV       = $av
        User     = (Get-CimInstance Win32_ComputerSystem).UserName
    }
"""

_HOST_RE = re.compile(r"^[A-Za-z0-9._\-]+$")


def remote_snapshot(host: str, user: str = "", password: str = ""):
    host = (host or "").strip()
    if not host or not _HOST_RE.match(host):
        return {"ok": False, "error": "Enter a valid computer name or IP."}

    if user:
        cred = ("$sec = ConvertTo-SecureString $env:DM_RPASS -AsPlainText -Force; "
                "$cred = New-Object System.Management.Automation.PSCredential($env:DM_RUSER, $sec); ")
        cred_arg = " -Credential $cred"
        env = {"DM_RUSER": user, "DM_RPASS": password or ""}
    else:
        cred, cred_arg, env = "", "", None

    # Fast reachability check first so a dead host fails in seconds, not minutes
    probe = run_ps(
        f"{cred}try {{ $null = Test-WSMan -ComputerName '{host}'{cred_arg} -ErrorAction Stop; 'OK' }} "
        f"catch {{ 'ERR: ' + $_.Exception.Message }}", timeout=30, env=env)
    if not probe.startswith("OK"):
        detail = probe[5:].strip() if probe.startswith("ERR:") else "no response"
        # WSMan faults arrive as XML — pull out the human-readable message
        m = re.search(r"<f:Message>(.*?)</f:Message>", detail, re.S)
        if m:
            detail = m.group(1).strip()
        detail = re.sub(r"<[^>]+>", " ", detail).strip()
        return {"ok": False,
                "error": f"WinRM not reachable on {host} — {detail[:200]} "
                         "(target needs Enable-PSRemoting and firewall rule 5985)."}

    raw = ps_json(
        f"{cred}Invoke-Command -ComputerName '{host}'{cred_arg} -ScriptBlock {{ {_SNAPSHOT_BLOCK} }} | "
        "Select-Object -Property * -ExcludeProperty PSComputerName,RunspaceId,PSShowComputerName",
        timeout=120, env=env)
    if raw is None:
        return {"ok": False, "error": "Remote command returned nothing (access denied or policy blocked)."}

    return {"ok": True, "snapshot": {
        "host": raw.get("Host"),
        "os": raw.get("OS"),
        "build": raw.get("Build"),
        "boot": raw.get("Boot"),
        "model": raw.get("Model"),
        "cpu": (raw.get("CPU") or "").strip(),
        "ram_gb": raw.get("RamGB"),
        "c_free_gb": raw.get("CFreeGB"),
        "c_total_gb": raw.get("CTotalGB"),
        "stopped_services": raw.get("Stopped") or [],
        "stopped_count": raw.get("StoppedN") or 0,
        "last_kb": raw.get("LastKB"),
        "reboot_pending": bool(raw.get("Reboot")),
        "av": raw.get("AV"),
        "logged_on": raw.get("User"),
    }}
