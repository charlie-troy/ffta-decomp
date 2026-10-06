param([int]$ProcId = 0, [string]$Combo = "Shift+F1")
# Variant of sendkey_window.ps1 that sends MODIFIER+KEY combos (VK codes)
# to the mGBA window. Used to discover/dispatch mGBA save-state hotkeys
# without the (dead) Lua console. Focus discipline identical to the C1
# sender: restore/foreground the QGBA window first.
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class KeyHot {
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
'@
Add-Type -TypeDefinition 'using System.Runtime.InteropServices; public class DpiFixH { [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }'
[DpiFixH]::SetProcessDPIAware() | Out-Null
$root = [System.Windows.Automation.AutomationElement]::RootElement
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
$hwnd = [IntPtr]::Zero
foreach ($w in $wins) {
  if (($ProcId -eq 0 -or $w.Current.ProcessId -eq $ProcId) -and $w.Current.ClassName -eq 'QGBA::Window') {
    $hwnd = [IntPtr]$w.Current.NativeWindowHandle
  }
}
if ($hwnd -eq [IntPtr]::Zero) { Write-Output "no mGBA window for pid $ProcId"; exit 1 }
if ([KeyHot]::IsIconic($hwnd)) { [KeyHot]::ShowWindow($hwnd, 9) | Out-Null; Start-Sleep -Milliseconds 500 }
[KeyHot]::SetForegroundWindow($hwnd) | Out-Null
Start-Sleep -Milliseconds 400
$vkmap = @{ 'CTRL' = 0x11; 'SHIFT' = 0x10; 'ALT' = 0x12
            'F1' = 0x70; 'F2' = 0x71; 'F3' = 0x72; 'F4' = 0x73
            'F5' = 0x74; 'F6' = 0x75; 'F7' = 0x76; 'F8' = 0x77
            'F9' = 0x78; 'F10' = 0x79; 'F11' = 0x7A; 'F12' = 0x7B
            'S' = 0x53; 'O' = 0x4F; 'L' = 0x4C; 'P' = 0x50 }
$parts = $Combo -split '\+'
$codes = @()
foreach ($p in $parts) { $k = $p.Trim().ToUpper(); if (-not $vkmap.ContainsKey($k)) { Write-Output "unknown key $k"; exit 1 }; $codes += [byte]$vkmap[$k] }
foreach ($c in $codes) { [KeyHot]::keybd_event($c, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 60 }
$rev = New-Object System.Collections.ArrayList
foreach ($c in $codes) { [void]$rev.Add($c) }
$rev.Reverse()
foreach ($c in $rev) { [KeyHot]::keybd_event($c, 0, 2, [UIntPtr]::Zero); Start-Sleep -Milliseconds 60 }
Write-Output "sent $Combo (pid=$ProcId)"
