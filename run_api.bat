@echo off
REM CrawlLama API Server - Windows
REM Aktiviert das venv und startet den FastAPI Server

REM Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run setup.bat first to create the virtual environment.
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

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

REM Run FastAPI Server
python app.py

REM Keep window open if error occurred
if errorlevel 1 (
    echo.
    echo An error occurred. Press any key to exit...
    pause >nul
)
