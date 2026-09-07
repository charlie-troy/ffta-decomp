param([int]$ProcId = 0, [string]$Keys = '{ENTER}')
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32s {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
}
"@
$root = [System.Windows.Automation.AutomationElement]::RootElement
$procCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $ProcId)
$win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $procCond)
if (-not $win) { Write-Output "no window"; exit 1 }
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $procCond)
$main = $null
foreach ($w in $wins) {
  if ($w.Current.ClassName -eq 'QGBA::Window') { $main = $w }
}
if (-not $main) { $main = $win }
$hwnd = [IntPtr]$main.Current.NativeWindowHandle
[Win32s]::SetForegroundWindow($hwnd) | Out-Null
Start-Sleep -Milliseconds 400
$sh = New-Object -ComObject WScript.Shell
$sh.SendKeys($Keys)
Write-Output ("sent " + $Keys + " to '" + $main.Current.Name + "'")
