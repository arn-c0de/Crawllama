#!/bin/bash
# CrawlLama Setup Script for Linux/macOS

set -e

echo "========================================"
echo "CrawlLama Setup"
echo "========================================"
echo ""

# Check Python version
echo "[1/6] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.10 or higher"
    exit 1
fi
python3 --version
echo ""

# Create virtual environment
echo "[2/6] Creating virtual environment..."
if [ -d "venv" ]; then
    echo "Virtual environment already exists, skipping..."
else
    python3 -m venv venv
    echo "Virtual environment created successfully."
fi
echo ""

# Activate virtual environment and install dependencies
echo "[3/6] Activating virtual environment and installing dependencies..."
source venv/bin/activate
echo "Virtual environment activated."
echo ""

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo ""

# Create directories
echo "[4/6] Creating directories..."
mkdir -p data/cache
mkdir -p data/embeddings
mkdir -p data/history
mkdir -p logs
echo "Directories created successfully."
echo ""

# Copy .env.example to .env if not exists
echo "[5/6] Setting up environment..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Created .env file from .env.example"
else
    echo ".env file already exists"
fi
echo ""

# Check Ollama
echo "[6/6] Checking Ollama installation..."
if ! command -v ollama &> /dev/null; then
    echo "WARNING: Ollama is not installed or not in PATH"
    echo "Please install Ollama from https://ollama.ai/download"
    echo ""
    echo "After installation, run:"
    echo "  ollama serve"
    echo "  ollama pull deepseek-r1:8b"
else
    ollama --version
    echo ""
    echo "To download the required model, run:"
    echo "  ollama pull deepseek-r1:8b"
fi
echo ""

echo "========================================"
echo "Setup completed!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Start Ollama: ollama serve"
echo "  2. Pull model: ollama pull deepseek-r1:8b"
echo "  3. Run CrawlLama: ./run.sh"
echo ""
echo "Note: Use ./run.sh to start CrawlLama (automatically uses venv)"
echo ""
