@echo off
REM ================================
REM CrawlLama - NUL File Cleanup
REM ================================
REM Dieses Script entfernt die fehlerhafte "nul" Datei,
REM die durch Filesystem-Bugs entstehen kann.

echo Checking for problematic NUL file...

REM Prüfe ob die nul-Datei existiert (als echte Datei, nicht als Device)
if exist "nul" (
    echo [WARNING] Found problematic 'nul' file. Attempting to remove...

    REM Methode 1: Lösche mit UNC-Pfad (sicherste Methode)
    del /F /Q "\\?\%CD%\nul" 2>NUL

    if not exist "nul" (
        echo [OK] Successfully removed 'nul' file
    ) else (
        echo [ERROR] Could not remove 'nul' file automatically.
        echo.
        echo Manual removal methods:
        echo 1. PowerShell: Remove-Item "\\?\%CD%\nul" -Force
        echo 2. WSL/Git Bash: rm nul
        echo 3. Command Prompt: del "\\?\%CD%\nul"
        echo.
        pause
        exit /b 1
    )
) else (
    echo [OK] No problematic 'nul' file found
)

exit /b 0
