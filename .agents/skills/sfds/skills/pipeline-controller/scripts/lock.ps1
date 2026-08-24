param(
  [Parameter(Mandatory=$true)][ValidateSet("status","acquire","release","check")][string]$Action,
  [string]$TaskId = "",
  [string]$LockPath = ""
)
if (-not $LockPath) { $LockPath = Join-Path (Get-Location) ".pipeline\lock" }
switch ($Action) {
  "status"   { if (Test-Path $LockPath) { Get-Content $LockPath } else { "FREE" } }
  "check"    { if (Test-Path $LockPath) { "LOCKED" } else { "FREE" } }
  "acquire"  {
    if (Test-Path $LockPath) { "LOCKED"; exit 1 }
    Set-Content -Path $LockPath -Value ("$TaskId|" + (Get-Date -Format o))
    "ACQUIRED $TaskId"
  }
  "release"  {
    if (Test-Path $LockPath) { Remove-Item $LockPath; "RELEASED" } else { "NOT_LOCKED"; exit 1 }
  }
}
