"""Pending-reboot detector — the 'why won't anything install / nothing sticks' answer.

Windows sets a handful of registry breadcrumbs when it's waiting on a restart to
finish servicing. Until that restart happens, update installs hang, some MSIs
refuse to run, and config changes silently don't take. This reads every well-known
signal, explains in plain English what each one means, and (on request, confirmed)
restarts the machine. Read-only except for the explicit restart.
"""

import winreg

HKLM = winreg.HKEY_LOCAL_MACHINE


def _key_exists(path):
    try:
        k = winreg.OpenKey(HKLM, path)
        winreg.CloseKey(k)
        return True
    except OSError:
        return False


def _value(path, name):
    try:
        k = winreg.OpenKey(HKLM, path)
        try:
            v, _ = winreg.QueryValueEx(k, name)
            return v
        finally:
            winreg.CloseKey(k)
    except OSError:
        return None


def _active_vs_pending_name():
    """A queued computer rename leaves ActiveComputerName != ComputerName."""
    active = _value(r"SYSTEM\CurrentControlSet\Control\ComputerName\ActiveComputerName",
                    "ComputerName")
    pending = _value(r"SYSTEM\CurrentControlSet\Control\ComputerName\ComputerName",
                     "ComputerName")
    if active and pending and active != pending:
        return active, pending
    return None


def _pending_file_renames():
    """PendingFileRenameOperations is a REG_MULTI_SZ of files to move/delete on boot.

    Entries come in pairs (source, dest); a blank dest means 'delete'. Returns the
    count of operations, or 0.
    """
    raw = _value(r"SYSTEM\CurrentControlSet\Control\Session Manager",
                 "PendingFileRenameOperations")
    if not raw:
        return 0
    sources = [s for s in raw if s and not s.startswith("!")]
    # pairs of (source, target); count source entries
    return max(0, len([s for i, s in enumerate(sources) if i % 2 == 0]))


def _sccm_pending():
    """If a ConfigMgr (SCCM) client is present, ask it directly. None if no client."""
    try:
        from .ps import run_ps
        out = run_ps(
            "& { try { $r = Invoke-CimMethod -Namespace 'root\\ccm\\ClientSDK' "
            "-ClassName 'CCM_ClientUtilities' -MethodName 'DetermineIfRebootPending' "
            "-ErrorAction Stop; if ($r.RebootPending -or $r.IsHardRebootPending) "
            "{ 'YES' } else { 'NO' } } catch { 'NA' } }", timeout=15)
        if "YES" in out:
            return True
        if "NO" in out:
            return False
    except Exception:
        pass
    return None


def pending_reboot():
    """Every pending-reboot signal, explained. `pending` = any hard signal is set."""
    signals = []

    def add(sid, label, is_set, detail, where):
        signals.append({"id": sid, "label": label, "set": bool(is_set),
                        "detail": detail, "where": where})

    cbs = _key_exists(r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending")
    add("cbs", "Component servicing", cbs,
        "A Windows component (a feature, language pack, or cumulative update) finished "
        "staging and is waiting on a restart to complete. This is the most common cause "
        "of 'updates won't install — another is pending'.",
        r"HKLM\SOFTWARE\…\Component Based Servicing\RebootPending")

    cbs_prog = _key_exists(r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootInProgress")
    add("cbs_inprogress", "Servicing in progress", cbs_prog,
        "Component servicing is mid-flight. Let it finish, then restart.",
        r"HKLM\SOFTWARE\…\Component Based Servicing\RebootInProgress")

    wu = _key_exists(r"SOFTWARE\Microsoft\Windows\WindowsUpdate\Auto Update\RebootRequired")
    add("wu", "Windows Update", wu,
        "Windows Update installed something that needs a restart to take effect.",
        r"HKLM\SOFTWARE\…\WindowsUpdate\Auto Update\RebootRequired")

    n_files = _pending_file_renames()
    add("file_rename", "Files queued to move on boot", n_files > 0,
        (f"{n_files} file operation(s) are scheduled to run at the next boot — usually an "
         "installer or update that couldn't replace a file in use. Common after a half-"
         "finished install." if n_files else
         "No files are queued to be moved or deleted on the next boot."),
        r"HKLM\SYSTEM\…\Session Manager\PendingFileRenameOperations")

    rename = _active_vs_pending_name()
    add("computer_rename", "Computer rename", rename is not None,
        (f"This PC was renamed to '{rename[1]}' but is still running as '{rename[0]}' — the "
         "new name applies after a restart." if rename else
         "No computer rename is waiting."),
        r"HKLM\SYSTEM\…\ComputerName\(Active)ComputerName")

    sccm = _sccm_pending()
    if sccm is not None:
        add("sccm", "ConfigMgr (SCCM) client", sccm,
            "The ConfigMgr management client reports a reboot is pending for a deployment.",
            r"root\ccm\ClientSDK CCM_ClientUtilities")

    hard = [s for s in signals if s["set"]]
    pending = len(hard) > 0
    if pending:
        summary = ("A restart is pending — " + ", ".join(s["label"].lower() for s in hard) +
                   ". Until you reboot, new updates and some installers may fail or silently "
                   "not apply. A restart will clear this.")
    else:
        summary = "No restart is pending. Servicing is up to date and nothing's waiting on a reboot."

    return {"ok": True, "pending": pending, "count": len(hard),
            "signals": signals, "summary": summary}


def restart_now():
    """Restart the machine (the UI confirms first). 10-second grace so the bridge returns."""
    try:
        from .ps import run_ps
        run_ps("& { shutdown.exe /r /t 10 /c 'Benchly is restarting to finish a pending update.' }",
               timeout=10)
        return {"ok": True, "restarting_in": 10}
    except Exception as e:
        return {"ok": False, "error": str(e)}
