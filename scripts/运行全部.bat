@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\..") do set "ROOT=%%~fI"
set "VENV=%ROOT%\.venv"
set "PYTHON=%VENV%\Scripts\python.exe"
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"
set "MODEL_SOURCE=%ROOT%\models\yolov8n-pose.pt"
set "MODEL_TARGET=%ROOT%\data\models\yolov8n-pose.pt"

cd /d "%ROOT%"
echo ========================================
echo   依赖与运行目录: %ROOT%
echo ========================================

:: 1) 后端虚拟环境与依赖（全部在项目目录）
if not exist "%PYTHON%" (
    echo [1/4] 在项目目录创建 Python 虚拟环境...
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo [错误] 未找到 Python，请安装 Python 3.10+ 并勾选 Add to PATH
        pause
        exit /b 1
    )
) else (
    echo [1/4] 使用已有虚拟环境 %VENV%
)

echo [2/4] 安装后端依赖到项目目录...
"%PYTHON%" -m pip install -r "%BACKEND%\requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo [错误] 后端依赖安装失败
    pause
    exit /b 1
)

:: 2) 前端依赖（node_modules 在项目 frontend 目录）
where npm >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 npm，请安装 Node.js 并勾选 Add to PATH
    pause
    exit /b 1
)

echo [3/4] 安装前端依赖到项目目录...
cd /d "%FRONTEND%"
if not exist "node_modules" (
    call npm install
) else (
    echo 前端 node_modules 已存在，跳过安装
)
cd /d "%ROOT%"

:: 3) 创建数据目录
if not exist "%ROOT%\data" mkdir "%ROOT%\data"
if not exist "%ROOT%\data\uploads" mkdir "%ROOT%\data\uploads"
if not exist "%ROOT%\data\exports" mkdir "%ROOT%\data\exports"
if not exist "%ROOT%\data\models" mkdir "%ROOT%\data\models"
if not exist "%MODEL_TARGET%" (
    if exist "%MODEL_SOURCE%" (
        echo 复制本地 YOLO 姿态模型到 data\models...
        copy /Y "%MODEL_SOURCE%" "%MODEL_TARGET%" >nul
        if errorlevel 1 (
            echo [错误] 复制 YOLO 姿态模型失败
            pause
            exit /b 1
        )
    )
)

echo [4/4] 启动后端与前端...
start "后端-8000" /D "%SCRIPT_DIR%" "%SCRIPT_DIR%\run_backend.bat"
timeout /t 3 /nobreak >nul
start "前端-3000" /D "%SCRIPT_DIR%" "%SCRIPT_DIR%\run_frontend.bat"

echo.
echo ========================================
echo   已启动两个窗口：
echo   - 本机访问: http://localhost:3000
echo   - 后端 API: http://localhost:8000
echo ========================================
for /f "tokens=2 delims=:" %%a in ('ipconfig 2^>nul ^| findstr /c:"IPv4"') do (
  for /f "tokens=2" %%b in ("%%a") do (
    echo   局域网其他人访问: http://%%b:3000
    echo   将上面地址发给同事/同学，同一 WiFi 下即可打开
    goto :done_ip
  )
)
:done_ip
echo ========================================
echo   依赖均在 %ROOT%（保持本窗口不关）
echo ========================================
pause
