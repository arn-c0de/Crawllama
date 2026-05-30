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

# `uv run` ensures the .venv exists and matches uv.lock before launching.
exec uv run python main.py "$@"
