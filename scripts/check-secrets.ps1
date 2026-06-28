$ErrorActionPreference = "Stop"

$patterns = @(
  @{ Name = "OpenAI API key"; Regex = "sk-[A-Za-z0-9_-]{20,}" },
  @{ Name = "Supabase secret key"; Regex = "sb_secret_[A-Za-z0-9_-]+" },
  @{ Name = "Supabase personal access token"; Regex = "sbp_[A-Za-z0-9_-]+" },
  @{ Name = "Supabase service role JWT"; Regex = "SUPABASE_SERVICE_ROLE_KEY\s*=\s*`"?eyJ[A-Za-z0-9_-]{20,}" }
)

$binaryExtensions = @(".ico", ".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf")
$findings = New-Object System.Collections.Generic.List[string]

$files = git ls-files
foreach ($file in $files) {
  $extension = [System.IO.Path]::GetExtension($file).ToLowerInvariant()
  if ($binaryExtensions -contains $extension) {
    continue
  }
  if (-not (Test-Path -LiteralPath $file)) {
    continue
  }
  $content = Get-Content -LiteralPath $file -Raw -ErrorAction SilentlyContinue
  if ($null -eq $content) {
    continue
  }
  foreach ($pattern in $patterns) {
    if ($content -match $pattern.Regex) {
      $findings.Add("$file`: $($pattern.Name)")
    }
  }
}

if ($findings.Count -gt 0) {
  Write-Error ("Possible committed secret(s) detected:`n" + ($findings -join "`n"))
}

Write-Host "No tracked secret patterns found."
