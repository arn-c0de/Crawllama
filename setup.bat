@echo off
REM Setup script for CrawlLama on Windows (uv-based).
setlocal enabledelayedexpansion

REM Cleanup problematic NUL file if it exists (Windows filesystem bug)
if exist "nul" del /F /Q "\\?\%CD%\nul" 2>NUL

REM Absolute path to this project (used for the generated crawllama launcher).
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

echo ================================
echo CrawlLama Setup for Windows
echo ================================
echo.

REM Ensure uv is installed. uv manages the Python interpreter (pinned in
REM .python-version), the virtual environment (.venv) and all dependencies
REM from pyproject.toml + uv.lock.
echo [1/6] Checking for uv...
where uv >NUL 2>NUL
if errorlevel 1 (
    echo [INFO] uv not found - installing it...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    where uv >NUL 2>NUL
    if errorlevel 1 (
        echo [ERROR] uv installed but not on PATH. Open a new terminal and re-run setup.bat
        pause
        exit /b 1
    )
)
for /f "tokens=2" %%v in ('uv --version') do set UV_VERSION=%%v
echo [OK] uv !UV_VERSION!
echo.

REM Feature Selection - maps to optional-dependency extras in pyproject.toml.
echo [2/6] Feature Selection...
echo ================================
echo Select features to install:
echo ================================
echo.

set "EXTRAS="

REM LLM Provider Selection
echo LLM Provider (choose one or more, press ENTER to skip):
echo   1. Ollama (Local, Free) [Recommended]
echo   2. OpenAI (GPT-3.5/4, Requires API Key)
echo   3. Anthropic Claude (Requires API Key)
echo   4. Groq (Fast Inference, Requires API Key)
echo.
set /p LLM_CHOICE="Enter numbers (e.g., 1 or 1,2 or 1,2,3) [ENTER to skip]: "
echo !LLM_CHOICE! | findstr "1" >nul && set "EXTRAS=!EXTRAS! --extra ollama"
echo !LLM_CHOICE! | findstr "2" >nul && set "EXTRAS=!EXTRAS! --extra openai"
echo !LLM_CHOICE! | findstr "3" >nul && set "EXTRAS=!EXTRAS! --extra anthropic"
echo !LLM_CHOICE! | findstr "4" >nul && set "EXTRAS=!EXTRAS! --extra groq"

REM API Server
echo.
set /p INSTALL_API="Install FastAPI Server? (y/n) [n] [ENTER to skip]: "
if /i "!INSTALL_API:~0,1!"=="y" set "EXTRAS=!EXTRAS! --extra api"

REM OSINT Features
echo.
set /p INSTALL_OSINT="Install OSINT Features? (y/n) [n] [ENTER to skip]: "
if /i "!INSTALL_OSINT:~0,1!"=="y" set "EXTRAS=!EXTRAS! --extra osint"

REM LinkedIn API (Optional)
echo.
echo [NOTE] LinkedIn API requires a LinkedIn account and may have ToS implications.
set /p INSTALL_LINKEDIN="Install optional LinkedIn API support? (y/n) [n] [ENTER to skip]: "
if /i "!INSTALL_LINKEDIN:~0,1!"=="y" set "EXTRAS=!EXTRAS! --extra linkedin"

REM Testing Tools
echo.
set /p INSTALL_TESTING="Install Testing Tools? (y/n) [n] [ENTER to skip]: "
if /i "!INSTALL_TESTING:~0,1!"=="y" set "EXTRAS=!EXTRAS! --extra testing"

echo.
echo [3/6] Installing dependencies with uv...
if "!EXTRAS!"=="" (
    echo [INFO] No optional features selected - installing core only.
    echo          Running: uv sync
    uv sync
) else (
    echo          Running: uv sync!EXTRAS!
    uv sync!EXTRAS!
)
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo [OK] Dependencies installed into .venv
echo.

REM Create necessary directories
echo [4/7] Creating directories...
if not exist data mkdir data
if not exist data\cache mkdir data\cache
if not exist data\embeddings mkdir data\embeddings
if not exist data\history mkdir data\history
if not exist logs mkdir logs
if not exist plugins mkdir plugins
echo [OK] Directories created
echo.

REM Setup configuration
echo [5/7] Setting up configuration...

REM Setup .env
if not exist .env (
    if exist .env.example (
        copy .env.example .env
        echo [OK] Created .env from template

        REM Generate secure API key
        echo [INFO] Generating secure API key...
        for /f "delims=" %%i in ('uv run python -c "import secrets; print(secrets.token_urlsafe(32))"') do set GENERATED_API_KEY=%%i

        REM Replace placeholder with generated key in .env
        powershell -Command "(Get-Content .env) -replace 'your_secure_api_key_here_min_32_chars', '!GENERATED_API_KEY!' | Set-Content .env"

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
    if exist config\config.json.example (
        copy config\config.json.example config.json
        echo [OK] Created config.json from template
    ) else (
        echo [WARNING] No config\config.json.example found
    )
) else (
    echo [INFO] config.json already exists
)
echo.

REM Install the crawllama system command (a thin launcher that runs CrawlLama
REM from its project directory via uv, so config.json/data/.env resolve no
REM matter where the command is invoked from). %USERPROFILE%\.local\bin is the
REM same directory uv installs into and is on PATH after the uv installer runs.
echo [6/7] Installing crawllama system command...
set "BIN_DIR=%USERPROFILE%\.local\bin"
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"
set "LAUNCHER=%BIN_DIR%\crawllama.bat"
(
    echo @echo off
    echo REM CrawlLama launcher ^(generated by setup.bat^). Runs CrawlLama from anywhere.
    echo cd /d "%PROJECT_DIR%" ^|^| exit /b 1
    echo uv run python main.py %%*
) > "%LAUNCHER%"
echo [OK] Installed: %LAUNCHER%
echo %PATH% | find /i "%BIN_DIR%" >NUL
if errorlevel 1 (
    echo [ACTION REQUIRED] %BIN_DIR% is not on your PATH.
    echo          Add it via: setx PATH "%%PATH%%;%BIN_DIR%"  then open a new terminal.
) else (
    echo [OK] You can now run: crawllama --help-extended
)
echo.

REM Check for Ollama
echo [7/7] Checking for Ollama...
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
echo 4. Run: crawllama --help-extended   (or run.bat --help-extended)
echo.
echo Common commands:
echo   crawllama                    # start CrawlLama from anywhere (system command)
echo   uv run python main.py        # start CrawlLama (CLI) from the project dir
echo   run_api.bat                  # start the FastAPI server
echo   uv sync --extra ^<feature^>    # add a feature later (api, osint, openai, ...)
echo   uv run pytest                # run the test suite (after --extra testing)
echo.
pause
exit
