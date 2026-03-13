# Install dependencies and initialize the project.
# Usage: run from project root in PowerShell: .\scripts\install_and_run.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = if ($PSScriptRoot) { Join-Path $PSScriptRoot ".." } else { (Get-Location).Path }
$ProjectRoot = (Resolve-Path $ProjectRoot).Path
$VenvPath = Join-Path $ProjectRoot ".venv"
$BackendPath = Join-Path $ProjectRoot "backend"
$FrontendPath = Join-Path $ProjectRoot "frontend"

# Keep npm cache on local disk
$NpmCache = "D:\npm-cache"
if (-not (Test-Path $NpmCache)) { New-Item -ItemType Directory -Path $NpmCache -Force | Out-Null }
$env:NPM_CONFIG_CACHE = $NpmCache

Write-Host "=== 项目根目录: $ProjectRoot ===" -ForegroundColor Cyan

# ---------- 1. Python virtual environment ----------
if (-not (Test-Path (Join-Path $VenvPath "Scripts\python.exe"))) {
    Write-Host "`n[1/4] 创建 Python 虚拟环境到 $VenvPath ..." -ForegroundColor Yellow
    Set-Location $ProjectRoot
    python -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) { throw "创建 venv 失败" }
}
$Py = Join-Path $VenvPath "Scripts\python.exe"
$Pip = Join-Path $VenvPath "Scripts\pip.exe"

Write-Host "`n[2/4] 安装 Python 依赖（backend + scripts + ml-backend）..." -ForegroundColor Yellow
& $Pip install -q --upgrade pip
& $Pip install -q -r (Join-Path $ProjectRoot "backend\requirements.txt")
& $Pip install -q -r (Join-Path $ProjectRoot "scripts\requirements.txt")
& $Pip install -q -r (Join-Path $ProjectRoot "ml-backend\requirements.txt")
& $Pip install -q Pillow
Write-Host "Python 依赖安装完成." -ForegroundColor Green

# ---------- 2. Frontend dependencies ----------
Write-Host "`n[3/4] 安装前端依赖（npm cache: $NpmCache）..." -ForegroundColor Yellow
Set-Location $FrontendPath
npm install
if ($LASTEXITCODE -ne 0) { throw "npm install 失败" }
Write-Host "前端依赖安装完成." -ForegroundColor Green

# ---------- 3. Environment file ----------
if (-not (Test-Path (Join-Path $ProjectRoot ".env"))) {
    $envPath = Join-Path $ProjectRoot ".env"
    $content = Get-Content (Join-Path $ProjectRoot ".env.example") -Raw
    $content = $content -replace 'POSTGRES_HOST=postgres', 'POSTGRES_HOST=localhost' -replace 'REDIS_HOST=redis', 'REDIS_HOST=localhost' -replace 'LABEL_STUDIO_HOST=http://label-studio:8080', 'LABEL_STUDIO_HOST=http://localhost:8080' -replace 'ML_BACKEND_HOST=http://ml-backend:9090', 'ML_BACKEND_HOST=http://localhost:9090' -replace 'MINIO_ENDPOINT=minio:9000', 'MINIO_ENDPOINT=localhost:9000'
    Set-Content -Path $envPath -Value $content.TrimEnd()
    Write-Host "`n已生成 .env（已设为 localhost 便于本机连接）。请编辑 .env 设置 LABEL_STUDIO_API_KEY（Label Studio 启动后在设置中创建）。" -ForegroundColor Yellow
}

# ---------- 4. Database migration ----------
Write-Host "`n[4/4] 执行数据库迁移..." -ForegroundColor Yellow
Set-Location $BackendPath
$env:PYTHONPATH = $BackendPath
& $Py -m alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Host "alembic upgrade failed, trying to stamp current schema as head..." -ForegroundColor Yellow
    & $Py -m alembic stamp head
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Migration/stamp failed. Check backend requirements and .env configuration." -ForegroundColor Red
    }
}

Write-Host "`n=== 安装完成 ===" -ForegroundColor Green
Write-Host "启动后端: 在 $BackendPath 执行:  ..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
Write-Host "启动前端: 在 $FrontendPath 执行:  npm run dev"
Write-Host "然后访问: 管理前端 http://localhost:3000  后端 API http://localhost:8000/api/health" -ForegroundColor Cyan
