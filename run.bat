@echo off
REM CrawlLama Run Script - Windows
REM Aktiviert das venv und startet CrawlLama

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

REM Run CrawlLama with all arguments
python main.py %*
exit
