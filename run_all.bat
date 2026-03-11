@echo off
chcp 65001 >nul
cd /d "d:\badminton"
echo ========================================
echo   依赖与运行目录: D:\badminton
echo ========================================

:: 1) 后端虚拟环境与依赖（全部在 D 盘）
if not exist "d:\badminton\.venv\Scripts\python.exe" (
    echo [1/4] 在 D 盘创建 Python 虚拟环境...
    python -m venv "d:\badminton\.venv"
    if errorlevel 1 (
        echo [错误] 未找到 Python，请安装 Python 3.10+ 并勾选 Add to PATH
        pause
        exit /b 1
    )
) else (
    echo [1/4] 使用已有虚拟环境 D:\badminton\.venv
)

echo [2/4] 安装后端依赖到 D 盘...
"d:\badminton\.venv\Scripts\python.exe" -m pip install -r "d:\badminton\backend\requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo [错误] 后端依赖安装失败
    pause
    exit /b 1
)

:: 2) 前端依赖（node_modules 在 D:\badminton\frontend）
where npm >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 npm，请安装 Node.js 并勾选 Add to PATH
    pause
    exit /b 1
)

echo [3/4] 安装前端依赖到 D 盘...
cd /d "d:\badminton\frontend"
if not exist "node_modules" (
    call npm install
) else (
    echo 前端 node_modules 已存在，跳过安装
)
cd /d "d:\badminton"

:: 3) 创建数据目录
if not exist "d:\badminton\data" mkdir "d:\badminton\data"
if not exist "d:\badminton\data\uploads" mkdir "d:\badminton\data\uploads"
if not exist "d:\badminton\data\exports" mkdir "d:\badminton\data\exports"

echo [4/4] 启动后端与前端...
start "后端-8000" cmd /k "cd /d d:\badminton\backend && d:\badminton\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
timeout /t 3 /nobreak >nul
start "前端-3000" cmd /k "cd /d d:\badminton\frontend && npm run dev"

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
echo   依赖均在 D:\badminton（保持本窗口不关）
echo ========================================
pause
