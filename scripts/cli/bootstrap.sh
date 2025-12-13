#!/bin/bash
set -e

echo "🚀 Bootstrapping Affordabot..."

# 1. Initialize submodules
echo "📦 Initializing submodules..."
git submodule update --init --recursive

# 2. Check for backend/llm-common
if [ ! -f "packages/llm-common/pyproject.toml" ]; then
    echo "❌ Error: packages/llm-common is empty. Submodule init failed."
    exit 1
fi

echo "✅ Submodules ready."

# 3. Install backend dependencies (if requested)
if [ "$1" == "--install" ]; then
    echo "🐍 Installing backend dependencies..."
    cd backend
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
    else
        echo "⚠️ No requirements.txt found in backend/"
    fi
    cd ..
fi

echo "✨ Bootstrap complete! You can now run the app."
