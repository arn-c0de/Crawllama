#!/bin/bash
# CodeQL Scan Script for Crawllama

# Get script directory and change to root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."

echo "Starting CodeQL scan for Crawllama..."

# Create database
echo "Creating CodeQL database..."
codeql database create codeql-db --language=python --source-root=. --overwrite

# Run analysis
echo "Running security and quality analysis..."
codeql database analyze codeql-db --format=sarif-latest --output=reports/codeql-results.sarif --download --config=config/codeql-config.yml

echo "Analysis complete! Results saved to reports/codeql-results.sarif"
echo ""
echo "To view results in VS Code, install the CodeQL extension and open the SARIF file."
