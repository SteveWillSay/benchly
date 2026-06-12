param([string]$Title = "DeskMedic", [string]$Out = "F:\Surprise App\_dev\shot.png", [int]$ProcId = 0)
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class Win4 {
    public delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc p, IntPtr l);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
[Win4]::SetProcessDPIAware() | Out-Null
$script:target = [IntPtr]::Zero
$cb = { param($h, $l)
    if ([Win4]::IsWindowVisible($h)) {
        $sb = New-Object System.Text.StringBuilder 256
        [Win4]::GetWindowText($h, $sb, 256) | Out-Null
        if ($sb.ToString() -eq $Title) {
            if ($ProcId -gt 0) {
                $wpid = [uint32]0
                [Win4]::GetWindowThreadProcessId($h, [ref]$wpid) | Out-Null
                if ($wpid -ne $ProcId) { return $true }
            }
            $script:target = $h; return $false
        }
    }
    return $true
}
[Win4]::EnumWindows($cb, [IntPtr]::Zero) | Out-Null
if ($script:target -eq [IntPtr]::Zero) { Write-Output "WINDOW NOT FOUND"; exit 1 }
$r = New-Object Win4+RECT
[Win4]::GetWindowRect($script:target, [ref]$r) | Out-Null
$w = $r.Right - $r.Left; $hh = $r.Bottom - $r.Top
$bmp = New-Object System.Drawing.Bitmap($w, $hh)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$dc = $g.GetHdc()
# PW_RENDERFULLCONTENT = 2 (needed for WebView2 / DirectComposition surfaces)
$okPrint = [Win4]::PrintWindow($script:target, $dc, 2)
$g.ReleaseHdc($dc)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output "SAVED $Out ($w x $hh) printOk=$okPrint"
