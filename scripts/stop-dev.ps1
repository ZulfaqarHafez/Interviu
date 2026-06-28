$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$statePath = Join-Path $root "logs\dev-ports.json"

function Get-ChildProcessIds {
  param([int]$ParentId)
  $children = @(Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $ParentId })
  foreach ($child in $children) {
    $child.ProcessId
    Get-ChildProcessIds -ParentId $child.ProcessId
  }
}

if (-not (Test-Path $statePath)) {
  Write-Host "No dev state found at $statePath."
  exit 0
}

$state = Get-Content $statePath | ConvertFrom-Json
$rootPids = @($state.api_pid, $state.web_pid) | Where-Object { $_ }
$allPids = @()

foreach ($pidValue in $rootPids) {
  $allPids += [int]$pidValue
  $allPids += Get-ChildProcessIds -ParentId ([int]$pidValue)
}

$allPids = @($allPids | Sort-Object -Unique)
foreach ($pidValue in $allPids) {
  Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
}

Remove-Item -Path $statePath -Force -ErrorAction SilentlyContinue
Write-Host "Stopped Assay dev processes."
