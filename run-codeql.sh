#!/bin/bash
# CodeQL Scan Script for Crawllama

echo "Starting CodeQL scan for Crawllama..."

# Create database
echo "Creating CodeQL database..."
codeql database create codeql-db --language=python --source-root=. --overwrite

# Run analysis
echo "Running security and quality analysis..."
codeql database analyze codeql-db --format=sarif-latest --output=codeql-results.sarif --download

echo "Analysis complete! Results saved to codeql-results.sarif"
echo ""
echo "To view results in VS Code, install the CodeQL extension and open the SARIF file."
