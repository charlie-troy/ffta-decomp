Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$procCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, 101912)
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $procCond)
foreach ($w in $wins) {
  if ($w.Current.Name -eq 'Scripting') {
    Write-Output ("SCRIPTING WIN hwnd=" + $w.Current.NativeWindowHandle)
    $all = $w.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
    Write-Output ("els: " + $all.Count)
    foreach ($el in $all) {
      $n = $el.Current.Name
      $ct = $el.Current.ControlType.ProgrammaticName
      $cl = $el.Current.ClassName
      Write-Output ("  '" + $n + "' " + $ct + " class=" + $cl)
    }
  }
}
