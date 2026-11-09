$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (!(Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    $pyCmd = $null
    try {
        $testPy = & py -0 2>&1
        if ($LASTEXITCODE -eq 0) { $pyCmd = "py" }
    } catch {}

    if (-not $pyCmd) {
        if (Test-Path "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe") {
            $pyCmd = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
        } elseif (Test-Path "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe") {
            $pyCmd = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
        } elseif (Get-Command python -ErrorAction SilentlyContinue) {
            $pyCmd = "python"
        } else {
            $pyCmd = "python"
        }
    }
    & $pyCmd -m venv .venv
}

& ".venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
Write-Host ""
Write-Host "Starting DealRescue AI..." -ForegroundColor Green
Write-Host "Open http://127.0.0.1:8000" -ForegroundColor Yellow
& ".venv\Scripts\python.exe" -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
