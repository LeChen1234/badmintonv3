@echo off
chcp 65001 >nul
cd /d "d:\badminton\frontend"
where npm >nul 2>&1 || (
    echo [错误] 未找到 npm，请先安装 Node.js 并勾选 "Add to PATH"
    echo 下载: https://nodejs.org/
    pause
    exit /b 1
)
if not exist "node_modules" (
    echo 正在安装前端依赖...
    call npm install
)
echo ========================================
echo   前端启动中...
echo   本机访问: http://localhost:3000
echo   其他人通过你的 IP:3000 访问
echo ========================================
call npm run dev
pause
