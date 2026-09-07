Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@
$root = [System.Windows.Automation.AutomationElement]::RootElement
$procCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, 101912)
$win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $procCond)
$hwnd = [IntPtr]$win.Current.NativeWindowHandle
Write-Output ("hwnd=" + $hwnd)
[Win32]::ShowWindow($hwnd, 9) | Out-Null   # SW_RESTORE
$r = [Win32]::SetForegroundWindow($hwnd)
Write-Output ("SetForeground=" + $r)
Start-Sleep -Milliseconds 600
$sh = New-Object -ComObject WScript.Shell
$sh.SendKeys('%t')
Start-Sleep -Milliseconds 1000
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $procCond)
Write-Output ("top-level windows now: " + $wins.Count)
foreach ($w in $wins) {
  Write-Output ("WIN: '" + $w.Current.Name + "' class=" + $w.Current.ClassName)
}
$all = $win.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
foreach ($el in $all) {
  $n = $el.Current.Name
  if ($n) { Write-Output ("   EL: '" + $n + "' " + $el.Current.ControlType.ProgrammaticName) }
}
