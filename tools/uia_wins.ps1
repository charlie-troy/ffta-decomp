param([int]$ProcId = 101912)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$procCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $ProcId)
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $procCond)
Write-Output ("windows: " + $wins.Count)
foreach ($w in $wins) {
  Write-Output ("WIN: '" + $w.Current.Name + "' class=" + $w.Current.ClassName + " hwnd=" + $w.Current.NativeWindowHandle)
}
