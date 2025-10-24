#!/bin/bash
# Health Dashboard Starter Script for Linux/Mac
# This script activates the venv and starts the dashboard

echo "============================================================"
echo "  🦙 CrawlLama Health Dashboard Starter"
echo "============================================================"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if venv exists
if [ ! -f "venv/bin/activate" ]; then
    echo "❌ [ERROR] Virtual environment not found!"
    echo ""
    echo "Please create venv first:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    echo ""
    exit 1
fi

# Activate venv
echo "🔧 [1/2] Activating virtual environment..."
source venv/bin/activate

# Check if activation worked
if [ $? -ne 0 ]; then
    echo "❌ [ERROR] Failed to activate venv"
    exit 1
fi

echo "✅ Virtual environment activated"
echo ""

echo "🚀 [2/2] Starting Health Dashboard..."
echo ""

# Start dashboard
python health-dashboard.py

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
