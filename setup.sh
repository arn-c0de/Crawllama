#!/bin/bash
# Setup script for CrawlLama on Linux/macOS (uv-based).

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

# Absolute path to this project (used for the generated `crawllama` launcher).
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Ensure uv is installed. uv manages the Python interpreter (pinned in
# .python-version), the virtual environment (.venv) and every dependency
# from pyproject.toml + uv.lock.
echo "[1/7] Checking for uv..."
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}[INFO]${NC} uv not found — installing it..."
    if command -v curl &> /dev/null; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget &> /dev/null; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        echo -e "${RED}[ERROR]${NC} Need curl or wget to install uv. Install uv manually:"
        echo "  https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
    # Make uv available in the current shell for the rest of this script.
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v uv &> /dev/null; then
        echo -e "${RED}[ERROR]${NC} uv installed but not on PATH. Open a new shell and re-run ./setup.sh"
        exit 1
    fi
fi
echo -e "${GREEN}[OK]${NC} uv $(uv --version | awk '{print $2}')"
echo ""

# Relocate the venv off symlink-incapable shared folders (vboxsf/vmhgfs) before
# any `uv sync`/`uv run`, otherwise uv fails to create the in-project .venv.
source "$PROJECT_DIR/scripts/uv-env.sh"
crawllama_setup_uv_env "$PROJECT_DIR"

# Install system-level dependencies (tkinter, clipboard).
#
# These are OS packages, not PyPI ones, so uv/pip cannot provide them.
# uv's managed CPython already bundles tkinter, but if uv ends up using a
# system interpreter the GUI Test Dashboard still needs the system Tk package,
# so we provision it here when missing.
echo "[2/7] Installing system dependencies (tkinter, clipboard)..."
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
            echo -e "${GREEN}[OK]${NC} tkinter installed"
        else
            echo -e "${YELLOW}[WARNING]${NC} tkinter install failed (no sudo rights?)."
            echo "          The GUI Test Dashboard may be unavailable; the rest of"
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

# Feature Selection — maps to optional-dependency extras in pyproject.toml.
echo "[3/7] Feature Selection..."
echo "================================"
echo "Select features to install:"
echo "================================"
echo ""

EXTRAS=()

# LLM Provider Selection
echo "LLM Provider (choose one or more, press ENTER to skip):"
echo "  1. Ollama (Local, Free) [Recommended]"
echo "  2. OpenAI (GPT-3.5/4, Requires API Key)"
echo "  3. Anthropic Claude (Requires API Key)"
echo "  4. Groq (Fast Inference, Requires API Key)"
echo ""
read -r -p "Enter numbers (e.g., 1 or 1,2 or 1,2,3) [ENTER to skip]: " LLM_CHOICE
[[ "$LLM_CHOICE" == *"1"* ]] && EXTRAS+=("--extra" "ollama")
[[ "$LLM_CHOICE" == *"2"* ]] && EXTRAS+=("--extra" "openai")
[[ "$LLM_CHOICE" == *"3"* ]] && EXTRAS+=("--extra" "anthropic")
[[ "$LLM_CHOICE" == *"4"* ]] && EXTRAS+=("--extra" "groq")

# Helper: read a y/n answer (default n) and append an extra if yes.
ask_extra() {
    local prompt="$1" extra="$2" answer
    read -r -p "$prompt (y/n) [n] [ENTER to skip]: " answer
    answer="${answer## }"; answer="${answer%% }"
    if [[ "${answer:0:1}" =~ [yY] ]]; then
        EXTRAS+=("--extra" "$extra")
    fi
}

echo ""
ask_extra "Install FastAPI Server?" "api"
echo ""
ask_extra "Install OSINT Features?" "osint"
echo ""
echo -e "${YELLOW}[NOTE]${NC} LinkedIn API requires a LinkedIn account and may have ToS implications."
ask_extra "Install optional LinkedIn API support?" "linkedin"
echo ""
ask_extra "Install Testing Tools?" "testing"

echo ""
echo "[4/7] Installing dependencies with uv..."
if [ ${#EXTRAS[@]} -eq 0 ]; then
    echo -e "${YELLOW}[INFO]${NC} No optional features selected — installing core only."
    echo "          Running: uv sync"
    uv sync
else
    echo "          Running: uv sync ${EXTRAS[*]}"
    uv sync "${EXTRAS[@]}"
fi
echo -e "${GREEN}[OK]${NC} Dependencies installed into ${UV_PROJECT_ENVIRONMENT:-.venv}"
echo ""

# Create necessary directories
echo "[5/8] Creating directories..."
mkdir -p data/cache data/embeddings data/history logs plugins
echo -e "${GREEN}[OK]${NC} Directories created"
echo ""

# Setup configuration
echo "[6/8] Setting up configuration..."

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
    if [ -f "config/config.json.example" ]; then
        cp config/config.json.example config.json
        echo -e "${GREEN}[OK]${NC} Created config.json from template"
    else
        echo -e "${YELLOW}[WARNING]${NC} No config/config.json.example found"
    fi
else
    echo -e "${YELLOW}[INFO]${NC} config.json already exists"
fi
echo ""

# Install the `crawllama` system command (a thin launcher that runs CrawlLama
# from its project directory via uv, so config.json/data/.env resolve correctly
# no matter where the command is invoked from).
echo "[7/8] Installing 'crawllama' system command..."
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
LAUNCHER="$BIN_DIR/crawllama"
cat > "$LAUNCHER" <<EOF
#!/bin/bash
# CrawlLama launcher (generated by setup.sh). Runs CrawlLama from anywhere.
cd "$PROJECT_DIR" || { echo "CrawlLama directory not found: $PROJECT_DIR"; exit 1; }
# Relocate the venv off symlink-incapable shared folders (vboxsf/vmhgfs).
source "$PROJECT_DIR/scripts/uv-env.sh"
crawllama_setup_uv_env "$PROJECT_DIR"
exec uv run python main.py "\$@"
EOF
chmod +x "$LAUNCHER"
echo -e "${GREEN}[OK]${NC} Installed: $LAUNCHER"
case ":$PATH:" in
    *":$BIN_DIR:"*)
        echo -e "${GREEN}[OK]${NC} You can now run: crawllama --help-extended"
        ;;
    *)
        echo -e "${YELLOW}[ACTION REQUIRED]${NC} $BIN_DIR is not on your PATH."
        echo "          Add this line to your ~/.bashrc or ~/.zshrc, then restart the shell:"
        echo "            export PATH=\"\$HOME/.local/bin:\$PATH\""
        ;;
esac
echo ""

# Check for Ollama
echo "[8/8] Checking for Ollama..."
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
    echo "  sudo cp deployment/crawllama.service /etc/systemd/system/"
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
echo "4. Run: crawllama --help-extended   (or ./run.sh --help-extended)"
echo ""
echo "Common commands:"
echo "  crawllama                    # start CrawlLama from anywhere (system command)"
echo "  uv run python main.py        # start CrawlLama (CLI) from the project dir"
echo "  ./run_api.sh                 # start the FastAPI server"
echo "  uv sync --extra <feature>    # add a feature later (api, osint, openai, ...)"
echo "  uv run pytest                # run the test suite (after --extra testing)"
echo ""
