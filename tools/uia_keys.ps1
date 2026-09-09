param([int]$ProcId = 0, [string]$Keys = 'x', [int]$GapMs = 350)
# Focus the mGBA main window and send real keyboard events (default mGBA
# mapping: X = GBA A, Z = GBA B, arrows = D-pad, Enter = Start).
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class Win32k {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
'@
$root = [System.Windows.Automation.AutomationElement]::RootElement
$cond = [System.Windows.Automation.Condition]::TrueCondition
if ($ProcId -ne 0) {
  $cond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ProcessIdProperty, $ProcId)
}
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $cond)
$main = $null
foreach ($w in $wins) {
  if ($w.Current.ClassName -eq 'QGBA::Window') { $main = $w }
}
if (-not $main) { Write-Output 'no main window'; exit 1 }
[Win32k]::ShowWindow([IntPtr]$main.Current.NativeWindowHandle, 9) | Out-Null
[Win32k]::SetForegroundWindow([IntPtr]$main.Current.NativeWindowHandle) | Out-Null
Start-Sleep -Milliseconds 500
$sh = New-Object -ComObject WScript.Shell
foreach ($ch in $Keys.ToCharArray()) {
  $sh.SendKeys([string]$ch)
  Start-Sleep -Milliseconds $GapMs
}
Write-Output "sent: $Keys"
[Environment]::Exit(0)
