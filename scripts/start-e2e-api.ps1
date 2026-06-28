$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$appsDir = Join-Path $repoRoot "apps"
$apiDir = Join-Path $appsDir "api"
$dataDir = Join-Path $apiDir "data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$env:ASSAY_DISABLE_OPENAI = "1"
$env:ASSAY_DB_BACKEND = "sqlite"
$env:ASSAY_DB_PATH = Join-Path $dataDir "e2e-8010.db"
$env:SUPABASE_URL = " "
$env:SUPABASE_SERVICE_ROLE_KEY = " "
$env:ASSAY_RATE_LIMIT_ENABLED = "0"

Set-Location $repoRoot
python -m uvicorn assay_api.main:app --app-dir apps/api --host 127.0.0.1 --port 8010
