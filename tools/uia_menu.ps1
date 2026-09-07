param([int]$ProcId = 101912, [string]$MenuName = "Tools")
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$procCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $ProcId)
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $procCond)
$main = $wins.Item(0)
$main.SetFocus()
$mbCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::MenuBar)
$mbar = $main.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $mbCond)
$miCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::MenuItem)
$mits = $mbar.FindAll([System.Windows.Automation.TreeScope]::Children, $miCond)
$target = $null
foreach ($it in $mits) { if ($it.Current.Name -eq $MenuName) { $target = $it } }
$exp = $null
if ($target.TryGetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern, [ref]$exp)) { $exp.Expand() }
Start-Sleep -Milliseconds 600
# enumerate whole subtree under the Tools menuitem
$all = $target.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
Write-Output ("subtree els: " + $all.Count)
foreach ($el in $all) {
  $n = $el.Current.Name
  if ($n -and $n.Length -gt 0) {
    Write-Output ("  '" + $n + "' " + $el.Current.ControlType.ProgrammaticName)
  }
}
