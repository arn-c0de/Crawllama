#!/bin/bash
# CrawlLama API Server - Linux/macOS
# Aktiviert das venv und startet den FastAPI Server

# Check if venv exists
if [ ! -f "venv/bin/activate" ]; then
    echo "ERROR: Virtual environment not found!"
    echo "Please run ./setup.sh first to create the virtual environment."
    echo ""
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

echo "========================================"
echo "CrawlLama API Server"
echo "========================================"
echo "Starting FastAPI server..."
echo "API Documentation: http://localhost:8000/docs"
echo "ReDoc: http://localhost:8000/redoc"
echo ""
echo "Press Ctrl+C to stop the server"
echo "========================================"
echo ""

# Run FastAPI Server
python app.py
