param(
  [Parameter(Mandatory=$true)][string]$Baseline,
  [Parameter(Mandatory=$true)][string]$Touches,
  [string]$Project = "."
)
$ErrorActionPreference = "Stop"
$paths = $Touches -split ';' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
if (-not $paths) { "ERROR: empty touches"; exit 1 }
Push-Location $Project
try {
  git rev-parse --git-dir *> $null
  if ($LASTEXITCODE -ne 0) { "ERROR: not a git repo"; exit 1 }
  $out = git diff "$Baseline..HEAD" -- $paths
  if ($LASTEXITCODE -ne 0) { "ERROR: git diff failed"; exit 1 }
  if ($out) { "CHANGED" } else { "UNCHANGED" }
} finally { Pop-Location }
