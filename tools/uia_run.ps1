param([string]$Code = 'print("hello-from-editor")')
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Write-Output "step1: find scripting window"
$root = [System.Windows.Automation.AutomationElement]::RootElement
$procCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, 101912)
$sw = $null
foreach ($w in $root.FindAll([System.Windows.Automation.TreeScope]::Children, $procCond)) {
  if ($w.Current.Name -eq 'Scripting') { $sw = $w }
}
if (-not $sw) { Write-Output "no scripting window"; exit 1 }
Write-Output "step2: find editor + run button"
$all = $sw.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
$editor = $null; $runBtn = $null; $lineEdit = $null
foreach ($el in $all) {
  $cl = $el.Current.ClassName
  if ($cl -eq 'QPlainTextEdit') { $editor = $el }
  elseif ($cl -eq 'QLineEdit') { $lineEdit = $el }
  elseif ($el.Current.ControlType -eq [System.Windows.Automation.ControlType]::Button -and $el.Current.Name -eq 'Run') { $runBtn = $el }
}
Write-Output ("editor=" + [bool]$editor + " run=" + [bool]$runBtn + " line=" + [bool]$lineEdit)
if ($editor) {
  Write-Output "step3: set editor text"
  $vp = $null
  if ($editor.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$vp)) {
    $vp.SetValue($Code)
    Write-Output "set via ValuePattern"
  } else {
    Write-Output "no value pattern on editor - trying legacy"
  }
}
if ($runBtn) {
  Write-Output "step4: click Run"
  $inv = $null
  if ($runBtn.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$inv)) {
    $inv.Invoke()
    Write-Output "invoked Run"
  }
}
Start-Sleep -Milliseconds 2000
Write-Output "step5: read log"
foreach ($el in $all) {
  if ($el.Current.ClassName -like '*Log*') {
    $lvp = $null
    if ($el.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$lvp)) {
      $v = $lvp.Current.Value
      if ($v) { Write-Output ("LOG: " + $v) }
    }
  }
}
Write-Output "done"
