@echo off
REM Health Dashboard Starter Script for Windows
REM This script activates the venv and starts the dashboard

REM Cleanup problematic NUL file if it exists (Windows filesystem bug)
if exist "nul" del /F /Q "\\?\%CD%\nul" 2>NUL

echo ============================================================
echo   CrawlLama Health Dashboard Starter
echo ============================================================
echo.

REM Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo.
    echo Please create venv first:
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

REM Activate venv
echo [1/2] Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if activation worked
if errorlevel 1 (
    echo [ERROR] Failed to activate venv
    pause
    exit /b 1
)

echo [2/2] Starting Health Dashboard...
echo.

REM Start dashboard
python health-dashboard.py

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
