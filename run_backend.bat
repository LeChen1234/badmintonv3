@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "BACKEND=%ROOT%\backend"
set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
set "PIP_MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple"
set "PIP_OFFICIAL=https://pypi.org/simple"

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

for /f %%v in ('"%PYTHON%" -c "import sys; print(sys.version_info[0]*100+sys.version_info[1])"') do set "PYVER=%%v"
if not defined PYVER (
    echo [ERROR] Failed to detect Python version.
    pause
    exit /b 1
)
if %PYVER% LSS 309 (
    echo [ERROR] Python is older than 3.9. Please upgrade Python and recreate .venv.
    pause
    exit /b 1
)
if %PYVER% GEQ 313 (
    echo [INFO] Python 3.13+ detected. Installing a compatible mediapipe version from requirements.
)

pushd "%BACKEND%"
"%PYTHON%" -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo Installing backend dependencies...
    "%PYTHON%" -m pip install -r requirements.txt -i "%PIP_MIRROR%"
    if errorlevel 1 (
        echo [WARN] Mirror index failed, retrying with official PyPI...
        "%PYTHON%" -m pip install -r requirements.txt -i "%PIP_OFFICIAL%"
        if errorlevel 1 (
            popd
            echo [ERROR] Backend dependency installation failed.
            pause
            exit /b 1
        )
    )
)

echo ========================================
echo   Backend starting: http://0.0.0.0:8000
echo   Health endpoint : http://localhost:8000/api/health
echo ========================================
"%PYTHON%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
popd
pause
