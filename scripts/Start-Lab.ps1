$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
    docker compose -f compose.yaml config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Docker Compose configuration failed.' }
    docker compose -f compose.yaml up -d
    if ($LASTEXITCODE -ne 0) { throw 'Failed to launch lab.' }
    Write-Host 'Lab started. Run: py -3 .\scripts\labctl.py check' -ForegroundColor Green
} finally { Pop-Location }
