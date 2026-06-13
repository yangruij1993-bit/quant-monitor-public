# Start backend + frontend on Windows (PowerShell)
# Usage:
#   .\start.ps1          — start (opens two console windows)
#   .\start.ps1 stop     — stop
#   .\start.ps1 status   — check status

param(
    [Parameter(Position = 0)]
    [string]$Action = "start"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$PidFile = Join-Path $Root ".start-pids.txt"

function Test-Running {
    if (-not (Test-Path $PidFile)) { return $false }
    $pids = Get-Content $PidFile | Where-Object { $_ }
    foreach ($p in $pids) {
        if (Get-Process -Id $p -ErrorAction SilentlyContinue) { return $true }
    }
    return $false
}

function Start-Services {
    if (Test-Running) {
        Write-Host "Services already running. Use '.\start.ps1 stop' first." -ForegroundColor Yellow
        return
    }

    if (-not (Test-Path (Join-Path $Backend "app\main.py"))) {
        Write-Host "backend/app/main.py not found. Run this script from the project root." -ForegroundColor Red
        exit 1
    }
    if (-not (Test-Path (Join-Path $Frontend "package.json"))) {
        Write-Host "frontend/package.json not found. Run 'npm install' in frontend/ first." -ForegroundColor Red
        exit 1
    }

    $venvActivate = Join-Path $Backend ".venv\Scripts\Activate.ps1"
    $backendCmd = if (Test-Path $venvActivate) {
        ". '$venvActivate'; uvicorn app.main:app --host 0.0.0.0 --port 8012"
    } else {
        Write-Host "backend/.venv not found — using system python. (Run: py -m venv backend\.venv ; backend\.venv\Scripts\pip install -r backend\requirements.txt)" -ForegroundColor Yellow
        "uvicorn app.main:app --host 0.0.0.0 --port 8012"
    }

    Write-Host "Starting backend on http://localhost:8012 ..."
    $be = Start-Process powershell `
        -ArgumentList "-NoExit", "-Command", "Set-Location '$Backend'; $backendCmd" `
        -PassThru

    Write-Host "Starting frontend on http://localhost:3012 ..."
    $fe = Start-Process powershell `
        -ArgumentList "-NoExit", "-Command", "Set-Location '$Frontend'; npx next dev -p 3012" `
        -PassThru

    "$($be.Id)`n$($fe.Id)" | Set-Content $PidFile -Encoding ascii

    Write-Host ""
    Write-Host "Started asset-monitor:" -ForegroundColor Green
    Write-Host "  Backend PID $($be.Id):  http://localhost:8012"
    Write-Host "  Frontend PID $($fe.Id): http://localhost:3012"
    Write-Host ""
    Write-Host "Two console windows opened (logs visible there)."
    Write-Host "Stop:    .\start.ps1 stop"
    Write-Host "Status:  .\start.ps1 status"
}

function Stop-Services {
    if (-not (Test-Path $PidFile)) {
        Write-Host "Not running (no pid file)."
        return
    }
    $pids = Get-Content $PidFile | Where-Object { $_ }
    foreach ($p in $pids) {
        $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id $p -Force
            Write-Host "Stopped PID $p ($($proc.ProcessName))"
        }
    }
    Remove-Item $PidFile -Force
    Write-Host "Stopped."
}

function Show-Status {
    if (-not (Test-Running)) {
        Write-Host "Services are NOT running."
        return
    }
    $pids = Get-Content $PidFile | Where-Object { $_ }
    Write-Host "Running:" -ForegroundColor Green
    foreach ($p in $pids) {
        $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "  PID $p ($($proc.ProcessName))"
        }
    }
    try {
        $beCode = (Invoke-WebRequest -Uri "http://localhost:8012/api/v1/health" -UseBasicParsing -TimeoutSec 3).StatusCode
        Write-Host "  Backend health: $beCode"
    } catch {
        Write-Host "  Backend health: DOWN" -ForegroundColor Red
    }
    try {
        $feCode = (Invoke-WebRequest -Uri "http://localhost:3012" -UseBasicParsing -TimeoutSec 3).StatusCode
        Write-Host "  Frontend:       $feCode"
    } catch {
        Write-Host "  Frontend:       warming up or down" -ForegroundColor Yellow
    }
}

switch ($Action.ToLower()) {
    "start"  { Start-Services }
    "stop"   { Stop-Services }
    "status" { Show-Status }
    default  { Write-Host "Usage: .\start.ps1 {start|stop|status}" }
}
