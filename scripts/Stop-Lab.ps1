$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
    docker compose -f compose.yaml down --remove-orphans
    if ($LASTEXITCODE -ne 0) { throw 'Failed to remove lab.' }
    Write-Host 'Only this lab was stopped/removed.' -ForegroundColor Green
} finally { Pop-Location }
