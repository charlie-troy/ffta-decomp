param([int]$ProcId = 101912)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32c {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
}
"@
$root = [System.Windows.Automation.AutomationElement]::RootElement
$procCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $ProcId)
$miCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::MenuItem)
$sh = New-Object -ComObject WScript.Shell
$script = $null
for ($try = 0; $try -lt 6 -and -not $script; $try++) {
  $win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $procCond)
  $hwnd = [IntPtr]$win.Current.NativeWindowHandle
  [Win32c]::SetForegroundWindow($hwnd) | Out-Null
  Start-Sleep -Milliseconds 400
  $sh.SendKeys('%t')
  Start-Sleep -Milliseconds 800
  $items = $win.FindAll([System.Windows.Automation.TreeScope]::Descendants, $miCond)
  $names = @()
  foreach ($it in $items) {
    $names += $it.Current.Name
    if ($it.Current.Name -eq 'Scripting...') { $script = $it }
  }
  Write-Output ("try " + $try + ": menu items=" + $items.Count + " scripting? " + [bool]$script)
  if (-not $script) { $sh.SendKeys('{ESC}'); Start-Sleep -Milliseconds 300 }
}
if ($script) {
  $inv = $null
  if ($script.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$inv)) {
    $inv.Invoke(); Write-Output "invoked Scripting..."
  }
}
Start-Sleep -Milliseconds 2500
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $procCond)
Write-Output ("top-level windows: " + $wins.Count)
foreach ($w in $wins) {
  Write-Output ("WIN: '" + $w.Current.Name + "' class=" + $w.Current.ClassName)
}
