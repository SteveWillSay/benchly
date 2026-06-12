"""Windows Memory Diagnostic — launch the scheduler and read past results."""

import subprocess

from .ps import ps_json, as_list, CREATE_NO_WINDOW

_RESULTS_PS = r"""
Get-WinEvent -FilterHashtable @{ LogName='System';
        ProviderName='Microsoft-Windows-MemoryDiagnostics-Results' } -MaxEvents 5 -ErrorAction SilentlyContinue |
    Select-Object @{n='Time';e={$_.TimeCreated.ToString('yyyy-MM-dd HH:mm')}},
                  Id,
                  @{n='Msg';e={ if ($_.Message) { $_.Message.Substring(0, [Math]::Min(300, $_.Message.Length)) } else { '' } }}
"""


def launch_memory_test():
    """Opens mdsched.exe — Windows shows its own restart-now/later dialog (and a
    UAC prompt if we aren't elevated)."""
    try:
        subprocess.Popen(["mdsched.exe"], creationflags=CREATE_NO_WINDOW)
        return {"ok": True}
    except OSError as e:
        return {"ok": False, "error": str(e)}


def get_memory_results():
    rows = as_list(ps_json(_RESULTS_PS, timeout=30))
    results = []
    for r in rows:
        msg = (r.get("Msg") or "").replace("\r\n", " ").replace("\n", " ").strip()
        # Event 1201 = completed; "no errors" appears in the pass message on all SKUs
        passed = "no errors" in msg.lower() or "keine fehler" in msg.lower()
        results.append({"time": r.get("Time"), "id": r.get("Id"),
                        "message": msg, "passed": passed if msg else None})
    return results
