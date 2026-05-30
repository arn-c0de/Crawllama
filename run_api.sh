#!/bin/bash
# CrawlLama API Server - Linux/macOS
# Runs the FastAPI server via uv (auto-syncs the environment + the `api` extra).

if ! command -v uv &> /dev/null; then
    echo "ERROR: uv is not installed!"
    echo "Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "Then run ./setup.sh to provision the environment."
    echo ""
    exit 1
fi

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

# --extra api ensures fastapi/uvicorn/starlette are present regardless of how
# the environment was last synced.
exec uv run --extra api python app.py
