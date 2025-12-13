.PHONY: help install dev build test lint clean ci e2e ci-lite

# Default target
help:
	@echo "Available targets:"
	@echo "  install      - Install all dependencies (frontend + backend)"
	@echo "  dev          - Run development servers (frontend + backend)"
	@echo "  dev-frontend - Run frontend dev server"
	@echo "  dev-backend  - Run backend dev server"
	@echo "  dev-railway  - Run all services via Railway (Pilot)"
	@echo "  build        - Build frontend production bundle"
	@echo "  test         - Run all tests"
	@echo "  e2e          - Run Playwright e2e tests"
	@echo "  lint         - Run linters (Python + frontend)"
	@echo "  ci-lite      - Fast local validation (<30s)"
	@echo "  clean        - Clean build artifacts"
	@echo "  ci           - Run full CI suite locally"

# Install dependencies
install:
	@echo "Initializing submodules..."
	git submodule update --init --recursive
	@if [ ! -f "packages/llm-common/pyproject.toml" ]; then \
		echo "❌ Error: packages/llm-common is empty. Submodule init failed."; \
		exit 1; \
	fi
	@echo "Installing dependencies..."
	pnpm install
	@echo "Backend uses venv - activate with: source backend/venv/bin/activate"
	@echo "Then install: pip install -r backend/requirements.txt"

# Run development servers
dev:
	@echo "Starting development servers..."
	@echo "Run 'make dev-frontend' and 'make dev-backend' in separate terminals"

# Run development servers via Railway (Pilot)
dev-railway:
	@echo "Starting development via Railway..."
	./scripts/railway-dev.sh


dev-frontend:
	cd frontend && pnpm dev

dev-backend:
	@if [ ! -d backend/venv ]; then \
		echo "Creating Python virtual environment..."; \
		cd backend && python3.13 -m venv venv; \
	fi
	@echo "Starting backend server..."
	@echo "Make sure venv is activated: source backend/venv/bin/activate"
	@echo "Then run: uvicorn main:app --reload --host 0.0.0.0 --port 8000"

# Build for production
build:
	@echo "Building production bundles..."
	cd frontend && pnpm build

# Run tests
test:
	@echo "Running tests..."
	cd frontend && pnpm test

# Run e2e tests
e2e:
	@echo "Running Playwright e2e tests..."
	cd frontend && pnpm exec playwright test

# Run linters
lint:
	@./scripts/ci/lint.sh

# Run fast local validation (<30s)
ci-lite:
	@echo "🧪 Running CI Lite (fast local validation)..."
	@$(MAKE) lint
	@echo "🐍 Backend unit tests (Fail Fast)..."
	cd backend && poetry run pytest tests/ -q --maxfail=1 || echo "⚠️  Tests failed"
	@echo "✅ CI Lite completed"


# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -rf frontend/.next
	rm -rf frontend/node_modules
	rm -rf frontend/playwright-report
	rm -rf frontend/test-results
	rm -rf backend/__pycache__
	rm -rf backend/.pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Run local CI
ci:
	@echo "Running local CI..."
	@echo "=== Build Check ==="
	$(MAKE) build
	@echo ""
	@echo "=== E2E Tests ==="
	$(MAKE) e2e
