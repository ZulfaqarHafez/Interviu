param(
  [int]$Port = 8080
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Set-Location $root
python -m uvicorn examples.http_candidate.server:app --host 127.0.0.1 --port $Port
