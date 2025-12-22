@echo off
echo Installing Git hooks...

REM Copy bash hooks (for Git Bash / Unix-style environments)
copy .git-hooks\pre-commit .git\hooks\pre-commit
copy .git-hooks\pre-push .git\hooks\pre-push

REM Copy Windows batch hooks (for native Windows/git.exe)
copy .git-hooks\pre-commit.bat .git\hooks\pre-commit.bat
copy .git-hooks\pre-push.bat .git\hooks\pre-push.bat

if %ERRORLEVEL% equ 0 (
    echo Git hooks installed successfully!
) else (
    echo Failed to install Git hooks.
    exit /b 1
)
