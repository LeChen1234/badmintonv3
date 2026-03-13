@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "FRONTEND=%ROOT%\frontend"

if not exist "%FRONTEND%\package.json" (
    echo [ERROR] frontend\package.json not found.
    pause
    exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm not found. Install Node.js and enable Add to PATH.
    pause
    exit /b 1
)

pushd "%FRONTEND%"
if not exist "node_modules" (
    echo Installing frontend dependencies...
    call npm install
    if errorlevel 1 (
        popd
        echo [ERROR] Frontend dependency installation failed.
        pause
        exit /b 1
    )
)

echo ========================================
echo   Frontend starting: http://localhost:3000
echo ========================================
call npm run dev
popd
pause
