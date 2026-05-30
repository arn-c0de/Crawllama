#!/bin/bash
# Health Dashboard Starter Script for Linux/Mac (uv-based).

echo "============================================================"
echo "  🦙 CrawlLama Health Dashboard Starter"
echo "============================================================"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# uv manages the environment from pyproject.toml + uv.lock.
if ! command -v uv &> /dev/null; then
    echo "❌ [ERROR] uv is not installed!"
    echo ""
    echo "Install it with:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "Then provision the environment:"
    echo "  ./setup.sh"
    echo ""
    exit 1
fi

echo "🚀 Starting Health Dashboard..."
echo ""

# `uv run` ensures the .venv exists and matches uv.lock before launching.
uv run python health-dashboard.py

# Capture exit code
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "============================================================"
    echo "❌ Dashboard exited with an error (code: $EXIT_CODE)"
    echo "============================================================"
    echo ""
    exit $EXIT_CODE
fi

echo ""
echo "============================================================"
echo "✅ Dashboard closed successfully."
echo "============================================================"
echo ""
