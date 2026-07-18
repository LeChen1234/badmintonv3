# 启动后端与前端（依赖已安装后使用）
# 在项目根目录执行: .\scripts\run.ps1

$ProjectRoot = if ($PSScriptRoot) { Join-Path $PSScriptRoot ".." } else { (Get-Location).Path }
$ProjectRoot = (Resolve-Path $ProjectRoot).Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$BackendPath = Join-Path $ProjectRoot "backend"
$FrontendPath = Join-Path $ProjectRoot "frontend"
$ModelSource = Join-Path $ProjectRoot "models\yolov8n-pose.pt"
$ModelTarget = Join-Path $ProjectRoot "data\models\yolov8n-pose.pt"

if (-not (Test-Path $VenvPython)) {
    Write-Host "未找到虚拟环境，请先运行: .\scripts\install_and_run.ps1" -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot "data"), (Join-Path $ProjectRoot "data\uploads"), (Join-Path $ProjectRoot "data\exports"), (Join-Path $ProjectRoot "data\models") | Out-Null
if ((-not (Test-Path $ModelTarget)) -and (Test-Path $ModelSource)) {
    Copy-Item -Path $ModelSource -Destination $ModelTarget -Force
}

Write-Host "启动后端 (http://localhost:8000) ..." -ForegroundColor Cyan
Start-Process -FilePath $VenvPython -ArgumentList "-m","uvicorn","app.main:app","--reload","--host","0.0.0.0","--port","8000" -WorkingDirectory $BackendPath -WindowStyle Normal

Start-Sleep -Seconds 2
Write-Host "启动前端 (http://localhost:3000) ..." -ForegroundColor Cyan
Start-Process -FilePath "npm" -ArgumentList "run","dev" -WorkingDirectory $FrontendPath -WindowStyle Normal

Write-Host "`n后端与前端已在独立窗口启动。访问: 前端 http://localhost:3000  后端 http://localhost:8000/api/health" -ForegroundColor Green
