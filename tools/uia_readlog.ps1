Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$procCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, 101912)
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $procCond)
foreach ($w in $wins) {
  if ($w.Current.Name -eq 'Scripting') {
    $edCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Edit)
    $eds = $w.FindAll([System.Windows.Automation.TreeScope]::Descendants, $edCond)
    foreach ($e in $eds) {
      $vp = $null
      if ($e.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$vp)) {
        $v = $vp.Current.Value
        if ($v) { Write-Output ("[" + $e.Current.ClassName + "] " + $v.Substring(0, [Math]::Min(400, $v.Length))) }
      }
    }
  }
}
