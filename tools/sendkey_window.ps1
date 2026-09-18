param([int]$ProcId = 0, [string]$Keys = "A:200")
# Send gamepad-style key input to the mGBA window via SendInput-level
# keybd_event. Used by the C1 manual-handoff proof: AFTER the runner
# detaches from a paused handoff, input sent this way is PLAYER input
# (human or agent operating the emulator like a player) - it never
# touches the GDB stub, so it cannot be automation input.
# Keys format: comma-separated TOKEN:DURATION_MS, e.g. "DOWN:150,DOWN:150,A:300"
# Token map (mGBA default keyboard bindings):
#   A -> X, B -> Z, L -> A, R -> S, START -> Enter, SELECT -> Backspace,
#   UP/DOWN/LEFT/RIGHT -> arrows
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class KeySend {
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool IntersectRect(out RECT dst, ref RECT a, ref RECT b);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
}
'@
Add-Type -TypeDefinition 'using System.Runtime.InteropServices; public class DpiFixK { [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }'
[DpiFixK]::SetProcessDPIAware() | Out-Null
$root = [System.Windows.Automation.AutomationElement]::RootElement
$hwnd = [IntPtr]::Zero
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
foreach ($w in $wins) {
  if ($ProcId -eq 0 -or $w.Current.ProcessId -eq $ProcId) {
    if ($w.Current.ClassName -eq 'QGBA::Window') { $hwnd = [IntPtr]$w.Current.NativeWindowHandle }
  }
}
if ($hwnd -eq [IntPtr]::Zero) { Write-Output "no mGBA window for pid $ProcId"; exit 1 }
if ([KeySend]::IsIconic($hwnd)) { [KeySend]::ShowWindow($hwnd, 9) | Out-Null; Start-Sleep -Milliseconds 600 }
# Same focus discipline as capture_window.ps1: minimize visible windows
# overlapping the mGBA window so focus-steal prevention does not block us.
$mr = New-Object KeySend+RECT
[KeySend]::GetWindowRect($hwnd, [ref]$mr) | Out-Null
foreach ($w in $wins) {
  $wh = [IntPtr]$w.Current.NativeWindowHandle
  if ($wh -eq [IntPtr]::Zero -or $wh -eq $hwnd) { continue }
  if ($w.Current.ClassName -eq 'Shell_TrayWnd') { continue }
  if (-not [KeySend]::IsWindowVisible($wh)) { continue }
  if ([KeySend]::IsIconic($wh)) { continue }
  $wr = New-Object KeySend+RECT
  if (-not [KeySend]::GetWindowRect($wh, [ref]$wr)) { continue }
  if (($wr.R - $wr.L) -le 0 -or ($wr.B - $wr.T) -le 0) { continue }
  $ix = New-Object KeySend+RECT
  if ([KeySend]::IntersectRect([ref]$ix, [ref]$mr, [ref]$wr)) {
    [KeySend]::ShowWindow($wh, 6) | Out-Null
  }
}
Start-Sleep -Milliseconds 700
$fg = [KeySend]::SetForegroundWindow($hwnd)
Start-Sleep -Milliseconds 400
$map = @{ A = 0x58; B = 0x5A; L = 0x41; R = 0x53; START = 0x0D; SELECT = 0x08;
          UP = 0x26; DOWN = 0x28; LEFT = 0x25; RIGHT = 0x27 }
$sent = 0
foreach ($tok in $Keys -split ",") {
  $parts = $tok.Trim() -split ":"
  $name = $parts[0].ToUpper()
  $dur = if ($parts.Count -gt 1) { [int]$parts[1] } else { 200 }
  if (-not $map.ContainsKey($name)) { Write-Output "unknown key $name"; exit 1 }
  $vk = [byte]$map[$name]
  [KeySend]::keybd_event($vk, 0, 0, [UIntPtr]::Zero)      # key down
  Start-Sleep -Milliseconds $dur
  [KeySend]::keybd_event($vk, 0, 2, [UIntPtr]::Zero)      # KEYEVENTF_KEYUP
  $sent++
  Start-Sleep -Milliseconds 120
}
Write-Output "sent $Keys (foreground=$fg, window pid $ProcId)"
