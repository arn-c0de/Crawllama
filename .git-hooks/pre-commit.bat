@echo off
REM Pre-commit hook for CodeQL security scanning
REM Install: copy .git-hooks\pre-commit.bat .git\hooks\pre-commit

echo Running CodeQL security scan...

REM Check if CodeQL is installed
where codeql >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Warning: CodeQL is not installed. Skipping security scan.
    echo Install CodeQL from: https://github.com/github/codeql-cli-binaries/releases
    exit /b 0
)

REM Run CodeQL database creation and analysis
echo Creating CodeQL database...
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
    echo ERROR: Found high severity security issues!
    echo Review codeql-results.sarif for details
    echo To commit anyway, use: git commit --no-verify
    exit /b 1
)

echo CodeQL security scan passed!
exit /b 0
