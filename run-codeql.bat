@echo off
REM CodeQL Scan Script for Crawllama

echo Starting CodeQL scan for Crawllama...
echo.

REM Create database
echo Creating CodeQL database...
codeql database create codeql-db --language=python --source-root=. --overwrite
if %ERRORLEVEL% neq 0 (
    echo Error creating database
    exit /b 1
)

echo.
REM Run analysis
echo Running security and quality analysis...
codeql database analyze codeql-db --format=sarif-latest --output=codeql-results.sarif --download
if %ERRORLEVEL% neq 0 (
    echo Error running analysis
    exit /b 1
)

echo.
echo Analysis complete! Results saved to codeql-results.sarif
echo.
echo To view results in VS Code, install the CodeQL extension and open the SARIF file.
echo.
pause
