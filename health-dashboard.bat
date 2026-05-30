@echo off
REM Health Dashboard Starter Script for Windows (uv-based).

REM Cleanup problematic NUL file if it exists (Windows filesystem bug)
if exist "nul" del /F /Q "\\?\%CD%\nul" 2>NUL

echo ============================================================
echo   CrawlLama Health Dashboard Starter
echo ============================================================
echo.

REM uv manages the environment from pyproject.toml + uv.lock.
where uv >NUL 2>NUL
if errorlevel 1 (
    echo [ERROR] uv is not installed!
    echo.
    echo Install it with:
    echo   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 ^| iex"
    echo Then provision the environment:
    echo   setup.bat
    echo.
    pause
    exit /b 1
)

echo Starting Health Dashboard...
echo.

REM "uv run" ensures the .venv exists and matches uv.lock before launching.
uv run python health-dashboard.py

REM If dashboard exits with error
if errorlevel 1 (
    echo.
    echo ============================================================
    echo Dashboard exited with an error.
    echo ============================================================
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo Dashboard closed successfully.
echo ============================================================
echo.
