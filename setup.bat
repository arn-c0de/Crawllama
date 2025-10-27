@echo off
REM Setup script for CrawlLama on Windows

echo ================================
echo CrawlLama Setup for Windows
echo ================================
echo.

REM Check Python version
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.10 or higher from https://python.org
    pause
    exit /b 1
)

echo [1/6] Checking Python version...
python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)"
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.10 or higher is required
    pause
    exit /b 1
)
echo [OK] Python version compatible
echo.

REM Create virtual environment
echo [2/6] Creating virtual environment...
if not exist venv (
    python -m venv venv
    echo [OK] Virtual environment created
) else (
    echo [INFO] Virtual environment already exists
)
echo.

REM Activate virtual environment
echo [3/6] Activating virtual environment...
call venv\Scripts\activate.bat
echo.

REM Install dependencies
echo [4/6] Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo [OK] Dependencies installed
echo.

REM Create necessary directories
echo [5/6] Creating directories...
if not exist data mkdir data
if not exist data\cache mkdir data\cache
if not exist data\embeddings mkdir data\embeddings
if not exist data\history mkdir data\history
if not exist logs mkdir logs
if not exist plugins mkdir plugins
echo [OK] Directories created
echo.

REM Setup configuration
echo [6/6] Setting up configuration...
if not exist .env (
    if exist .env.example (
        copy .env.example .env
        echo [OK] Created .env from template
        
        REM Generate secure API key
        echo [INFO] Generating secure API key...
        for /f "delims=" %%i in ('python -c "import secrets; print(secrets.token_urlsafe(32))"') do set GENERATED_API_KEY=%%i
        
        REM Replace placeholder with generated key in .env
        powershell -Command "(Get-Content .env) -replace 'your_secure_api_key_here_min_32_chars', '%GENERATED_API_KEY%' | Set-Content .env"
        
        echo [OK] Generated secure API key and saved to .env
        echo [ACTION REQUIRED] Please edit .env and add other API keys if needed
    ) else (
        echo [INFO] No .env.example found, skipping
    )
) else (
    echo [INFO] .env already exists
)
echo.

REM Check for Ollama
echo ================================
echo Checking for Ollama...
echo ================================
curl -s http://127.0.0.1:11434/api/tags >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Ollama is running
) else (
    echo [WARNING] Ollama is not running or not installed
    echo.
    echo To install Ollama:
    echo 1. Download from: https://ollama.ai/download
    echo 2. Run: ollama serve
    echo 3. Pull a model: ollama pull qwen2.5:3b
)
echo.

echo ================================
echo Setup Complete!
echo ================================
echo.
echo Next steps:
echo 1. Edit .env and add API keys (if needed)
echo 2. Make sure Ollama is running: ollama serve
echo 3. Pull a model: ollama pull qwen2.5:3b
echo 4. Run: python main.py --help-extended
echo.
echo To activate the environment in future sessions:
echo   venv\Scripts\activate.bat
echo.
pause
exit
