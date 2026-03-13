@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"
set "VENV=%ROOT%\.venv"
set "PY=%VENV%\Scripts\python.exe"

echo ========================================
echo   Project root: %ROOT%
echo ========================================

if not exist "%BACKEND%\requirements.txt" (
    echo [ERROR] backend\requirements.txt not found.
    pause
    exit /b 1
)
if not exist "%FRONTEND%\package.json" (
    echo [ERROR] frontend\package.json not found.
    pause
    exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm not found on PATH.
    pause
    exit /b 1
)

if not exist "%PY%" (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python not found on PATH.
        pause
        exit /b 1
    )
    echo [1/4] Creating virtual environment...
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [1/4] Using existing virtual environment.
)

for /f %%v in ('%PY% -c "import sys; print(sys.version_info[0]*100+sys.version_info[1])"') do set "PYVER=%%v"
if not defined PYVER (
    echo [ERROR] Failed to detect Python version in .venv.
    pause
    exit /b 1
)
if %PYVER% LSS 309 (
    echo [ERROR] .venv Python is older than 3.9. Recreate .venv and retry.
    pause
    exit /b 1
)

echo [2/4] Installing backend dependencies...
"%PY%" -m pip install -r "%BACKEND%\requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo [ERROR] Backend dependency installation failed.
    pause
    exit /b 1
)

echo [3/4] Installing frontend dependencies...
pushd "%FRONTEND%"
if not exist "node_modules" (
    call npm install
) else (
    echo node_modules already exists, skipping npm install.
)
if errorlevel 1 (
    popd
    echo [ERROR] Frontend dependency installation failed.
    pause
    exit /b 1
)
popd

if not exist "%ROOT%\data" mkdir "%ROOT%\data"
if not exist "%ROOT%\data\uploads" mkdir "%ROOT%\data\uploads"
if not exist "%ROOT%\data\exports" mkdir "%ROOT%\data\exports"

if not exist "%ROOT%\run_backend.bat" (
    echo [ERROR] run_backend.bat not found.
    pause
    exit /b 1
)
if not exist "%ROOT%\run_frontend.bat" (
    echo [ERROR] run_frontend.bat not found.
    pause
    exit /b 1
)

echo [4/4] Starting backend and frontend...
start "backend-8000" /D "%ROOT%" run_backend.bat
timeout /t 3 /nobreak >nul
start "frontend-3000" /D "%ROOT%" run_frontend.bat

echo.
echo Frontend: http://localhost:3000
echo Backend : http://localhost:8000/api/health
pause
