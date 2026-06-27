$ErrorActionPreference = "Stop"

python -m pip install -r apps/api/requirements-dev.txt

$traceRazorPath = "C:\Users\zulfa\TraceRazor"
if (Test-Path $traceRazorPath) {
  python -m pip install -e $traceRazorPath
} else {
  Write-Warning "TraceRazor checkout not found at $traceRazorPath. Falling back to PyPI package."
  python -m pip install "tracerazor>=1.0.3"
}

npm install
