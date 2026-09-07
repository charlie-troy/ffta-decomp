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
$all = $sw.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
Write-Output ("els: " + $all.Count)
foreach ($el in $all) {
  $n = $el.Current.Name; $ct = $el.Current.ControlType.ProgrammaticName; $cl = $el.Current.ClassName
  Write-Output ("  '" + $n + "' " + $ct + " class=" + $cl)
}
