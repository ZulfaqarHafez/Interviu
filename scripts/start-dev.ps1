param(
  [int]$ApiPort = 8000,
  [int]$WebPort = 3000,
  [int]$PortScanLimit = 40
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$logs = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

function Import-EnvFile {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) {
    return
  }
  Get-Content -LiteralPath $Path | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
      $name, $value = $line.Split("=", 2)
      $name = $name.Trim()
      $value = $value.Trim()
      if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
        $value = $value.Substring(1, $value.Length - 2)
      }
      if ($name -and -not [Environment]::GetEnvironmentVariable($name, "Process")) {
        Set-Item -Path "Env:$name" -Value $value
      }
    }
  }
}

Import-EnvFile -Path (Join-Path $root ".env")
Import-EnvFile -Path (Join-Path $root ".env.local")

function Test-PortInUse {
  param([int]$Port)
  $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  return $null -ne $connections
}

function Find-AvailablePort {
  param(
    [int]$StartPort,
    [int]$Limit
  )
  for ($offset = 0; $offset -lt $Limit; $offset++) {
    $candidate = $StartPort + $offset
    if (-not (Test-PortInUse -Port $candidate)) {
      return $candidate
    }
  }
  throw "No available port found from $StartPort through $($StartPort + $Limit - 1)."
}

function Wait-ForHttp {
  param(
    [string]$Url,
    [int]$Attempts = 30
  )
  for ($i = 0; $i -lt $Attempts; $i++) {
    try {
      $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
        return $true
      }
    } catch {
      Start-Sleep -Milliseconds 700
    }
  }
  return $false
}

$apiPortResolved = Find-AvailablePort -StartPort $ApiPort -Limit $PortScanLimit
$webPortResolved = Find-AvailablePort -StartPort $WebPort -Limit $PortScanLimit
$apiUrl = "http://127.0.0.1:$apiPortResolved"
$webUrl = "http://127.0.0.1:$webPortResolved"
$apiLog = Join-Path $logs "dev-api-$apiPortResolved.log"
$webLog = Join-Path $logs "dev-web-$webPortResolved.log"

$apiCommand = "python -m uvicorn assay_api.main:app --reload --app-dir apps/api --host 127.0.0.1 --port $apiPortResolved *> '$apiLog'"
$webCommand = "Set-Location '$root\apps\web'; `$env:NEXT_PUBLIC_API_BASE_URL='$apiUrl'; npx next dev --hostname 127.0.0.1 --port $webPortResolved *> '$webLog'"

$apiProcess = Start-Process -WindowStyle Hidden -PassThru -FilePath powershell -ArgumentList @(
  "-NoProfile",
  "-ExecutionPolicy",
  "Bypass",
  "-Command",
  $apiCommand
) -WorkingDirectory $root

if (-not (Wait-ForHttp -Url "$apiUrl/health")) {
  throw "API did not become healthy at $apiUrl. See $apiLog."
}

$webProcess = Start-Process -WindowStyle Hidden -PassThru -FilePath powershell -ArgumentList @(
  "-NoProfile",
  "-ExecutionPolicy",
  "Bypass",
  "-Command",
  $webCommand
) -WorkingDirectory $root

if (-not (Wait-ForHttp -Url $webUrl -Attempts 45)) {
  throw "Web app did not become reachable at $webUrl. See $webLog."
}

$state = [ordered]@{
  api_url = $apiUrl
  api_port = $apiPortResolved
  api_pid = $apiProcess.Id
  api_log = $apiLog
  web_url = $webUrl
  web_port = $webPortResolved
  web_pid = $webProcess.Id
  web_log = $webLog
  next_public_api_base_url = $apiUrl
  started_at = (Get-Date).ToUniversalTime().ToString("o")
}

$statePath = Join-Path $logs "dev-ports.json"
$state | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 -Path $statePath

Write-Host "Assay API: $apiUrl"
Write-Host "Assay web: $webUrl"
Write-Host "Dev state: $statePath"
