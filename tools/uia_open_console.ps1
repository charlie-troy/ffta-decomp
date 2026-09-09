param([int]$ProcId = 0)
# Open the mGBA Scripting console for the given process by focusing the main
# window first (the menu bar does not expose items while unfocused), then
# invoking Tools > Scripting... via UIA.
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class Win32f {
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
$sw = $null
$main = $null
foreach ($w in $wins) {
  if ($w.Current.Name -eq 'Scripting') { $sw = $w }
  elseif ($w.Current.ClassName -eq 'QGBA::Window') { $main = $w }
}
if ($sw) { Write-Output "already-open"; [Environment]::Exit(0) }
if (-not $main) { Write-Output "no main window"; exit 1 }

[Win32f]::ShowWindow([IntPtr]$main.Current.NativeWindowHandle, 9) | Out-Null
[Win32f]::SetForegroundWindow([IntPtr]$main.Current.NativeWindowHandle) | Out-Null
Start-Sleep -Milliseconds 600

# Win32 menus are lazy: items only exist while the menu is open. Open the
# Tools menu with Alt+T, then find the popup (class #32768) and invoke the
# Scripting item from it.
$sh = New-Object -ComObject WScript.Shell
$sh.SendKeys('%t')
Start-Sleep -Milliseconds 700
$popCond = New-Object System.Windows.Automation.PropertyCondition(
  [System.Windows.Automation.AutomationElement]::ClassNameProperty, '#32768')
$pops = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $popCond)
$opened = $false
foreach ($p in $pops) {
  $mits = $p.FindAll([System.Windows.Automation.TreeScope]::Descendants,
    (New-Object System.Windows.Automation.PropertyCondition(
      [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
      [System.Windows.Automation.ControlType]::MenuItem)))
  foreach ($it in $mits) {
    if ($it.Current.Name -like 'Scripting*') {
      $inv = $null
      if ($it.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern,
          [ref]$inv)) { $inv.Invoke(); $opened = $true }
    }
  }
}
$sh.SendKeys('{ESC}')
Start-Sleep -Milliseconds 1800
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $cond)
foreach ($w in $wins) { if ($w.Current.Name -eq 'Scripting') { Write-Output "opened"; [Environment]::Exit(0) } }
if ($opened) { Write-Output "invoked-but-not-seen" } else { Write-Output "menu-item-not-found" }
[Environment]::Exit(0)
