param([string]$Cmd = 'print("hi")', [int]$ProcId = 0)
# Send one command to the mGBA Scripting console (pid-parameterized A1
# bridge). The QLineEdit accepts the text via UIA ValuePattern; Enter is
# SendKeys with the console focused, so it fires only into that window.
# Focus discipline (c3_manual_layer lesson): minimize VISIBLE windows that
# overlap the console window first, or focus-steal prevention eats the
# SendKeys ENTER and the SetValue output never lands. Add-Type has a
# nontrivial startup cost (~10-20 s on this machine); keep the timeout
# generous on the caller side.
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32e {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
}
"@
$root = [System.Windows.Automation.AutomationElement]::RootElement
$procCond = New-Object System.Windows.Automation.PropertyCondition(
  [System.Windows.Automation.AutomationElement]::ProcessIdProperty, $ProcId)
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $procCond)
$sw = $null
foreach ($w in $wins) { if ($w.Current.Name -eq 'Scripting') { $sw = $w } }
if (-not $sw) { Write-Output "no scripting window"; exit 1 }
$hwnd = [IntPtr]$sw.Current.NativeWindowHandle
if ([Win32e]::IsIconic($hwnd)) { [Win32e]::ShowWindow($hwnd, 9) | Out-Null; Start-Sleep -Milliseconds 600 }
$cr = New-Object Win32e+RECT
[Win32e]::GetWindowRect($hwnd, [ref]$cr) | Out-Null
$allwins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
foreach ($w in $allwins) {
  $wh = [IntPtr]$w.Current.NativeWindowHandle
  if ($wh -eq [IntPtr]::Zero -or $wh -eq $hwnd) { continue }
  if ($w.Current.ClassName -eq 'Shell_TrayWnd') { continue }
  if (-not [Win32e]::IsWindowVisible($wh)) { continue }
  if ([Win32e]::IsIconic($wh)) { continue }
  $wr = New-Object Win32e+RECT
  if (-not [Win32e]::GetWindowRect($wh, [ref]$wr)) { continue }
  if (($wr.R - $wr.L) -le 0 -or ($wr.B - $wr.T) -le 0) { continue }
  $overlap = ($wr.L -lt $cr.R -and $wr.R -gt $cr.L -and $wr.T -lt $cr.B -and $wr.B -gt $cr.T)
  if ($overlap) { [Win32e]::ShowWindow($wh, 6) | Out-Null }
}
Start-Sleep -Milliseconds 500
[Win32e]::SetForegroundWindow($hwnd) | Out-Null
Start-Sleep -Milliseconds 300
$edCond = New-Object System.Windows.Automation.PropertyCondition(
  [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
  [System.Windows.Automation.ControlType]::Edit)
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
