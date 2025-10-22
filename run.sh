#!/bin/bash
# CrawlLama Run Script - Linux/macOS
# Aktiviert das venv und startet CrawlLama

# Check if venv exists
if [ ! -f "venv/bin/activate" ]; then
    echo "ERROR: Virtual environment not found!"
    echo "Please run ./setup.sh first to create the virtual environment."
    echo ""
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Run CrawlLama with all arguments
python main.py "$@"
