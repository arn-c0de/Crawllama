#!/bin/bash
# Get script directory and change to root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."

echo "Installing Git hooks..."
# Install pre-commit and pre-push hooks
cp .git-hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
cp .git-hooks/pre-push .git/hooks/pre-push
chmod +x .git/hooks/pre-push

# Also copy Windows batch versions for native Windows git.exe
cp .git-hooks/pre-commit.bat .git/hooks/pre-commit.bat
cp .git-hooks/pre-push.bat .git/hooks/pre-push.bat

if [ $? -eq 0 ]; then
    echo "Git hooks installed successfully!"
else
    echo "Failed to install Git hooks."
    exit 1
fi
