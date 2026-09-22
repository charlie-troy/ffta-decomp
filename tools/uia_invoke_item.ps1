param([int]$ProcId = 0, [string]$MenuName = "Emulation",
      [string]$ItemName = "Fast forward speed", [int]$ItemIndex = 1)
# Invoke a menu item in mGBA's Win32 menu bar (lazy: only exists while the
# menu is expanded, via ExpandCollapsePattern - no SendKeys, no focus race).
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$cond = New-Object System.Windows.Automation.PropertyCondition(
  [System.Windows.Automation.AutomationElement]::ProcessIdProperty, $ProcId)
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $cond)
$main = $null
foreach ($w in $wins) { if ($w.Current.ClassName -eq 'QGBA::Window') { $main = $w } }
if (-not $main) {
  # pid 0 ("any mGBA"): fall back to a class scan over all top windows
  if ($ProcId -eq 0) {
    $all = $root.FindAll([System.Windows.Automation.TreeScope]::Children,
      [System.Windows.Automation.Condition]::TrueCondition)
    foreach ($w in $all) { if ($w.Current.ClassName -eq 'QGBA::Window') { $main = $w; break } }
  }
}
if (-not $main) { Write-Output "no-main-window"; exit 1 }
$main.SetFocus()
Start-Sleep -Milliseconds 200
$mbCond = New-Object System.Windows.Automation.PropertyCondition(
  [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
  [System.Windows.Automation.ControlType]::MenuBar)
$mbar = $main.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $mbCond)
$miCond = New-Object System.Windows.Automation.PropertyCondition(
  [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
  [System.Windows.Automation.ControlType]::MenuItem)
$menus = $mbar.FindAll([System.Windows.Automation.TreeScope]::Children, $miCond)
$target = $null
foreach ($m in $menus) { if ($m.Current.Name -eq $MenuName) { $target = $m } }
if (-not $target) { Write-Output "menu-not-found:$MenuName"; exit 1 }
$exp = $null
if (-not $target.TryGetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern, [ref]$exp)) {
  Write-Output "no-expand-pattern"; exit 1 }
$exp.Expand()
Start-Sleep -Milliseconds 500
$items = $target.FindAll([System.Windows.Automation.TreeScope]::Descendants, $miCond)
$chosen = $null; $seen = 0
foreach ($it in $items) {
  $n = $it.Current.Name
  if ($n -and $n -eq $ItemName) {
    $seen += 1
    if ($seen -eq $ItemIndex) { $chosen = $it; break }
  }
}
if (-not $chosen) {
  $exp.Collapse()
  Write-Output ("item-not-found:" + $ItemName + "#" + $ItemIndex)
  exit 1
}
$inv = $null
if ($chosen.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$inv)) {
  $inv.Invoke(); Start-Sleep -Milliseconds 400
  # Collapse the menu: a submenu flyout (e.g. Fast forward speed) that
  # lingers expanded captures keyboard input — every later console call's
  # SendKeys ENTER lands in the dead menu and the bridge hangs (the A8
  # probe hung exactly once per menu invoke until this line existed).
  $exp.Collapse()
  Start-Sleep -Milliseconds 300
  Write-Output ("invoked:" + $MenuName + " > " + $ItemName + "#" + $ItemIndex)
} else {
  Write-Output "no-invoke-pattern"
}
