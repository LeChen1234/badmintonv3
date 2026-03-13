@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "BACKEND=%ROOT%\backend"
set "PYTHON=%ROOT%\.venv\Scripts\python.exe"

if not exist "%BACKEND%\alembic.ini" (
    echo [ERROR] backend\alembic.ini not found.
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

pushd "%BACKEND%"
echo [1/2] Running database migration...
"%PYTHON%" -m alembic upgrade head
if errorlevel 1 (
    echo [WARN] alembic upgrade failed. Trying alembic stamp head...
    "%PYTHON%" -m alembic stamp head
    if errorlevel 1 (
        popd
        echo [ERROR] Migration/stamp failed.
        pause
        exit /b 1
    )
)

echo.
echo [2/2] Starting backend...
"%PYTHON%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
popd
pause
