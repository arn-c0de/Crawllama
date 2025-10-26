#!/bin/bash
# Setup script for CrawlLama on Linux/macOS

set -e

echo "================================"
echo "CrawlLama Setup for Linux/macOS"
echo "================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo "[1/6] Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR]${NC} Python 3 is not installed"
    echo "Please install Python 3.10 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}[ERROR]${NC} Python $REQUIRED_VERSION or higher is required (found $PYTHON_VERSION)"
    exit 1
fi

echo -e "${GREEN}[OK]${NC} Python $PYTHON_VERSION"
echo ""

# Create virtual environment
echo "[2/6] Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}[OK]${NC} Virtual environment created"
else
    echo -e "${YELLOW}[INFO]${NC} Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "[3/6] Activating virtual environment..."
source venv/bin/activate
echo ""

# Install dependencies
echo "[4/6] Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR]${NC} Failed to install dependencies"
    exit 1
fi

echo -e "${GREEN}[OK]${NC} Dependencies installed"
echo ""

# Create necessary directories
echo "[5/6] Creating directories..."
mkdir -p data/cache data/embeddings data/history logs plugins
echo -e "${GREEN}[OK]${NC} Directories created"
echo ""

# Setup configuration
echo "[6/6] Setting up configuration..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}[OK]${NC} Created .env from template"
        
        # Generate secure API key
        echo -e "${YELLOW}[INFO]${NC} Generating secure API key..."
        GENERATED_API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
        
        # Replace placeholder with generated key in .env
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s/your_secure_api_key_here_min_32_chars/$GENERATED_API_KEY/" .env
        else
            # Linux
            sed -i "s/your_secure_api_key_here_min_32_chars/$GENERATED_API_KEY/" .env
        fi
        
        echo -e "${GREEN}[OK]${NC} Generated secure API key and saved to .env"
        echo -e "${YELLOW}[ACTION REQUIRED]${NC} Please edit .env and add other API keys if needed"
    else
        echo -e "${YELLOW}[INFO]${NC} No .env.example found, skipping"
    fi
else
    echo -e "${YELLOW}[INFO]${NC} .env already exists"
fi
echo ""

# Check for Ollama
echo "================================"
echo "Checking for Ollama..."
echo "================================"
if curl -s http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}[OK]${NC} Ollama is running"
else
    echo -e "${YELLOW}[WARNING]${NC} Ollama is not running or not installed"
    echo ""
    echo "To install Ollama:"
    echo "  curl -fsSL https://ollama.ai/install.sh | sh"
    echo ""
    echo "Then run:"
    echo "  ollama serve"
    echo "  ollama pull qwen2.5:3b"
fi
echo ""

# Systemd service (Linux only)
if [ "$(uname)" = "Linux" ]; then
    echo "================================"
    echo "Systemd Service Setup (Optional)"
    echo "================================"
    echo ""
    echo "To install as a systemd service:"
    echo "  sudo cp crawllama.service /etc/systemd/system/"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable crawllama"
    echo "  sudo systemctl start crawllama"
    echo ""
fi

echo "================================"
echo "Setup Complete!"
echo "================================"
echo ""
echo "Next steps:"
echo "1. Edit .env and add API keys (if needed)"
echo "2. Make sure Ollama is running: ollama serve"
echo "3. Pull a model: ollama pull qwen2.5:3b"
echo "4. Run: python main.py --help-extended"
echo ""
echo "To activate the environment in future sessions:"
echo "  source venv/bin/activate"
echo ""
