param([int]$ProcId = 0, [string]$Cmd = 'console:log("hi")')
# Send one Lua command to an mGBA Scripting console (opening it if needed)
# via UIA. Works while a GDB client holds the stub: the Lua console and the
# GDB stub are independent subsystems.
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class Win32e {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
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
if (-not $sw -and $main) {
  # open the console through Tools > Scripting...
  $mbCond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::MenuBar)
  $mbar = $main.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $mbCond)
  $mits = $mbar.FindAll([System.Windows.Automation.TreeScope]::Descendants,
    (New-Object System.Windows.Automation.PropertyCondition(
      [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
      [System.Windows.Automation.ControlType]::MenuItem)))
  foreach ($it in $mits) {
    if ($it.Current.Name -like 'Scripting*') {
      $inv = $null
      if ($it.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern,
          [ref]$inv)) { $inv.Invoke() }
    }
  }
  Start-Sleep -Milliseconds 1500
  $wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $cond)
  foreach ($w in $wins) { if ($w.Current.Name -eq 'Scripting') { $sw = $w } }
}
if (-not $sw) { Write-Output "no scripting window"; exit 1 }
[Win32e]::SetForegroundWindow([IntPtr]$sw.Current.NativeWindowHandle) | Out-Null
Start-Sleep -Milliseconds 300
$edCond = New-Object System.Windows.Automation.PropertyCondition(
  [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
  [System.Windows.Automation.ControlType]::Edit)
$eds = $sw.FindAll([System.Windows.Automation.TreeScope]::Descendants, $edCond)
$input = $null
foreach ($e in $eds) { if ($e.Current.ClassName -eq 'QLineEdit') { $input = $e } }
if (-not $input) { Write-Output "no QLineEdit"; exit 1 }
$vp = $null
if ($input.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern,
    [ref]$vp)) {
  $vp.SetValue($Cmd)
} else { Write-Output "no value pattern"; exit 1 }
$input.SetFocus()
Start-Sleep -Milliseconds 200
$sh = New-Object -ComObject WScript.Shell
$sh.SendKeys('{ENTER}')
Start-Sleep -Milliseconds 2500
foreach ($e in $eds) {
  if ($e.Current.ClassName -like '*Log*') {
    $lvp = $null
    if ($e.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern,
        [ref]$lvp)) {
      $v = $lvp.Current.Value
      if ($v) { Write-Output ("LOG: " + $v.Substring([Math]::Max(0, $v.Length - 400))) }
    }
  }
}
# UIA finalizers can keep PowerShell alive indefinitely; exit explicitly.
[Environment]::Exit(0)
