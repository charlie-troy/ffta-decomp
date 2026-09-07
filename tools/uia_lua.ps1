param([string]$Cmd = 'print("hi")')
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32e {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
}
"@
$root = [System.Windows.Automation.AutomationElement]::RootElement
$procCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, 101912)
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $procCond)
$sw = $null
foreach ($w in $wins) { if ($w.Current.Name -eq 'Scripting') { $sw = $w } }
if (-not $sw) { Write-Output "no scripting window"; exit 1 }
[Win32e]::SetForegroundWindow([IntPtr]$sw.Current.NativeWindowHandle) | Out-Null
Start-Sleep -Milliseconds 300
$edCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Edit)
$eds = $sw.FindAll([System.Windows.Automation.TreeScope]::Descendants, $edCond)
$input = $null
foreach ($e in $eds) { if ($e.Current.ClassName -eq 'QLineEdit') { $input = $e } }
if (-not $input) { Write-Output "no QLineEdit"; exit 1 }
$vp = $null
if ($input.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$vp)) {
  $vp.SetValue($Cmd)
} else { Write-Output "no value pattern on input"; exit 1 }
$input.SetFocus()
Start-Sleep -Milliseconds 200
$sh = New-Object -ComObject WScript.Shell
$sh.SendKeys('{ENTER}')
Start-Sleep -Milliseconds 1500
foreach ($e in $eds) {
  if ($e.Current.ClassName -like '*Log*') {
    $lvp = $null
    if ($e.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$lvp)) {
      Write-Output ("LOG: " + $lvp.Current.Value)
    }
  }
}
