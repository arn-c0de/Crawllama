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
echo "[1/8] Checking Python version..."
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

# Install system-level dependencies (tkinter) BEFORE creating the venv.
#
# tkinter is NOT on PyPI — it ships with the OS Python build, so pip can never
# install it. A venv only inherits tkinter if the *base* interpreter has it at
# venv-creation time, so this must run before "python3 -m venv". This is what
# lets `./setup.sh` fully provision the GUI Test Dashboard with no manual steps.
echo "[2/8] Installing system dependencies (tkinter, clipboard)..."
if python3 -c "import tkinter" > /dev/null 2>&1; then
    echo -e "${GREEN}[OK]${NC} tkinter already available"
else
    echo -e "${YELLOW}[INFO]${NC} tkinter missing — installing the system package..."

    # Pick the package + manager for this OS. Each branch needs sudo on Linux.
    TK_INSTALL=""
    if [ "$(uname)" = "Darwin" ]; then
        if command -v brew &> /dev/null; then
            TK_INSTALL="brew install python-tk"
        fi
    elif command -v apt-get &> /dev/null; then
        TK_INSTALL="sudo apt-get install -y python3-tk"
    elif command -v dnf &> /dev/null; then
        TK_INSTALL="sudo dnf install -y python3-tkinter"
    elif command -v pacman &> /dev/null; then
        TK_INSTALL="sudo pacman -S --noconfirm tk"
    elif command -v zypper &> /dev/null; then
        TK_INSTALL="sudo zypper install -y python3-tk"
    fi

    if [ -z "$TK_INSTALL" ]; then
        echo -e "${YELLOW}[WARNING]${NC} Could not detect a package manager for tkinter."
        echo "          The GUI Test Dashboard will be unavailable. Install Tk manually,"
        echo "          then re-run ./setup.sh."
    else
        echo "          Running: $TK_INSTALL"
        if $TK_INSTALL; then
            if python3 -c "import tkinter" > /dev/null 2>&1; then
                echo -e "${GREEN}[OK]${NC} tkinter installed"
            else
                echo -e "${YELLOW}[WARNING]${NC} tkinter still not importable after install."
                echo "          The GUI Test Dashboard may be unavailable."
            fi
        else
            echo -e "${YELLOW}[WARNING]${NC} tkinter install failed (no sudo rights?)."
            echo "          The GUI Test Dashboard will be unavailable; the rest of"
            echo "          CrawlLama will still work. Install it manually with:"
            echo "            $TK_INSTALL"
        fi
    fi
fi

# Clipboard support for pyperclip (copy buttons in the GUI / CLI). Like tkinter,
# this is an OS package, not a PyPI one: pyperclip shells out to a system tool.
# macOS ships pbcopy/pbpaste; Linux needs xclip or xsel on X11, wl-clipboard on
# Wayland. Without one, copy actions raise PyperclipException at runtime.
if [ "$(uname)" = "Darwin" ]; then
    : # pbcopy/pbpaste are built in on macOS
elif command -v xclip &> /dev/null || command -v xsel &> /dev/null \
     || command -v wl-copy &> /dev/null; then
    echo -e "${GREEN}[OK]${NC} clipboard tool already available"
else
    echo -e "${YELLOW}[INFO]${NC} no clipboard tool found — installing one..."

    # On Wayland prefer wl-clipboard; otherwise the X11 utility xclip.
    CLIP_INSTALL=""
    if command -v apt-get &> /dev/null; then
        if [ "$XDG_SESSION_TYPE" = "wayland" ] || [ -n "$WAYLAND_DISPLAY" ]; then
            CLIP_INSTALL="sudo apt-get install -y wl-clipboard"
        else
            CLIP_INSTALL="sudo apt-get install -y xclip"
        fi
    elif command -v dnf &> /dev/null; then
        if [ "$XDG_SESSION_TYPE" = "wayland" ] || [ -n "$WAYLAND_DISPLAY" ]; then
            CLIP_INSTALL="sudo dnf install -y wl-clipboard"
        else
            CLIP_INSTALL="sudo dnf install -y xclip"
        fi
    elif command -v pacman &> /dev/null; then
        if [ "$XDG_SESSION_TYPE" = "wayland" ] || [ -n "$WAYLAND_DISPLAY" ]; then
            CLIP_INSTALL="sudo pacman -S --noconfirm wl-clipboard"
        else
            CLIP_INSTALL="sudo pacman -S --noconfirm xclip"
        fi
    elif command -v zypper &> /dev/null; then
        if [ "$XDG_SESSION_TYPE" = "wayland" ] || [ -n "$WAYLAND_DISPLAY" ]; then
            CLIP_INSTALL="sudo zypper install -y wl-clipboard"
        else
            CLIP_INSTALL="sudo zypper install -y xclip"
        fi
    fi

    if [ -z "$CLIP_INSTALL" ]; then
        echo -e "${YELLOW}[WARNING]${NC} Could not detect a package manager for a clipboard tool."
        echo "          Copy buttons will be unavailable. Install xclip / xsel (X11) or"
        echo "          wl-clipboard (Wayland) manually, then re-run ./setup.sh."
    else
        echo "          Running: $CLIP_INSTALL"
        if $CLIP_INSTALL; then
            echo -e "${GREEN}[OK]${NC} clipboard tool installed"
        else
            echo -e "${YELLOW}[WARNING]${NC} clipboard tool install failed (no sudo rights?)."
            echo "          Copy actions will be unavailable; the rest of CrawlLama still"
            echo "          works. Install it manually with:"
            echo "            $CLIP_INSTALL"
        fi
    fi
fi
echo ""

# Create virtual environment
echo "[3/8] Creating virtual environment..."
# If a venv exists but predates the tkinter install, it won't expose tkinter.
# Recreate it so the dashboard works out of the box.
if [ -d "venv" ] && python3 -c "import tkinter" > /dev/null 2>&1 \
   && ! venv/bin/python -c "import tkinter" > /dev/null 2>&1; then
    echo -e "${YELLOW}[INFO]${NC} Existing venv lacks tkinter — recreating it..."
    rm -rf venv
fi
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}[OK]${NC} Virtual environment created"
else
    echo -e "${YELLOW}[INFO]${NC} Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "[4/8] Activating virtual environment..."
source venv/bin/activate
echo ""

# Feature Selection
echo "[5/8] Feature Selection..."
echo "================================"
echo "Select features to install:"
echo "================================"
echo ""

# LLM Provider Selection
echo "LLM Provider (choose one or more, press ENTER to skip):"
echo "  1. Ollama (Local, Free) [Recommended]"
echo "  2. OpenAI (GPT-3.5/4, Requires API Key)"
echo "  3. Anthropic Claude (Requires API Key)"
echo "  4. Groq (Fast Inference, Requires API Key)"
echo ""
read -r -p "Enter numbers (e.g., 1 or 1,2 or 1,2,3) [ENTER to skip]: " LLM_CHOICE
LLM_CHOICE="${LLM_CHOICE## }"  # lstrip spaces
LLM_CHOICE="${LLM_CHOICE%% }"  # rstrip spaces (simple)

# API Server
echo ""
read -r -p "Install FastAPI Server? (y/n) [n] [ENTER to skip]: " INSTALL_API
INSTALL_API="${INSTALL_API## }"
INSTALL_API="${INSTALL_API%% }"
if [ -z "$INSTALL_API" ]; then
    INSTALL_API="n"
else
    INSTALL_API="${INSTALL_API:0:1}"
    if [[ ! "$INSTALL_API" =~ [yY] ]]; then
        INSTALL_API="n"
    else
        INSTALL_API="y"
    fi
fi

# OSINT Features
echo ""
read -r -p "Install OSINT Features? (y/n) [n] [ENTER to skip]: " INSTALL_OSINT
INSTALL_OSINT="${INSTALL_OSINT## }"
INSTALL_OSINT="${INSTALL_OSINT%% }"
if [ -z "$INSTALL_OSINT" ]; then
    INSTALL_OSINT="n"
else
    INSTALL_OSINT="${INSTALL_OSINT:0:1}"
    if [[ ! "$INSTALL_OSINT" =~ [yY] ]]; then
        INSTALL_OSINT="n"
    else
        INSTALL_OSINT="y"
    fi
fi

# LinkedIn API (Optional)
echo ""
echo -e "${YELLOW}[NOTE]${NC} LinkedIn API requires a LinkedIn account and may have ToS implications."
read -r -p "Install optional LinkedIn API support? (y/n) [n] [ENTER to skip]: " INSTALL_LINKEDIN_API
INSTALL_LINKEDIN_API="${INSTALL_LINKEDIN_API## }"
INSTALL_LINKEDIN_API="${INSTALL_LINKEDIN_API%% }"
if [ -z "$INSTALL_LINKEDIN_API" ]; then
    INSTALL_LINKEDIN_API="n"
else
    INSTALL_LINKEDIN_API="${INSTALL_LINKEDIN_API:0:1}"
    if [[ ! "$INSTALL_LINKEDIN_API" =~ [yY] ]]; then
        INSTALL_LINKEDIN_API="n"
    else
        INSTALL_LINKEDIN_API="y"
    fi
fi

# Testing Tools
echo ""
read -r -p "Install Testing Tools? (y/n) [n] [ENTER to skip]: " INSTALL_TESTING
INSTALL_TESTING="${INSTALL_TESTING## }"
INSTALL_TESTING="${INSTALL_TESTING%% }"
if [ -z "$INSTALL_TESTING" ]; then
    INSTALL_TESTING="n"
else
    INSTALL_TESTING="${INSTALL_TESTING:0:1}"
    if [[ ! "$INSTALL_TESTING" =~ [yY] ]]; then
        INSTALL_TESTING="n"
    else
        INSTALL_TESTING="y"
    fi
fi

echo ""
echo "[6/8] Installing dependencies..."
pip install --upgrade pip

# Create temporary requirements file
echo "# Auto-generated requirements" > requirements_temp.txt

# Always install core
python3 -c "
f = open('requirements.txt', 'r', encoding='utf-8')
lines = f.readlines()
f.close()
installing = False
for line in lines:
    if line.startswith('# ===== CORE'):
        installing = True
    elif line.startswith('# =====') and '# ===== CORE' not in line:
        installing = False
    elif installing and not line.strip().startswith('#') and line.strip():
        print(line.rstrip())
" >> requirements_temp.txt

# Install selected LLM providers
if [[ "$LLM_CHOICE" == *"1"* ]]; then
    python3 -c "
f = open('requirements.txt', 'r', encoding='utf-8')
lines = f.readlines()
f.close()
installing = False
for line in lines:
    if line.startswith('# ===== LLM_OLLAMA'):
        installing = True
    elif line.startswith('# ====='):
        installing = False
    elif installing and line.strip():
        cleaned = line.strip()
        if cleaned.startswith('#'):
            cleaned = cleaned[1:].strip()
        if cleaned and '=====' not in cleaned:
            print(cleaned)
" >> requirements_temp.txt
fi

if [[ "$LLM_CHOICE" == *"2"* ]]; then
    python3 -c "
f = open('requirements.txt', 'r', encoding='utf-8')
lines = f.readlines()
f.close()
installing = False
for line in lines:
    if line.startswith('# ===== LLM_OPENAI'):
        installing = True
    elif line.startswith('# ====='):
        installing = False
    elif installing and line.strip():
        cleaned = line.strip()
        if cleaned.startswith('#'):
            cleaned = cleaned[1:].strip()
        if cleaned and '=====' not in cleaned:
            print(cleaned)
" >> requirements_temp.txt
fi

if [[ "$LLM_CHOICE" == *"3"* ]]; then
    python3 -c "
f = open('requirements.txt', 'r', encoding='utf-8')
lines = f.readlines()
f.close()
installing = False
for line in lines:
    if line.startswith('# ===== LLM_ANTHROPIC'):
        installing = True
    elif line.startswith('# ====='):
        installing = False
    elif installing and line.strip():
        cleaned = line.strip()
        if cleaned.startswith('#'):
            cleaned = cleaned[1:].strip()
        if cleaned and '=====' not in cleaned:
            print(cleaned)
" >> requirements_temp.txt
fi

if [[ "$LLM_CHOICE" == *"4"* ]]; then
    python3 -c "
f = open('requirements.txt', 'r', encoding='utf-8')
lines = f.readlines()
f.close()
installing = False
for line in lines:
    if line.startswith('# ===== LLM_GROQ'):
        installing = True
    elif line.startswith('# ====='):
        installing = False
    elif installing and line.strip():
        cleaned = line.strip()
        if cleaned.startswith('#'):
            cleaned = cleaned[1:].strip()
        if cleaned and '=====' not in cleaned:
            print(cleaned)
" >> requirements_temp.txt
fi

# Install API if selected
if [[ "$INSTALL_API" == "y" || "$INSTALL_API" == "Y" ]]; then
    python3 -c "
f = open('requirements.txt', 'r', encoding='utf-8')
lines = f.readlines()
f.close()
installing = False
for line in lines:
    if line.startswith('# ===== API'):
        installing = True
    elif line.startswith('# ====='):
        installing = False
    elif installing and line.strip():
        cleaned = line.strip()
        if cleaned.startswith('#'):
            cleaned = cleaned[1:].strip()
        if cleaned and '=====' not in cleaned:
            print(cleaned)
" >> requirements_temp.txt
fi

# Install OSINT if selected
if [[ "$INSTALL_OSINT" == "y" || "$INSTALL_OSINT" == "Y" ]]; then
    python3 -c "
f = open('requirements.txt', 'r', encoding='utf-8')
lines = f.readlines()
f.close()
installing = False
for line in lines:
    if line.startswith('# ===== OSINT'):
        installing = True
    elif line.startswith('# ====='):
        installing = False
    elif installing and line.strip():
        cleaned = line.strip()
        if cleaned.startswith('#'):
            cleaned = cleaned[1:].strip()
        if cleaned and '=====' not in cleaned:
            print(cleaned)
" >> requirements_temp.txt
fi

# Install LinkedIn API if selected
if [[ "$INSTALL_LINKEDIN_API" == "y" || "$INSTALL_LINKEDIN_API" == "Y" ]]; then
    python3 -c "
f = open('requirements.txt', 'r', encoding='utf-8')
lines = f.readlines()
f.close()
installing = False
for line in lines:
    if line.startswith('# ===== LINKEDIN_API'):
        installing = True
    elif line.startswith('# ====='):
        installing = False
    elif installing and line.strip():
        cleaned = line.strip()
        if cleaned.startswith('#'):
            cleaned = cleaned[1:].strip()
        if cleaned and '=====' not in cleaned and not cleaned.startswith('NOTE:') and not cleaned.startswith('See ') and not cleaned.startswith('Requires ') and not cleaned.startswith('Installing') and not cleaned.startswith('Only'):
            print(cleaned)
" >> requirements_temp.txt
fi

# Install Testing if selected
if [[ "$INSTALL_TESTING" == "y" || "$INSTALL_TESTING" == "Y" ]]; then
    python3 -c "
f = open('requirements.txt', 'r', encoding='utf-8')
lines = f.readlines()
f.close()
installing = False
for line in lines:
    if line.startswith('# ===== TESTING'):
        installing = True
    elif line.startswith('# ====='):
        installing = False
    elif installing and line.strip():
        cleaned = line.strip()
        if cleaned.startswith('#'):
            cleaned = cleaned[1:].strip()
        if cleaned and '=====' not in cleaned:
            print(cleaned)
" >> requirements_temp.txt
fi

# Install selected packages
pip install -r requirements_temp.txt

if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR]${NC} Failed to install dependencies"
    rm -f requirements_temp.txt
    exit 1
fi

# Cleanup
rm -f requirements_temp.txt
echo -e "${GREEN}[OK]${NC} Dependencies installed"
echo ""

# Create necessary directories
echo "[7/8] Creating directories..."
mkdir -p data/cache data/embeddings data/history logs plugins
echo -e "${GREEN}[OK]${NC} Directories created"
echo ""

# Setup configuration
echo "[8/8] Setting up configuration..."

# Setup .env
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        # Restrict secret file to owner read/write only.
        chmod 600 .env
        echo -e "${GREEN}[OK]${NC} Created .env from template (chmod 600)"

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

# Setup config.json
if [ ! -f "config.json" ]; then
    if [ -f "config.json.example" ]; then
        cp config.json.example config.json
        echo -e "${GREEN}[OK]${NC} Created config.json from template"
    else
        echo -e "${YELLOW}[WARNING]${NC} No config.json.example found"
    fi
else
    echo -e "${YELLOW}[INFO]${NC} config.json already exists"
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
