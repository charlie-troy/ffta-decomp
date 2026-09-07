param([int]$ProcId = 101912)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$procCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $ProcId)
$sw = $null
foreach ($w in $root.FindAll([System.Windows.Automation.TreeScope]::Children, $procCond)) {
  if ($w.Current.ClassName -eq 'QGBA::ScriptingView') { $sw = $w }
}
if (-not $sw) { Write-Output "no scripting window"; exit 1 }
$mbCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::MenuBar)
$mbar = $sw.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $mbCond)
$miCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::MenuItem)
$mits = $mbar.FindAll([System.Windows.Automation.TreeScope]::Children, $miCond)
foreach ($it in $mits) { Write-Output ("MENU: '" + $it.Current.Name + "'") }
$file = $null
foreach ($it in $mits) { if ($it.Current.Name -eq 'File') { $file = $it } }
if ($file) {
  $exp = $null
  if ($file.TryGetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern, [ref]$exp)) {
    $exp.Expand()
    Start-Sleep -Milliseconds 600
    $all = $file.FindAll([System.Windows.Automation.TreeScope]::Descendants, $miCond)
    foreach ($el in $all) { Write-Output ("  ITEM: '" + $el.Current.Name + "'") }
  }
}
