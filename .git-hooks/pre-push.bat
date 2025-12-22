@echo off
REM Pre-push hook for CodeQL security scanning (Windows)
REM Install: copy .git-hooks\pre-push.bat .git\hooks\pre-push

echo Running CodeQL security scan (pre-push)...

REM Check if CodeQL is installed
where codeql >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Warning: CodeQL is not installed. Skipping security scan.
    echo Install CodeQL from: https://github.com/github/codeql-cli-binaries/releases
    exit /b 0
)

REM Create or update database
echo Creating/Updating CodeQL database...
codeql database create codeql-db --language=python --source-root=. --overwrite >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: CodeQL database creation failed
    exit /b 1
)

echo Running security analysis...
codeql database analyze codeql-db codeql/python-queries --format=sarif-latest --output=codeql-results.sarif >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: CodeQL analysis failed
    exit /b 1
)

REM Check for high severity issues
findstr /C:"\"level\":\"error\"" codeql-results.sarif >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo ERROR: Found high severity security issues! Push aborted.
    echo Review codeql-results.sarif for details
    echo To bypass the check (not recommended), use: git push --no-verify
    exit /b 1
)

echo CodeQL pre-push security scan passed!
exit /b 0
