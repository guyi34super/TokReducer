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

echo [2.5/3] Rust compressor...
where cargo >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    cd /d "%ROOT%backend\rust"
    cargo build --release --features cli 2>nul
    if %ERRORLEVEL% EQU 0 (
        start /b target\release\tokreducer-cli.exe serve --port 8081
        set RUST_COMPRESSOR_URL=http://localhost:8081
        echo   Rust compressor -^> http://localhost:8081
    ) else (
        echo   Rust build skipped
    )
    cd /d "%ROOT%"
) else (
    echo   Rust not installed
)

echo [3/3] Starting services...
echo.
echo   Backend   -^> http://localhost:8080
echo   Dashboard -^> http://localhost:3000
echo   Proxy     -^> http://localhost:8080/v1/chat/completions
echo.

cd /d "%ROOT%backend\python"
set RUST_COMPRESSOR_URL=%RUST_COMPRESSOR_URL%
start /b uvicorn tokreducer.api.server:app --host 0.0.0.0 --port 8080 --log-level info

cd /d "%ROOT%web"
start /b npx vite --port 3000 --host

echo Press Ctrl+C to stop.
pause >nul
