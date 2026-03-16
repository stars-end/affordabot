#!/bin/bash
set -e

echo "  Bootstrapping Affordabot..."

# 1. Backend uses git-pinned llm-common (no submodule needed)
echo "  Backend uses git-pinned llm-common (via pyproject.toml)."

# 2. Install backend dependencies (if requested)
if [ "$1" == "--install" ]; then
    echo "  Installing backend dependencies..."
    cd backend
    if command -v poetry >/dev/null 2>&1; then
        poetry install --no-interaction --no-root
    else
        echo "  Warning: Poetry not found. Install Poetry first."
        echo "  Then run: cd backend && poetry install"
    fi
    cd ..
fi

echo "  Bootstrap complete! You can now run the app."
