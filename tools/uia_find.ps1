param([int]$ProcId = 101912, [string]$NameLike = "")
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$procCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $ProcId)
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $procCond)
foreach ($w in $wins) {
  $n = $w.Current.Name
  if (-not $NameLike -or $n -like "*$NameLike*" -or $w.Current.ClassName -like "*$NameLike*") {
    Write-Output ("WIN: '" + $n + "' class=" + $w.Current.ClassName + " hwnd=" + $w.Current.NativeWindowHandle)
  }
}
