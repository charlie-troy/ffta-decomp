param([int]$ProcId = 0, [string]$Out = "outputs/window.png")
# Capture an mGBA window (client area) to PNG without touching the GDB stub.
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class Win32c {
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr hWnd, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr hWnd, ref POINT p);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
}
'@
$root = [System.Windows.Automation.AutomationElement]::RootElement
$hwnd = [IntPtr]::Zero
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
foreach ($w in $wins) {
  if ($ProcId -eq 0 -or $w.Current.ProcessId -eq $ProcId) {
    if ($w.Current.ClassName -eq 'QGBA::Window') { $hwnd = [IntPtr]$w.Current.NativeWindowHandle }
  }
}
if ($hwnd -eq [IntPtr]::Zero) { Write-Output "no mGBA window"; exit 1 }
$r = New-Object Win32c+RECT
[Win32c]::GetClientRect($hwnd, [ref]$r) | Out-Null
$p = New-Object Win32c+POINT
$p.X = 0; $p.Y = 0
[Win32c]::ClientToScreen($hwnd, [ref]$p) | Out-Null
$w = $r.R - $r.L; $h = $r.B - $r.T
$bmp = New-Object System.Drawing.Bitmap($w, $h)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($p.X, $p.Y, 0, 0, [System.Drawing.Size]::new($w, $h))
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output "saved $Out ($w x $h)"
