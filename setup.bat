@echo off
REM CrawlLama Setup Script for Windows
echo ========================================
echo CrawlLama Setup
echo ========================================
echo.

REM Check Python version
echo [1/6] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10 or higher from https://www.python.org/
    pause
    exit /b 1
)
python --version
echo.

REM Create virtual environment
echo [2/6] Creating virtual environment...
if exist "venv" (
    echo Virtual environment already exists, skipping...
) else (
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created successfully.
)
echo.

REM Activate virtual environment and install dependencies
echo [3/6] Activating virtual environment and installing dependencies...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)
echo Virtual environment activated.
echo.

echo Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo.

REM Create directories
echo [4/6] Creating directories...
if not exist "data\cache" mkdir data\cache
if not exist "data\embeddings" mkdir data\embeddings
if not exist "data\history" mkdir data\history
if not exist "logs" mkdir logs
echo Directories created successfully.
echo.

REM Copy .env.example to .env if not exists
echo [5/6] Setting up environment...
if not exist ".env" (
    copy .env.example .env
    echo Created .env file from .env.example
) else (
    echo .env file already exists
)
echo.

REM Check Ollama
echo [6/6] Checking Ollama installation...
ollama --version >nul 2>&1
if errorlevel 1 (
    echo WARNING: Ollama is not installed or not in PATH
    echo Please install Ollama from https://ollama.ai/download
    echo.
    echo After installation, run:
    echo   ollama serve
    echo   ollama pull deepseek-r1:8b
) else (
    ollama --version
    echo.
    echo To download the required model, run:
    echo   ollama pull deepseek-r1:8b
)
echo.

echo ========================================
echo Setup completed!
echo ========================================
echo.
echo Next steps:
echo   1. Start Ollama: ollama serve
echo   2. Pull model: ollama pull deepseek-r1:8b
echo   3. Run CrawlLama: run.bat
echo.
echo Note: Use run.bat to start CrawlLama (automatically uses venv)
echo.
pause
