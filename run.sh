#!/bin/bash
# CrawlLama Run Script - Linux/macOS
# Runs CrawlLama via uv (auto-syncs the environment from uv.lock).

if ! command -v uv &> /dev/null; then
    echo "ERROR: uv is not installed!"
    echo "Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "Then run ./setup.sh to provision the environment."
    echo ""
    exit 1
fi

# Relocate the venv off symlink-incapable shared folders (vboxsf/vmhgfs).
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/scripts/uv-env.sh"
crawllama_setup_uv_env "$SCRIPT_DIR"

# `uv run` ensures the venv exists and matches uv.lock before launching.
exec uv run python main.py "$@"
