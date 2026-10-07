param(
  [Parameter(Mandatory=$true)][ValidateRange(1,2147483647)][int]$ProcId,
  [Parameter(Mandatory=$true)][ValidateSet('A','B','UP','DOWN','LEFT','RIGHT')][string]$Key,
  [ValidateRange(20,300)][int]$DurationMs = 100
)
# Manual-window proof helper. No input is sent unless owned focus is verified.
$ErrorActionPreference = 'Stop'
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class OwnedKey {
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
[void][OwnedKey]::GetWindowThreadProcessId($window, [ref]$windowOwner)
if ($windowOwner -ne $ProcId) { throw 'Window ownership mismatch' }
[uint32]$foregroundOwner = 0
$foregroundThread = [OwnedKey]::GetWindowThreadProcessId([OwnedKey]::GetForegroundWindow(), [ref]$foregroundOwner)
$thread = [OwnedKey]::GetCurrentThreadId()
$attached = $false
$map = @{A=0x58; B=0x5A; UP=0x26; DOWN=0x28; LEFT=0x25; RIGHT=0x27}
$vk = [byte]$map[$Key.ToUpper()]
try {
  if ($thread -ne $foregroundThread -and $foregroundThread -ne 0) {
    $attached = [OwnedKey]::AttachThreadInput($thread, $foregroundThread, $true)
  }
  [void][OwnedKey]::ShowWindow($window, 9)
  [void][OwnedKey]::BringWindowToTop($window)
  [void][OwnedKey]::SetForegroundWindow($window)
  Start-Sleep -Milliseconds 400
  if ([OwnedKey]::GetForegroundWindow() -ne $window) { throw 'Owned window did not gain foreground; no keys sent' }
  try {
    [OwnedKey]::keybd_event($vk, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds $DurationMs
  } finally {
    [OwnedKey]::keybd_event($vk, 0, 2, [UIntPtr]::Zero)
  }
  @{pid=$ProcId; hwnd=$window.ToInt64(); foreground_verified=$true; key=$Key; duration_ms=$DurationMs} | ConvertTo-Json -Compress
} finally {
  if ($attached) { [void][OwnedKey]::AttachThreadInput($thread, $foregroundThread, $false) }
}
