param([Parameter(Mandatory=$true)][ValidateRange(1,2147483647)][int]$ProcId)
# Save slot 2 only after verifying the foreground window belongs to our session.
$ErrorActionPreference = 'Stop'
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class OwnedState {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint p);
  [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
  [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool attach);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int command);
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
}
'@
$process = Get-Process -Id $ProcId
$window = $process.MainWindowHandle
if ($window -eq [IntPtr]::Zero -or $process.ProcessName -ne 'mGBA') { throw 'No owned mGBA window' }
[uint32]$windowOwner = 0
[void][OwnedState]::GetWindowThreadProcessId($window, [ref]$windowOwner)
if ($windowOwner -ne $ProcId) { throw 'Window ownership mismatch' }
[uint32]$foregroundOwner = 0
$foregroundThread = [OwnedState]::GetWindowThreadProcessId([OwnedState]::GetForegroundWindow(), [ref]$foregroundOwner)
$thread = [OwnedState]::GetCurrentThreadId()
$attached = $false
try {
  if ($thread -ne $foregroundThread -and $foregroundThread -ne 0) {
    $attached = [OwnedState]::AttachThreadInput($thread, $foregroundThread, $true)
  }
  [void][OwnedState]::ShowWindow($window, 9)
  [void][OwnedState]::BringWindowToTop($window)
  [void][OwnedState]::SetForegroundWindow($window)
  Start-Sleep -Milliseconds 400
  if ([OwnedState]::GetForegroundWindow() -ne $window) { throw 'Owned window did not gain foreground; no keys sent' }
  try {
    [OwnedState]::keybd_event(0x10, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 60
    if ([OwnedState]::GetForegroundWindow() -ne $window) { throw 'Foreground changed before save; no function key sent' }
    [OwnedState]::keybd_event(0x71, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 60
  } finally {
    [OwnedState]::keybd_event(0x71, 0, 2, [UIntPtr]::Zero)
    [OwnedState]::keybd_event(0x10, 0, 2, [UIntPtr]::Zero)
  }
  @{pid=$ProcId; hwnd=$window.ToInt64(); foreground_verified=$true; combo='Shift+F2'} | ConvertTo-Json -Compress
} finally {
  if ($attached) { [void][OwnedState]::AttachThreadInput($thread, $foregroundThread, $false) }
}
