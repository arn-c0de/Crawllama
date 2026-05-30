@echo off
REM CrawlLama API Server - Windows
REM Runs the FastAPI server via uv (auto-syncs the environment + the `api` extra).

REM Cleanup problematic NUL file if it exists (Windows filesystem bug)
if exist "nul" del /F /Q "\\?\%CD%\nul" 2>NUL

where uv >NUL 2>NUL
if errorlevel 1 (
    echo ERROR: uv is not installed!
    echo Install it with: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 ^| iex"
    echo Then run setup.bat to provision the environment.
    echo.
    pause
    exit /b 1
)

echo ========================================
echo CrawlLama API Server
echo ========================================
echo Starting FastAPI server...
echo API Documentation: http://localhost:8000/docs
echo ReDoc: http://localhost:8000/redoc
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

REM --extra api ensures fastapi/uvicorn/starlette are present.
uv run --extra api python app.py

REM Keep window open if error occurred
if errorlevel 1 (
    echo.
    echo An error occurred. Press any key to exit...
    pause >NUL
)
exit
