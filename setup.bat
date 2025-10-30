@echo off
REM Setup script for CrawlLama on Windows

REM Cleanup problematic NUL file if it exists (Windows filesystem bug)
if exist "nul" del /F /Q "\\?\%CD%\nul" 2>NUL

echo ================================
echo CrawlLama Setup for Windows
echo ================================
echo.

REM Check Python version
python --version >NUL 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.10 or higher from https://python.org
    pause
    exit /b 1
)

echo [1/7] Checking Python version...
python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)"
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.10 or higher is required
    pause
    exit /b 1
)
echo [OK] Python version compatible
echo.

REM Create virtual environment
echo [2/7] Creating virtual environment...
if not exist venv (
    python -m venv venv
    echo [OK] Virtual environment created
) else (
    echo [INFO] Virtual environment already exists
)
echo.

REM Activate virtual environment
echo [3/7] Activating virtual environment...
call venv\Scripts\activate.bat
echo.

REM Feature Selection
echo [4/7] Feature Selection...
echo ================================
echo Select features to install:
echo ================================
echo.

REM LLM Provider Selection
echo LLM Provider (choose one or more, press ENTER to skip):
echo   1. Ollama (Local, Free) [Recommended]
echo   2. OpenAI (GPT-3.5/4, Requires API Key)
echo   3. Anthropic Claude (Requires API Key)
echo   4. Groq (Fast Inference, Requires API Key)
echo.
set /p LLM_CHOICE="Enter numbers (e.g., 1 or 1,2 or 1,2,3) [ENTER to skip]: "

REM Trim spaces from input (simple trim)
for /f "tokens=* delims= " %%a in ("%LLM_CHOICE%") do set LLM_CHOICE=%%a

REM If empty, skip LLM installs
if "%LLM_CHOICE%"=="" (
    echo [INFO] No LLM selected, skipping LLM-specific packages
) else (
    REM Install selected LLM providers
    echo %LLM_CHOICE% | findstr "1" >nul && python -c "f=open('requirements.txt','r',encoding='utf-8');lines=f.readlines();f.close();sec=False;exec('for line in lines:\n if line.startswith(\"# ===== LLM_OLLAMA\"):sec=True\n elif line.startswith(\"# =====\"):sec=False\n elif sec:\n  c=line.strip()\n  if c.startswith(\"#\"):c=c[1:].strip()\n  if c and \"=====\" not in c:print(c)')" >> requirements_temp.txt

    echo %LLM_CHOICE% | findstr "2" >nul && python -c "f=open('requirements.txt','r',encoding='utf-8');lines=f.readlines();f.close();sec=False;exec('for line in lines:\n if line.startswith(\"# ===== LLM_OPENAI\"):sec=True\n elif line.startswith(\"# =====\"):sec=False\n elif sec:\n  c=line.strip()\n  if c.startswith(\"#\"):c=c[1:].strip()\n  if c and \"=====\" not in c:print(c)')" >> requirements_temp.txt

    echo %LLM_CHOICE% | findstr "3" >nul && python -c "f=open('requirements.txt','r',encoding='utf-8');lines=f.readlines();f.close();sec=False;exec('for line in lines:\n if line.startswith(\"# ===== LLM_ANTHROPIC\"):sec=True\n elif line.startswith(\"# =====\"):sec=False\n elif sec:\n  c=line.strip()\n  if c.startswith(\"#\"):c=c[1:].strip()\n  if c and \"=====\" not in c:print(c)')" >> requirements_temp.txt

    echo %LLM_CHOICE% | findstr "4" >nul && python -c "f=open('requirements.txt','r',encoding='utf-8');lines=f.readlines();f.close();sec=False;exec('for line in lines:\n if line.startswith(\"# ===== LLM_GROQ\"):sec=True\n elif line.startswith(\"# =====\"):sec=False\n elif sec:\n  c=line.strip()\n  if c.startswith(\"#\"):c=c[1:].strip()\n  if c and \"=====\" not in c:print(c)')" >> requirements_temp.txt
)

REM API Server
echo.
set /p INSTALL_API="Install FastAPI Server? (y/n) [n] [ENTER to skip]: "
REM Trim whitespace
for /f "tokens=* delims= " %%a in ("%INSTALL_API%") do set INSTALL_API=%%a
REM Default to 'n' if empty, else normalize to first char (y/n)
if "%INSTALL_API%"=="" (
    set INSTALL_API=n
) else (
    call set "INSTALL_API=%%INSTALL_API:~0,1%%"
    if /i not "%INSTALL_API%"=="y" set INSTALL_API=n
    if /i "%INSTALL_API%"=="y" set INSTALL_API=y
)

REM OSINT Features
echo.
set /p INSTALL_OSINT="Install OSINT Features? (y/n) [n] [ENTER to skip]: "
REM Trim whitespace
for /f "tokens=* delims= " %%a in ("%INSTALL_OSINT%") do set INSTALL_OSINT=%%a
REM Default to 'n' if empty, else normalize to first char (y/n)
if "%INSTALL_OSINT%"=="" (
    set INSTALL_OSINT=n
) else (
    call set "INSTALL_OSINT=%%INSTALL_OSINT:~0,1%%"
    if /i not "%INSTALL_OSINT%"=="y" set INSTALL_OSINT=n
    if /i "%INSTALL_OSINT%"=="y" set INSTALL_OSINT=y
)

REM Testing Tools
echo.
set /p INSTALL_TESTING="Install Testing Tools? (y/n) [n] [ENTER to skip]: "
REM Trim whitespace
for /f "tokens=* delims= " %%a in ("%INSTALL_TESTING%") do set INSTALL_TESTING=%%a
REM Default to 'n' if empty, else normalize to first char (y/n)
if "%INSTALL_TESTING%"=="" (
    set INSTALL_TESTING=n
) else (
    call set "INSTALL_TESTING=%%INSTALL_TESTING:~0,1%%"
    if /i not "%INSTALL_TESTING%"=="y" set INSTALL_TESTING=n
    if /i "%INSTALL_TESTING%"=="y" set INSTALL_TESTING=y
)

echo.
echo [5/7] Installing dependencies...
pip install --upgrade pip

REM Create temporary requirements file
echo # Auto-generated requirements > requirements_temp.txt

REM Always install core
python -c "import sys; f=open('requirements.txt','r',encoding='utf-8'); lines=f.readlines(); f.close(); installing=False; [print(line.rstrip()) for line in lines if (line.startswith('# ===== CORE') and not installing or (installing := line.startswith('# ===== CORE')) or (installing and not line.startswith('# =====') and not line.strip().startswith('#') and line.strip()))]" >> requirements_temp.txt

REM (Moved above into conditional block to handle empty input)

REM Install API if selected
if /i "%INSTALL_API%"=="y" python -c "f=open('requirements.txt','r',encoding='utf-8');lines=f.readlines();f.close();sec=False;exec('for line in lines:\n if line.startswith(\"# ===== API\"):sec=True\n elif line.startswith(\"# =====\"):sec=False\n elif sec:\n  c=line.strip()\n  if c.startswith(\"#\"):c=c[1:].strip()\n  if c and \"=====\" not in c:print(c)')" >> requirements_temp.txt

REM Install OSINT if selected
if /i "%INSTALL_OSINT%"=="y" python -c "f=open('requirements.txt','r',encoding='utf-8');lines=f.readlines();f.close();sec=False;exec('for line in lines:\n if line.startswith(\"# ===== OSINT\"):sec=True\n elif line.startswith(\"# =====\"):sec=False\n elif sec:\n  c=line.strip()\n  if c.startswith(\"#\"):c=c[1:].strip()\n  if c and \"=====\" not in c:print(c)')" >> requirements_temp.txt

REM Install Testing if selected
if /i "%INSTALL_TESTING%"=="y" python -c "f=open('requirements.txt','r',encoding='utf-8');lines=f.readlines();f.close();sec=False;exec('for line in lines:\n if line.startswith(\"# ===== TESTING\"):sec=True\n elif line.startswith(\"# =====\"):sec=False\n elif sec:\n  c=line.strip()\n  if c.startswith(\"#\"):c=c[1:].strip()\n  if c and \"=====\" not in c:print(c)')" >> requirements_temp.txt

REM Install selected packages
pip install -r requirements_temp.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies
    del requirements_temp.txt
    pause
    exit /b 1
)

REM Cleanup
del requirements_temp.txt
echo [OK] Dependencies installed
echo.

REM Create necessary directories
echo [6/7] Creating directories...
if not exist data mkdir data
if not exist data\cache mkdir data\cache
if not exist data\embeddings mkdir data\embeddings
if not exist data\history mkdir data\history
if not exist logs mkdir logs
if not exist plugins mkdir plugins
echo [OK] Directories created
echo.

REM Setup configuration
echo [7/7] Setting up configuration...

REM Setup .env
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

REM Setup config.json
if not exist config.json (
    if exist config.json.example (
        copy config.json.example config.json
        echo [OK] Created config.json from template
    ) else (
        echo [WARNING] No config.json.example found
    )
) else (
    echo [INFO] config.json already exists
)
echo.

REM Check for Ollama
echo ================================
echo Checking for Ollama...
echo ================================
curl -s http://127.0.0.1:11434/api/tags >NUL 2>&1
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
