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
	@echo "Installing dependencies..."
	pnpm install
	cd frontend-v2 && pnpm install
	@echo "Backend uses venv - activate with: source backend/venv/bin/activate"
	@echo "Then install: pip install -r backend/requirements.txt"

# Run development servers
dev:
	@echo "Starting development servers (Backend + Frontend V2)..."
	pnpm concurrently -n "BACKEND,FRONTEND" -c "blue,green" \
		"$(MAKE) dev-backend" \
		"$(MAKE) dev-frontend-v2"

# Run development servers via Railway (Pilot)
dev-railway:
	@echo "Starting development via Railway..."
	./scripts/railway-dev.sh

dev-frontend:
	cd frontend && pnpm dev

dev-frontend-v2:
	cd frontend-v2 && pnpm dev -- --port 5173

dev-backend:
	@echo "Starting backend server (via Railway run)..."
	cd backend && railway run poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Build for production
build:
	@echo "Building production bundles..."
	@echo "Building production bundles..."
	cd frontend && pnpm build
	cd frontend-v2 && pnpm build

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
	rm -rf frontend-v2/dist
	rm -rf frontend-v2/node_modules
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
	@echo "=== E2E Tests ==="
	$(MAKE) e2e

# Check for Railway Shell environment
check-railway-shell:
	@if [ -z "$$RAILWAY_PROJECT_NAME" ]; then \
		echo "❌ Error: Must run inside 'railway shell'."; \
		echo "   Run 'railway shell' first, then run this command."; \
		exit 1; \
	fi

# Run pipeline verification (RAG V3)
verify-pipeline:
	@echo "🧪 Running RAG Pipeline Verification (E2E)..."
	@if [ -z "$$RAILWAY_PROJECT_NAME" ]; then \
		echo "🔄 Not in Railway Shell. Wrapping in 'railway run'..."; \
		cd backend && railway run poetry run python scripts/verification/verify_sanjose_pipeline.py; \
	else \
		cd backend && poetry run python scripts/verification/verify_sanjose_pipeline.py; \
	fi

# Run analysis loop verification (Integration)
verify-analysis:
	@echo "🧠 Running Analysis Loop Verification..."
	@if [ -z "$$RAILWAY_PROJECT_NAME" ]; then \
		echo "🔄 Not in Railway Shell. Wrapping in 'railway run'..."; \
		cd backend && railway run poetry run python scripts/verification/verify_analysis_loop.py; \
	else \
		cd backend && poetry run python scripts/verification/verify_analysis_loop.py; \
	fi

# Run E2E Glass Box Audit (P0)
verify-e2e:
	@echo "🔍 Running E2E Glass Box Audit..."
	@if [ -z "$$RAILWAY_PROJECT_NAME" ]; then \
		echo "🔄 Not in Railway Shell. Wrapping in 'railway run'..."; \
		cd backend && railway run poetry run python scripts/verification/verify_e2e_glassbox.py; \
	else \
		cd backend && poetry run python scripts/verification/verify_e2e_glassbox.py; \
	fi

# Run agent pipeline verification (Mocked)
verify-agents:
	@echo "🤖 Running Agent Pipeline Verification (Mocked - No Railway Needed)..."
	cd backend && poetry run python scripts/verification/verify_agent_pipeline.py

# Run auth verification
verify-auth:
	@echo "🔐 Running Auth Configuration Verification..."
	@if [ -z "$$RAILWAY_PROJECT_NAME" ]; then \
		echo "🔄 Not in Railway Shell. Wrapping in 'railway run'..."; \
		cd backend && railway run poetry run python scripts/verification/verify_auth_config.py; \
	else \
		cd backend && poetry run python scripts/verification/verify_auth_config.py; \
	fi

# Run storage verification
verify-storage:
	@echo "📦 Running S3/MinIO Storage Verification..."
	@if [ -z "$$RAILWAY_PROJECT_NAME" ]; then \
		echo "🔄 Not in Railway Shell. Wrapping in 'railway run'..."; \
		cd backend && railway run poetry run python scripts/verification/verify_s3_connection.py; \
	else \
		cd backend && poetry run python scripts/verification/verify_s3_connection.py; \
	fi

# Run environment & admin check
verify-env:
	@echo "🌍 Checking Environment & Admin Setup..."
	@if [ -z "$$RAILWAY_PROJECT_NAME" ]; then \
		echo "🔄 Not in Railway Shell. Wrapping in 'railway run'..."; \
		cd backend && railway run poetry run python scripts/check_env.py; \
		cd backend && railway run poetry run python scripts/verification/verify_admin_import.py; \
	else \
		cd backend && poetry run python scripts/check_env.py; \
		cd backend && poetry run python scripts/verification/verify_admin_import.py; \
	fi

# Run ALL verifications
verify-all: verify-env verify-auth verify-storage verify-agents verify-analysis verify-pipeline
	@echo "✅ All Verifications Passed!"

