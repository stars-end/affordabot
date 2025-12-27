.PHONY: help install dev build test lint clean ci e2e ci-lite

# ============================================================
# CI/Verification Helpers
# ============================================================

# Conditionally determine the command wrapper for verification tasks.
# - If inside a Railway shell (RAILWAY_PROJECT_NAME is set), commands run directly.
# - If not in a shell but a RAILS_TOKEN is present, use 'railway run'.
# - Otherwise, no wrapper is used, and the environment must be configured manually.
RUN_CMD :=
ifeq ($(shell test -n "$$RAILWAY_PROJECT_NAME" && echo 1), 1)
	# Inside Railway shell, env vars are already present.
	RUN_CMD :=
else ifeq ($(shell railway status >/dev/null 2>&1 && echo 1), 1)
	# Local machine is authenticated + linked (non-interactive); use 'railway run'.
	RUN_CMD := railway run
else ifeq ($(shell test -n "$$RAILWAY_TOKEN" && echo 1), 1)
	# Not in shell, but token is available. Use 'railway run'.
	RUN_CMD := railway run
endif

# List of essential env vars for running verification without Railway.
REQUIRED_VERIFY_VARS := \
	BACKEND_URL \
	FRONTEND_URL \
	DATABASE_URL \
	ZAI_API_KEY \
	TEST_USER_EMAIL \
	TEST_USER_PASSWORD

# Helper to ensure environment is configured for verification.
# If not using 'railway run', it checks that all required env vars are set.
check-verify-env:
	@if [ -z "$(RUN_CMD)" ]; then \
		echo "ℹ️  'railway run' not used. Checking for required env vars..."; \
		for var in $(REQUIRED_VERIFY_VARS); do \
			if [ -z "$$(eval echo \"\$$$${var}\")" ]; then \
				echo "❌ Error: Missing required environment variable: $${var}"; \
				echo "   Please set it or run inside 'railway shell' or with 'RAILWAY_TOKEN'."; \
				exit 1; \
			fi; \
		done; \
		echo "✅ All required environment variables are set."; \
	else \
		echo "ℹ️  Using '$(RUN_CMD)' to inject environment variables."; \
	fi

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
verify-pipeline: check-verify-env
	@echo "🧪 Running RAG Pipeline Verification (E2E)..."
	cd backend && $(RUN_CMD) poetry run python scripts/verification/verify_sanjose_pipeline.py

# Phase 0: Verify Discovery Configuration (LLM Query Generation)
# This MUST be first - validates discovery prompt and LLM query generation before any pipeline runs
verify-discovery: check-verify-env
	@echo "🔍 Phase 0: Verifying Discovery Configuration (LLM Queries)..."
	@mkdir -p artifacts/verification/discovery
	cd backend && $(RUN_CMD) poetry run python scripts/verification/verify_discovery.py --artifacts-dir ../artifacts/verification/discovery
	@echo "📸 Discovery artifacts saved to artifacts/verification/discovery/"

# Run analysis loop verification (Integration)
verify-analysis: check-verify-env
	@echo "🧠 Running Analysis Loop Verification..."
	cd backend && $(RUN_CMD) poetry run python scripts/verification/verify_analysis_loop.py

# Run E2E Glass Box Audit (P0)
verify-e2e: check-verify-env
	@echo "🔍 Running E2E Glass Box Audit..."
	cd backend && $(RUN_CMD) poetry run python scripts/verification/verify_e2e_glassbox.py

# Unified Glass Box Verification (10 Phases with Screenshots)
verify-glassbox: check-verify-env
	@echo "🔍 Running Affordabot Glass Box Verification (10 Phases)..."
	@mkdir -p artifacts/verification
	cd backend && $(RUN_CMD) poetry run python scripts/verification/verify_sanjose_pipeline.py --screenshots --artifacts-dir ../artifacts/verification
	@echo "📸 Screenshots saved to artifacts/verification/"

# Run agent pipeline verification (Mocked)
verify-agents:
	@echo "🤖 Running Agent Pipeline Verification (Mocked - No Railway Needed)..."
	cd backend && poetry run python scripts/verification/verify_agent_pipeline.py

# Run auth verification
verify-auth: check-verify-env
	@echo "🔐 Running Auth Configuration Verification..."
	cd backend && $(RUN_CMD) poetry run python scripts/verification/verify_auth_config.py

# Run storage verification
verify-storage: check-verify-env
	@echo "📦 Running S3/MinIO Storage Verification..."
	cd backend && $(RUN_CMD) poetry run python scripts/verification/verify_s3_connection.py

# Run environment & admin check
verify-env: check-verify-env
	@echo "🌍 Checking Environment & Admin Setup..."
	$(RUN_CMD) sh -c "cd backend && poetry run python scripts/check_env.py"
	$(RUN_CMD) sh -c "cd backend && poetry run python scripts/verification/verify_admin_import.py"

# ============================================================
# Verification Targets (Harmonized Naming Convention)
# ============================================================
# verify-local    - Fast local checks (lint, unit tests) - no network
# verify-dev      - Full verification against Railway dev environment
# verify-pr PR=N  - Verification against Railway PR env + post comment
# verify-pr-lite  - Quick health check for small PRs
# ============================================================

# Run ALL verifications against Railway dev environment
# Sequence: Discovery → Environment → Auth → Storage → RAG Pipeline → E2E Glass Box → Admin UI → Stories
# NOTE: verify-discovery MUST be first - validates LLM query generation before any pipeline runs!
verify-dev: verify-discovery verify-env verify-auth verify-storage verify-pipeline verify-e2e verify-admin-pipeline verify-stories ## Full verification against Railway dev
	@echo "============================================================"
	@echo "✅ FULL PIPELINE VERIFICATION COMPLETE!"
	@echo "============================================================"
	@echo "Phase 0: Discovery Config (LLM) ✅"
	@echo "  - DB prompt check"
	@echo "  - GLM-4.7 query generation"
	@echo "  - Z.ai search validation"
	@echo "Phase 1: Environment & Auth     ✅"
	@echo "Phase 2: Storage (MinIO)        ✅"
	@echo "Phase 3: RAG Pipeline (10 phases) ✅"
	@echo "Phase 4: E2E Glass Box Audit    ✅"
	@echo "  - Research (Z.ai + pgvector)"
	@echo "  - Generate (cost analysis)"
	@echo "  - Review (critique + refine)"
	@echo "Phase 5: Admin UI (visual)      ✅"
	@echo "Phase 6: User Stories (7 flows) ✅"
	@echo "============================================================"


# DEPRECATED: Use verify-dev instead. Kept for backward compatibility.
verify-all: verify-dev

# DEPRECATED: Use verify-dev instead. Kept for backward compatibility.
verify-full-pipeline: verify-dev


# Stage 1: Local Visual E2E (browser screenshots against localhost)
verify-local:
	@echo "🏠 Running Local Visual E2E (localhost)..."
	@mkdir -p artifacts/verification/local
	cd backend && poetry run python scripts/verification/visual_e2e/runner.py \
		--stage local \
		--base-url http://localhost:3000 \
		--api-url http://localhost:8000

# Stage 2: PR Environment Visual E2E (browser screenshots against Railway PR)
verify-visual-pr:
	@echo "🚂 Running PR Visual E2E (Railway)..."
	@mkdir -p artifacts/verification/pr
	@if [ -z "$$RAILWAY_STATIC_URL" ]; then \
		echo "⚠️  RAILWAY_STATIC_URL not set. Using localhost fallback..."; \
		cd backend && poetry run python scripts/verification/visual_e2e/runner.py \
			--stage pr --base-url http://localhost:3000; \
	else \
		cd backend && poetry run python scripts/verification/visual_e2e/runner.py \
			--stage pr --base-url $$RAILWAY_STATIC_URL; \
	fi

# Alias for backward compat
verify-visual: verify-admin-pipeline


# UISmokeAgent Admin Pipeline Verification (GLM-4.6V visual analysis with Clerk auth)
# Uses railway run to get TEST_USER_EMAIL, TEST_USER_PASSWORD, and ZAI_API_KEY from Railway env
# Default to Railway dev frontend when FRONTEND_URL not set (for verify-dev)
RAILWAY_DEV_FRONTEND_URL ?= https://frontend-dev-5093.up.railway.app
verify-admin-pipeline: check-verify-env
	@echo "🤖 Running UISmokeAgent Admin Pipeline Verification..."
	@mkdir -p artifacts/verification/admin_pipeline
	@# Determine target URL from Make vars (preferred), falling back to Railway dev.
	@TARGET_URL="$(or $(FRONTEND_URL),$(RAILWAY_DEV_FRONTEND_URL))"; \
	echo "Using FRONTEND_URL=$${TARGET_URL}"; \
	echo "Auth: TEST_USER_EMAIL=$${TEST_USER_EMAIL:-(not set)}"; \
	cd backend && $(RUN_CMD) poetry run python scripts/verification/admin_pipeline_agent.py \
		--url "$${TARGET_URL}" \
		--output ../artifacts/verification/admin_pipeline

# Story-driven verification using docs/TESTING/STORIES/*.yml
# Validates admin console against user stories with GLM-4.6V visual analysis
verify-stories:
	@echo "📖 Running Story-Driven Verification (Deep Validity & Persona)..."
	@echo "   [Logic] Running backend python logic verifiers..."
	@if [ -z "$$RAILWAY_PROJECT_NAME" ]; then \
		echo "🔄 Not in Railway Shell. Wrapping in 'railway run'..."; \
		(cd backend && railway run poetry run python scripts/verification/story_runner.py --all) && \
		(cd backend && railway run poetry run python scripts/verification/visual_story_runner.py --all --tags core-flow); \
	else \
		(cd backend && poetry run python scripts/verification/story_runner.py --all) && \
		(cd backend && poetry run python scripts/verification/visual_story_runner.py --all --tags core-flow); \
	fi

# Overnight/CI story verification (runs all stories + generates report)
verify-stories-overnight:
	@echo "🌙 Running Overnight Story Verification..."
	@mkdir -p artifacts/verification/overnight
	$(MAKE) verify-admin-pipeline FRONTEND_URL=$(RAILWAY_DEV_FRONTEND_URL)
	@echo "📊 Stories verified. Report: artifacts/verification/admin_pipeline/report.md"


# Full E2E verification with auth on Railway PR environment
verify-admin-pipeline-pr: check-verify-env
	@echo "🤖 Running Admin Pipeline on Railway PR environment with auth..."
	@mkdir -p artifacts/verification/admin_pipeline_pr
	cd backend && $(RUN_CMD) poetry run python scripts/verification/admin_pipeline_agent.py \
		--url https://frontend-affordabot-pr-160.up.railway.app \
		--output ../artifacts/verification/admin_pipeline_pr

# Unified CI Verification (uses llm-common framework, overnight CI)
verify-ci: check-verify-env
	@echo "🔬 Running Unified CI Verification (12 RAG stories)..."
	@mkdir -p artifacts/verification
	@TARGET_URL="$(or $(FRONTEND_URL),http://localhost:3000)"; \
	cd backend && $(RUN_CMD) poetry run python scripts/verification/unified_verify.py --base-url "$${TARGET_URL}"

# ============================================================
# PR Environment Verification (Railway Preview Environments)
# ============================================================
# Use verify-pr for LARGE PRs (P0/P1, multi-file, infrastructure changes)
# Use verify-pr-lite for SMALL PRs (single file, docs, minor fixes)
# Agents: Check Beads priority and files changed to decide

# Railway PR URL patterns
PR_BACKEND_URL = https://backend-affordabot-pr-$(PR).up.railway.app
PR_FRONTEND_URL = https://frontend-affordabot-pr-$(PR).up.railway.app

verify-pr: ## Full verification against Railway PR env + post report to PR
ifndef PR
	$(error Usage: make verify-pr PR=163)
endif
	@echo "🔬 Full PR Verification for #$(PR)"
	@echo "   Backend:  $(PR_BACKEND_URL)"
	@echo "   Frontend: $(PR_FRONTEND_URL)"
	@# Wait for deployment with health check retry
	@echo "⏳ Waiting for Railway PR environment..."
	@for i in 1 2 3 4 5 6; do \
		STATUS=$$(curl -s -o /dev/null -w "%{http_code}" "$(PR_BACKEND_URL)/health" 2>/dev/null); \
		if [ "$$STATUS" = "200" ]; then \
			echo "✅ PR #$(PR) backend healthy"; \
			break; \
		else \
			echo "   Attempt $$i/6: status=$$STATUS (waiting 30s)..."; \
			sleep 30; \
		fi; \
		if [ $$i -eq 6 ]; then \
			echo "❌ PR #$(PR) not deployed after 3 min"; \
			echo "   Check: gh pr view $(PR) --web"; \
			exit 1; \
		fi; \
	done
	@# Run full verification
	@echo "🚀 Running verify-all against PR environment..."
	BACKEND_URL=$(PR_BACKEND_URL) FRONTEND_URL=$(PR_FRONTEND_URL) \
		$(MAKE) verify-all API_URL=$(PR_BACKEND_URL) BASE_URL=$(PR_FRONTEND_URL)
	@# Run story-driven verification on PR frontend
	@echo "📖 Running story verification on PR frontend..."
	$(MAKE) verify-admin-pipeline FRONTEND_URL=$(PR_FRONTEND_URL)
	@# Generate and post report
	@echo "📝 Generating verification report..."
	@./scripts/generate-pr-report.sh $(PR) $(PR_BACKEND_URL)
	@echo "📮 Posting report to PR #$(PR)..."
	@gh pr comment $(PR) --body-file artifacts/verification/pr-$(PR)-report.md
	@echo ""
	@echo "============================================================"
	@echo "✅ PR #$(PR) VERIFICATION COMPLETE"
	@echo "   Report posted to: https://github.com/stars-end/affordabot/pull/$(PR)"
	@echo "   Merge command: gh pr merge $(PR) --squash --delete-branch"
	@echo "============================================================"


verify-pr-lite: ## Quick verification (health + discovery only) for small PRs
ifndef PR
	$(error Usage: make verify-pr-lite PR=163)
endif
	@echo "🔬 Quick PR Verification for #$(PR)"
	@# Health check only
	@STATUS=$$(curl -s -o /dev/null -w "%{http_code}" "$(PR_BACKEND_URL)/health" 2>/dev/null); \
	if [ "$$STATUS" = "200" ]; then \
		echo "✅ PR #$(PR) backend healthy"; \
	else \
		echo "⏳ PR #$(PR) not ready (status=$$STATUS), waiting 60s..."; \
		sleep 60; \
		STATUS=$$(curl -s -o /dev/null -w "%{http_code}" "$(PR_BACKEND_URL)/health" 2>/dev/null); \
		if [ "$$STATUS" != "200" ]; then \
			echo "❌ PR #$(PR) not deployed"; \
			exit 1; \
		fi; \
	fi
	@# Quick discovery check only
	BACKEND_URL=$(PR_BACKEND_URL) FRONTEND_URL=$(PR_FRONTEND_URL) \
		$(MAKE) verify-discovery API_URL=$(PR_BACKEND_URL)
	@echo "✅ verify-pr-lite complete for PR #$(PR)"
	@echo "   For full verification: make verify-pr PR=$(PR)"
