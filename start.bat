@echo off
setlocal

set ROOT=%~dp0

echo === TokReducer ===
echo.

REM Load .env if present
if exist "%ROOT%.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%ROOT%.env") do (
        set "%%A=%%B"
    )
    echo Loaded environment from .env
)

echo [1/3] Installing Python backend...
cd /d "%ROOT%backend\python"
pip install -e ".[api]" --quiet 2>nul || pip install --user -e ".[api]"

echo [2/3] Installing frontend dependencies...
cd /d "%ROOT%web"
call npm install --silent 2>nul || call npm install

echo [3/3] Starting services...
echo.
echo   Backend   -^> http://localhost:8080
echo   Dashboard -^> http://localhost:3000
echo   Proxy     -^> http://localhost:8080/v1/chat/completions
echo.

cd /d "%ROOT%backend\python"
start /b uvicorn tokreducer.api.server:app --host 0.0.0.0 --port 8080 --log-level info

cd /d "%ROOT%web"
start /b npx vite --port 3000 --host

echo Press Ctrl+C to stop.
pause >nul
