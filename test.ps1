param(
    [switch]$Stop,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$NodeModules = Join-Path $FrontendDir "node_modules"
$RuntimeDir = Join-Path $Root "data\test-runtime"
$PidFile = Join-Path $RuntimeDir "processes.json"
$BackendUrl = "http://127.0.0.1:8000"
$FrontendUrl = "http://127.0.0.1:3000"

function Stop-TestSystem {
    if (-not (Test-Path -LiteralPath $PidFile)) {
        Write-Host "No process started by test.ps1 was found." -ForegroundColor Yellow
        return
    }
    $saved = Get-Content -Raw -LiteralPath $PidFile | ConvertFrom-Json
    foreach ($id in @($saved.frontend, $saved.backend)) {
        if (-not $id) { continue }
        $process = Get-Process -Id ([int]$id) -ErrorAction SilentlyContinue
        if ($process) {
            # Stop descendants first (npm launches node/vite as child processes).
            $queue = @($process.Id)
            $tree = @()
            while ($queue.Count -gt 0) {
                $parent = $queue[0]
                $queue = @($queue | Select-Object -Skip 1)
                $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$parent" -ErrorAction SilentlyContinue)
                foreach ($child in $children) {
                    $queue += [int]$child.ProcessId
                    $tree += [int]$child.ProcessId
                }
            }
            [array]::Reverse($tree)
            foreach ($childId in $tree) {
                Stop-Process -Id $childId -Force -ErrorAction SilentlyContinue
            }
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            Write-Host "Stopped $($process.ProcessName) (PID $($process.Id))"
        }
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}

if ($Stop) {
    Stop-TestSystem
    exit 0
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python environment is missing. Run .\scripts\install_and_run.ps1 first."
}
if (-not (Test-Path -LiteralPath $NodeModules)) {
    throw "Frontend dependencies are missing. Run npm install in frontend first."
}

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

if (Test-Path -LiteralPath $PidFile) {
    Write-Host "Cleaning up the previous test run..." -ForegroundColor Yellow
    Stop-TestSystem
}

Write-Host "[1/4] Preparing isolated test database..." -ForegroundColor Cyan
$env:PYTHONPATH = $BackendDir
$env:SQLITE_DB_PATH = Join-Path $RuntimeDir "annotation-system-test.db"
$testDatabasePath = $env:SQLITE_DB_PATH
if (Test-Path -LiteralPath $testDatabasePath) {
    Remove-Item -LiteralPath $testDatabasePath -Force
}
$env:ENABLE_AUTO_BACKUP = "false"
$env:BOOTSTRAP_ADMIN_USERNAME = "admin"
$env:BOOTSTRAP_ADMIN_PASSWORD = "admin123"
# FastAPI creates the complete schema from the current models on first start.
# Keeping this database outside data/badminton.db protects real annotation data.

Write-Host "[2/4] Starting backend..." -ForegroundColor Cyan
$backendOut = Join-Path $RuntimeDir "backend.log"
$backendErr = Join-Path $RuntimeDir "backend-error.log"
$backend = Start-Process -FilePath $Python `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $BackendDir -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr

Write-Host "[3/4] Starting frontend..." -ForegroundColor Cyan
$frontendOut = Join-Path $RuntimeDir "frontend.log"
$frontendErr = Join-Path $RuntimeDir "frontend-error.log"
$frontend = Start-Process -FilePath "npm.cmd" `
    -ArgumentList "run", "dev", "--", "--host", "127.0.0.1", "--port", "3000", "--strictPort" `
    -WorkingDirectory $FrontendDir -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr

@{ backend = $backend.Id; frontend = $frontend.Id } |
    ConvertTo-Json | Set-Content -LiteralPath $PidFile -Encoding UTF8

function Wait-Url([string]$Url, [int]$Seconds = 60) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { return $true }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    return $false
}

Write-Host "[4/4] Waiting for the application..." -ForegroundColor Cyan
$backendReady = Wait-Url "$BackendUrl/api/health"
$frontendReady = Wait-Url $FrontendUrl
if (-not $backendReady -or -not $frontendReady) {
    Stop-TestSystem
    throw "Application startup failed. See logs in $RuntimeDir."
}

& $Python (Join-Path $Root "scripts\seed_test_demo.py")
if ($LASTEXITCODE -ne 0) {
    Stop-TestSystem
    throw "Test demo initialization failed."
}

Write-Host ""
Write-Host "Annotation system is ready: $FrontendUrl" -ForegroundColor Green
Write-Host "Test account: admin / admin123" -ForegroundColor Green
Write-Host "Stop it with: .\test.ps1 -Stop" -ForegroundColor DarkGray
Write-Host "Logs: $RuntimeDir" -ForegroundColor DarkGray

if (-not $NoBrowser) {
    Start-Process $FrontendUrl
}
