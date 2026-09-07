param([int]$ProcId = 101912, [string]$Cmd = 'console:log("hello")')
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$procCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $ProcId)
$sw = $null
foreach ($w in $root.FindAll([System.Windows.Automation.TreeScope]::Children, $procCond)) {
  if ($w.Current.ClassName -eq 'QGBA::ScriptingView' -or $w.Current.Name -eq 'Scripting') { $sw = $w }
}
if (-not $sw) { Write-Output "no scripting window"; exit 1 }
$all = $sw.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
$lineEdit = $null; $log = $null; $btn = $null
foreach ($el in $all) {
  $cl = $el.Current.ClassName
  if ($cl -eq 'QLineEdit') { $lineEdit = $el }
  elseif ($cl -like '*Log*') { $log = $el }
  elseif ($el.Current.ControlType -eq [System.Windows.Automation.ControlType]::Button -and $el.Current.Name -eq 'Run') { $btn = $el }
}
if (-not $lineEdit) { Write-Output "no QLineEdit"; exit 1 }
$vp = $null
if ($lineEdit.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$vp)) {
  $vp.SetValue($Cmd)
  Write-Output "set"
} else { Write-Output "no vp"; exit 1 }
if ($btn) {
  $inv = $null
  if ($btn.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$inv)) { $inv.Invoke(); Write-Output "clicked Run" }
} else {
  $lineEdit.SetFocus()
  Start-Sleep -Milliseconds 200
  $sh = New-Object -ComObject WScript.Shell
  $sh.SendKeys('{ENTER}')
  Write-Output "sent Enter"
}
Start-Sleep -Milliseconds 1800
if ($log) {
  $lvp = $null
  if ($log.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$lvp)) {
    Write-Output ("LOG: " + $lvp.Current.Value)
  }
}
