#!/bin/bash
# scripts/jules_setup.sh - Bootstraps repo toolchain for Jules

# Install toolchain via mise
curl https://mise.run | sh
export PATH="$HOME/.local/bin:$PATH"
eval "$(mise activate bash)"
mise trust
mise install --yes

# Backend Setup
echo "🔧 Setting up Backend..."
cd backend
if [ ! -f "poetry.lock" ]; then
    poetry lock
fi
poetry install --no-interaction
cd ..

# Frontend Setup
echo "🔧 Setting up Frontend..."
cd frontend
pnpm install
cd ..

# Mock Environment
echo "🔧 generating mock .env..."
cat <<EOF > .env
DB_HOST=localhost
USE_MOCK_DATA=true
RAILWAY_ENVIRONMENT=development
EOF

echo "✅ Environment ready"
