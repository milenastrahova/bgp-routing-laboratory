# Publish the verified BGP Routing Laboratory into the owner's empty private GitHub repository.
# Windows 11 / PowerShell 5.1+; requires Git for Windows and interactive GitHub authentication.
# Changes only this project folder (.git) and the selected remote GitHub repository.
$ErrorActionPreference = 'Stop'
$RepoUrl = 'https://github.com/milenastrahova/bgp-routing-laboratory.git'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot

function Run-Git {
    & git @args
    if ($LASTEXITCODE -ne 0) { throw "Git command failed with exit code $LASTEXITCODE." }
}

Write-Host 'BGP Routing Laboratory | GitHub publisher' -ForegroundColor Cyan
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'Git for Windows is not installed. Install it from https://git-scm.com/downloads/win or use GitHub Add file > Upload files.'
}
if (-not (Test-Path -LiteralPath '.\compose.yaml') -or -not (Test-Path -LiteralPath '.\scripts\labctl.py')) {
    throw 'Project files not found. Extract all ZIP contents into one folder and run this script from there.'
}

Write-Host 'Checking remote access (Git Credential Manager may open a browser sign-in)...'
$remoterefs = & git ls-remote $RepoUrl 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host ($remoterefs | Out-String)
    throw 'Unable to access the private GitHub repository. Sign in to GitHub in Git Credential Manager and retry.'
}
if (($remoterefs | Out-String).Trim()) {
    throw 'The GitHub repository is NOT empty. This script refuses to overwrite existing history. No push was attempted.'
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    Write-Host 'Running offline regression tests...' -ForegroundColor Cyan
    & py -3 -m unittest discover -s tests -q
    if ($LASTEXITCODE -ne 0) { throw 'Offline tests failed; no push attempted.' }
}

if (Test-Path -LiteralPath '.\.git') {
    $origin = (& git remote get-url origin 2>$null | Out-String).Trim()
    if ($origin -and $origin -ne $RepoUrl) { throw "Existing Git remote differs from target: $origin" }
} else {
    Run-Git init
}
Run-Git branch -M main
$origin = (& git remote get-url origin 2>$null | Out-String).Trim()
if (-not $origin) { Run-Git remote add origin $RepoUrl }

Run-Git add -A
$staged = (& git diff --cached --name-only | Out-String).Trim()
if (-not $staged) { throw 'No files staged; refusing to create an empty commit.' }
Write-Host 'Files staged for first commit:'
Write-Host $staged

# Use existing local Git identity, otherwise GitHub's noreply address, only for this commit.
$name = (& git config --get user.name 2>$null | Out-String).Trim()
$email = (& git config --get user.email 2>$null | Out-String).Trim()
if (-not $name) { $name = 'milenastrahova' }
if (-not $email) { $email = '305638469+milenastrahova@users.noreply.github.com' }
Run-Git -c "user.name=$name" -c "user.email=$email" commit -m 'Add verified four-AS FRRouting BGP routing laboratory'
Write-Host 'Pushing main into the EMPTY private repository...' -ForegroundColor Cyan
Run-Git push -u origin main
Write-Host ''
Write-Host 'SUCCESS: https://github.com/milenastrahova/bgp-routing-laboratory' -ForegroundColor Green
Write-Host 'The repository remains PRIVATE. Keep the raw artifacts folder uncommitted.'
