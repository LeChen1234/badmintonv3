@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\..") do set "ROOT=%%~fI"
set "BACKEND=%ROOT%\backend"
set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
set "MODEL_SOURCE=%ROOT%\models\yolov8n-pose.pt"
set "MODEL_TARGET=%ROOT%\data\models\yolov8n-pose.pt"

if not exist "%BACKEND%\app\main.py" (
    echo [ERROR] backend\app\main.py not found.
    pause
    exit /b 1
)

if not exist "%PYTHON%" (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python not found on PATH.
        pause
        exit /b 1
    )
    set "PYTHON=python"
)

if not exist "%ROOT%\data" mkdir "%ROOT%\data"
if not exist "%ROOT%\data\models" mkdir "%ROOT%\data\models"
if not exist "%ROOT%\data\uploads" mkdir "%ROOT%\data\uploads"
if not exist "%ROOT%\data\exports" mkdir "%ROOT%\data\exports"
if not exist "%MODEL_TARGET%" (
    if exist "%MODEL_SOURCE%" (
        echo Copying local YOLO pose model into data\models...
        copy /Y "%MODEL_SOURCE%" "%MODEL_TARGET%" >nul
        if errorlevel 1 (
            echo [ERROR] Failed to copy YOLO pose model.
            pause
            exit /b 1
        )
    )
)

pushd "%BACKEND%"
"%PYTHON%" -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo Installing backend dependencies...
    "%PYTHON%" -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        popd
        echo [ERROR] Backend dependency installation failed.
        pause
        exit /b 1
    )
)

echo ========================================
echo   Backend starting: http://0.0.0.0:8000
echo   Health endpoint : http://localhost:8000/api/health
echo ========================================
"%PYTHON%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
popd
pause
