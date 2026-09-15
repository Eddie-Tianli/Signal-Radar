param([switch]$CheckOnly, [switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
$backend = Join-Path $PSScriptRoot 'backend'
$frontend = Join-Path $PSScriptRoot 'frontend'
$python = Join-Path $backend '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Missing backend virtual environment. Run: cd backend; python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements-dev.txt' }
if (-not (Test-Path -LiteralPath (Join-Path $backend '.env'))) { throw 'Missing backend/.env. Copy backend/.env.example to backend/.env and configure local database credentials.' }
if (-not (Test-Path -LiteralPath (Join-Path $frontend 'node_modules'))) { throw 'Missing frontend/node_modules. Run npm install from frontend/.' }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Node.js is missing from PATH. Install Node.js and reopen PowerShell.' }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw 'npm is missing from PATH. Check your Node.js installation.' }
Push-Location $backend
try {
    & $python -m app.local_runtime --check
    if ($LASTEXITCODE -ne 0) { throw 'Preflight failed. Resolve the message above, then retry.' }
} finally { Pop-Location }
if ($CheckOnly) { return }
if (-not $SkipBuild) {
    Push-Location $frontend
    try {
        & npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed. Inspect the build output above.' }
    } finally { Pop-Location }
}
if (-not (Test-Path -LiteralPath (Join-Path $frontend '.next\BUILD_ID'))) { throw 'Production build missing. Run this script without -SkipBuild.' }
Push-Location $backend
try {
    Write-Host 'Starting SignalRadar. Keep this terminal open; press Ctrl+C for graceful shutdown.'
    & $python -m app.local_runtime
    if ($LASTEXITCODE -ne 0) { throw 'SignalRadar stopped unexpectedly. Check logs/ for details.' }
} finally { Pop-Location }
