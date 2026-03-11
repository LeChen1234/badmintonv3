@echo off
chcp 65001 >nul
cd /d "d:\badminton\backend"

echo [1/2] 执行数据库迁移...
"d:\badminton\.venv\Scripts\python.exe" -m alembic upgrade head
if errorlevel 1 (
    echo 迁移失败，请确认 PostgreSQL 已启动且 .env 中 POSTGRES_HOST=localhost
    pause
    exit /b 1
)

echo.
echo [2/2] 启动后端（请先关闭旧的后端窗口）...
"d:\badminton\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
