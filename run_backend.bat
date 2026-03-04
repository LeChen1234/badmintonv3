@echo off
chcp 65001 >nul
cd /d "d:\badminton\backend"

:: 查找可用的 Python
if exist "d:\badminton\.venv\Scripts\python.exe" (
    set "PYTHON=d:\badminton\.venv\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        set "PYTHON=python"
    ) else (
        echo [错误] 未找到 Python，请先安装 Python 3.10+
        pause
        exit /b 1
    )
)

:: 安装依赖（如果缺少）
%PYTHON% -c "import fastapi" >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在安装后端依赖...
    %PYTHON% -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo ========================================
echo   后端启动中 http://0.0.0.0:8000
echo   数据库: SQLite (data/badminton.db)
echo   大模型标注: 可选 (默认关闭)
echo ========================================
%PYTHON% -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
