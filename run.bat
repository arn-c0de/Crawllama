@echo off
REM CrawlLama Run Script - Windows
REM Runs CrawlLama via uv (auto-syncs the environment from uv.lock).

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

REM "uv run" ensures the .venv exists and matches uv.lock before launching.
uv run python main.py %*
exit
