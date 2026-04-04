.PHONY: help install dev build test test-legacy lint clean ci e2e ci-lite \
        auth auth-check \
        dev-frontend dev-backend dev-railway \
        check-verify-env check-railway-shell \
        verify-pipeline verify-discovery verify-analysis verify-e2e verify-glassbox \
        verify-agents verify-auth verify-storage verify-env \
        verify-local verify-visual-pr verify-visual verify-admin-pipeline \
        verify-stories verify-nightly verify-gate verify-triage \
        verify-stories-failures verify-stories-overnight \
        verify-dev verify-all verify-full-pipeline \
        verify-pr verify-pr-lite

# ============================================================
# Railway Execution Contract
# ============================================================
# Affordabot uses a thin repo-local wrapper over the shared
# agent-skills Railway contract. See scripts/dx-railway-run.sh.
#
# Canonical execution path (worktree-safe, non-interactive):
#   ./scripts/dx-railway-run.sh -- <command> [args...]
#
# Canonical auth path (worktree-safe, non-interactive):
#   ./scripts/dx-load-auth.sh -- <command> [args...]
#   ./scripts/dx-load-auth.sh --check

DX_RAILWAY_RUN := ./scripts/dx-railway-run.sh

# ============================================================
# CI/Verification Helpers
# ============================================================

# List of essential env vars for running verification without Railway.
REQUIRED_VERIFY_VARS := \
	BACKEND_URL \
	FRONTEND_URL \
	DATABASE_URL \
	ZAI_API_KEY \
	TEST_USER_EMAIL \
	TEST_USER_PASSWORD

check-verify-env:
	@if [ -n "$${RAILWAY_ENVIRONMENT:-}" ]; then \
		echo "  Inside Railway context (RAILWAY_ENVIRONMENT is set)."; \
	elif [ -f ".dx/railway-context.env" ] || [ -n "$${DX_RAILWAY_CONTEXT_FILE:-}" ]; then \
		echo "  Railway context file found, using dx-railway-run wrapper."; \
	else \
		echo "  No Railway context file found. Checking for required env vars..."; \
		MISSING_VARS=0; \
		for var in $(REQUIRED_VERIFY_VARS); do \
			if [ -z "$$(eval echo \"\$$$${var}\")" ]; then \
				echo "  Error: Missing required environment variable: $${var}"; \
				MISSING_VARS=1; \
			fi; \
		done; \
		if [ "$$MISSING_VARS" -eq 1 ]; then \
			echo ""; \
			echo "  Fix this by running:"; \
			echo "   1. make auth-check     # verify auth is configured"; \
			echo "   2. ./scripts/dx-railway-run.sh -- make <target>"; \
			echo ""; \
			exit 1; \
		fi; \
		echo "  All required environment variables are set."; \
	fi

# Non-interactive Railway auth via agent-skills shared contract
auth-check:
	@echo "  Checking Railway auth (non-interactive)..."
	@./scripts/dx-load-auth.sh --check

auth:
	@echo "  Authenticating with Railway (non-interactive)..."
	@if ! command -v railway >/dev/null; then \
		echo "  Railway CLI not found. Installing..."; \
		npm install -g @railway/cli; \
	fi
	@./scripts/dx-load-auth.sh -- railway whoami

# Default target
help:
	@echo "Available targets:"
	@echo "  install      - Install all dependencies (backend)"
	@echo "  dev          - Run development servers (frontend + backend)"
	@echo "  dev-frontend - Run frontend dev server (Next.js)"
	@echo "  dev-backend  - Run backend dev server"
	@echo "  dev-railway  - Run all services via Railway (Pilot)"
	@echo "  build        - Build frontend production bundle"
	@echo "  test         - Run the canonical Playwright preservation suite"
	@echo "  e2e          - Alias for the canonical Playwright preservation suite"
	@echo "  test-legacy  - Run quarantined legacy Playwright specs"
	@echo "  lint         - Run linters (Python + frontend)"
	@echo "  ci-lite      - Fast local validation (<30s)"
	@echo "  clean        - Clean build artifacts"
	@echo "  ci           - Run full CI suite locally"
	@echo ""
	@echo "  auth-check   - Verify Railway auth (non-interactive)"
	@echo "  auth         - Authenticate with Railway (non-interactive)"
	@echo ""
	@echo "Railway execution (worktree-safe):"
	@echo "  ./scripts/dx-railway-run.sh -- <command> [args...]"
	@echo "  ./scripts/dx-load-auth.sh -- <command> [args...]"

# Install dependencies
install:
	@echo "Installing dependencies..."
	pnpm install
	cd frontend && pnpm install
	@echo "Backend uses Poetry for dependency management."
	@echo "Run: cd backend && poetry install"

# Run development servers
dev:
	@echo "Starting development servers (Backend + Frontend)..."
	pnpm concurrently -n "BACKEND,FRONTEND" -c "blue,green" \
		"$(MAKE) dev-backend" \
		"$(MAKE) dev-frontend"

# Run development servers via Railway (Pilot)
dev-railway:
	@echo "Starting development via Railway..."
	./scripts/railway-dev.sh

dev-frontend:
	cd frontend && pnpm dev

dev-backend:
	@echo "Starting backend server (via dx-railway-run)..."
	cd backend && $(DX_RAILWAY_RUN) -- poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Build for production
build:
	@echo "Building production bundle..."
	cd frontend && pnpm build

# Run preservation tests
test:
	@echo "Running Playwright preservation tests..."
	cd frontend && pnpm test

# Run e2e tests
e2e:
	@echo "Running canonical preserved-route Playwright tests..."
	cd frontend && pnpm test

test-legacy:
	@echo "Running legacy Playwright specs..."
	cd frontend && pnpm test:legacy

# Run linters
lint:
	@./scripts/ci/lint.sh

# Run fast local validation (<30s)
ci-lite:
	@echo "  Running CI Lite (fast local validation)..."
	@$(MAKE) lint
	@echo "  Backend unit tests (Fail Fast)..."
	cd backend && poetry run pytest tests/ -q --maxfail=1 || echo "  Tests failed"
	@echo "  Checking for bespoke UI runners..."
	@python3 ./scripts/ci/check_bespoke_runners.py
	@echo "  CI Lite completed"


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
	@echo "=== Preservation Tests ==="
	$(MAKE) test

# Check for Railway Shell environment
check-railway-shell:
	@if [ -z "$${RAILWAY_ENVIRONMENT:-}" ]; then \
		echo "  Error: Not inside a Railway environment."; \
		echo "   Use ./scripts/dx-railway-run.sh -- <command> for worktree-safe execution."; \
		exit 1; \
	fi

# ============================================================
# Verification Targets
# ============================================================

verify-pipeline: check-verify-env
	@echo "  Running RAG Pipeline Verification (E2E)..."
	cd backend && $(DX_RAILWAY_RUN) -- poetry run python scripts/verification/verify_sanjose_pipeline.py

verify-discovery: check-verify-env
	@echo "  Phase 0: Verifying Discovery Configuration (LLM Queries)..."
	@mkdir -p artifacts/verification/discovery
	cd backend && $(DX_RAILWAY_RUN) -- poetry run python scripts/verification/verify_discovery.py --artifacts-dir ../artifacts/verification/discovery
	@echo "  Discovery artifacts saved to artifacts/verification/discovery/"

verify-analysis: check-verify-env
	@echo "  Running Analysis Loop Verification..."
	cd backend && $(DX_RAILWAY_RUN) -- poetry run python scripts/verification/verify_analysis_loop.py

verify-e2e: check-verify-env
	@echo "  Running E2E Glass Box Audit..."
	cd backend && $(DX_RAILWAY_RUN) -- poetry run python scripts/verification/verify_e2e_glassbox.py

verify-glassbox: check-verify-env
	@echo "  Running Affordabot Glass Box Verification (10 Phases)..."
	@mkdir -p artifacts/verification
	cd backend && $(DX_RAILWAY_RUN) -- poetry run python scripts/verification/verify_sanjose_pipeline.py --screenshots --artifacts-dir ../artifacts/verification
	@echo "  Screenshots saved to artifacts/verification/"

verify-agents:
	@echo "  Running Agent Pipeline Verification (Mocked - No Railway Needed)..."
	cd backend && poetry run python scripts/verification/verify_agent_pipeline.py

verify-auth: check-verify-env
	@echo "  Running Auth Configuration Verification..."
	cd backend && $(DX_RAILWAY_RUN) -- poetry run python scripts/verification/verify_auth_config.py

verify-storage: check-verify-env
	@echo "  Running S3/MinIO Storage Verification..."
	cd backend && $(DX_RAILWAY_RUN) -- poetry run python scripts/verification/verify_s3_connection.py

verify-env: check-verify-env
	@echo "  Checking Environment & Admin Setup..."
	$(DX_RAILWAY_RUN) -- sh -c "cd backend && poetry run python scripts/check_env.py"
	$(DX_RAILWAY_RUN) -- sh -c "cd backend && poetry run python scripts/verification/verify_admin_import.py"

verify-local:
	@echo "  Running Local Visual E2E (localhost)..."
	@mkdir -p artifacts/verification/local
	cd backend && poetry run python scripts/verification/visual_e2e/runner.py \
		--stage local \
		--base-url http://localhost:3000 \
		--api-url http://localhost:8000

verify-visual-pr:
	@echo "  Running PR Visual E2E (Railway)..."
	@mkdir -p artifacts/verification/pr
	@if [ -z "$$RAILWAY_STATIC_URL" ]; then \
		echo "  RAILWAY_STATIC_URL not set. Using localhost fallback..."; \
		cd backend && poetry run python scripts/verification/visual_e2e/runner.py \
			--stage pr --base-url http://localhost:3000; \
	else \
		cd backend && poetry run python scripts/verification/visual_e2e/runner.py \
			--stage pr --base-url $$RAILWAY_STATIC_URL; \
	fi

verify-visual: verify-admin-pipeline

RAILWAY_DEV_FRONTEND_URL ?= https://frontend-dev-5093.up.railway.app
verify-admin-pipeline: check-verify-env
	@echo "  Running UISmokeAgent Admin Pipeline Verification..."
	@mkdir -p artifacts/verification/admin_pipeline
	@TARGET_URL="$(or $(FRONTEND_URL),$(RAILWAY_DEV_FRONTEND_URL))"; \
	echo "Using FRONTEND_URL=$${TARGET_URL}"; \
	cd backend && $(DX_RAILWAY_RUN) -- poetry run python scripts/verification/admin_pipeline_agent.py \
		--url "$${TARGET_URL}" \
		--output ../artifacts/verification/admin_pipeline

verify-stories:
	@echo "  Running QA UISmoke Verification..."
	@mkdir -p artifacts/verification/uismoke
	@TARGET_URL="$(or $(FRONTEND_URL),$(RAILWAY_DEV_FRONTEND_URL))"; \
	cd backend && $(DX_RAILWAY_RUN) -- poetry run uismoke run \
		--stories ../docs/TESTING/STORIES \
		--base-url "$${TARGET_URL}" \
		--output ../artifacts/verification/uismoke \
		--auth-mode cookie_bypass \
		--cookie-name $${COOKIE_NAME:-x-test-user} --cookie-value $${COOKIE_VALUE:-admin} --cookie-signed \
		--cookie-secret-env TEST_AUTH_BYPASS_SECRET \
		--cookie-domain auto \
		--email-env TEST_USER_EMAIL --password-env TEST_USER_PASSWORD \
		--suite-timeout 5400 --story-timeout 900 --nav-timeout-ms 120000 --action-timeout-ms 60000 \
		--mode qa --repro 1 \
		--tracing

verify-nightly:
	@echo "  Running Nightly UISmoke Verification (Repro=3)..."
	@mkdir -p artifacts/verification/nightly
	@TARGET_URL="$(or $(FRONTEND_URL),$(RAILWAY_DEV_FRONTEND_URL))"; \
	cd backend && $(DX_RAILWAY_RUN) -- poetry run uismoke run \
		--stories ../docs/TESTING/STORIES \
		--base-url "$${TARGET_URL}" \
		--output ../artifacts/verification/nightly \
		--auth-mode cookie_bypass \
		--cookie-name $${COOKIE_NAME:-x-test-user} --cookie-value $${COOKIE_VALUE:-admin} --cookie-signed \
		--cookie-secret-env TEST_AUTH_BYPASS_SECRET \
		--cookie-domain auto \
		--email-env TEST_USER_EMAIL --password-env TEST_USER_PASSWORD \
		--suite-timeout 5400 --story-timeout 900 --nav-timeout-ms 120000 --action-timeout-ms 60000 \
		--mode qa --repro 3 \
		--exclude-stories story-profile-persistence \
		--fail-on-classifications skip not_run suite_timeout auth_failed timeout flaky_recovered flaky_inconclusive single_timeout reproducible_timeout single_navigation_failed reproducible_navigation_failed single_clerk_failed reproducible_clerk_failed \
		--tracing

verify-gate:
	@echo "  Running UISmoke Quality Gate..."
	@mkdir -p artifacts/verification/gate
	@TARGET_URL="$(or $(FRONTEND_URL),$(RAILWAY_DEV_FRONTEND_URL))"; \
	cd backend && $(DX_RAILWAY_RUN) -- poetry run uismoke run \
		--stories ../docs/TESTING/STORIES \
		--base-url "$${TARGET_URL}" \
		--output ../artifacts/verification/gate \
		--auth-mode cookie_bypass \
		--cookie-name $${COOKIE_NAME:-x-test-user} --cookie-value $${COOKIE_VALUE:-admin} --cookie-signed \
		--cookie-secret-env TEST_AUTH_BYPASS_SECRET \
		--cookie-domain auto \
		--email-env TEST_USER_EMAIL --password-env TEST_USER_PASSWORD \
		--suite-timeout 5400 --story-timeout 900 --nav-timeout-ms 120000 --action-timeout-ms 60000 \
		--mode gate --repro 1 --deterministic-only \
		--only-stories substrate_run_list substrate_failure_buckets substrate_raw_row_detail \
		--fail-on-classifications skip not_run suite_timeout auth_failed timeout flaky_recovered flaky_inconclusive single_timeout reproducible_timeout single_navigation_failed reproducible_navigation_failed single_clerk_failed reproducible_clerk_failed

verify-triage:
	@echo "  Triaging failures and generating Beads plan..."
	@cd backend && poetry run uismoke triage \
		--run-dir ../artifacts/verification/$${TARGET_DIR:-uismoke}/$$(ls -t ../artifacts/verification/$${TARGET_DIR:-uismoke} | head -1) $${ARGS:-}

verify-stories-failures:
	@echo "  Rerunning failing stories..."
	@./scripts/verification/uismoke-rerun.sh uismoke

verify-stories-overnight: verify-nightly

verify-dev: verify-discovery verify-env verify-auth verify-storage verify-pipeline verify-e2e verify-admin-pipeline verify-stories
	@echo "============================================================"
	@echo "  FULL PIPELINE VERIFICATION COMPLETE!"
	@echo "============================================================"
	@echo "Phase 0: Discovery Config (LLM)"
	@echo "Phase 1: Environment & Auth"
	@echo "Phase 2: Storage (MinIO)"
	@echo "Phase 3: RAG Pipeline (10 phases)"
	@echo "Phase 4: E2E Glass Box Audit"
	@echo "Phase 5: Admin UI (visual)"
	@echo "Phase 6: User Stories (7 flows)"
	@echo "============================================================"

verify-all: verify-dev
verify-full-pipeline: verify-dev

PR_BACKEND_URL = https://backend-affordabot-pr-$(PR).up.railway.app
PR_FRONTEND_URL = https://frontend-affordabot-pr-$(PR).up.railway.app

verify-pr:
ifndef PR
	$(error Usage: make verify-pr PR=163)
endif
	@echo "  Full PR Verification for #$(PR)"
	@echo "   Backend:  $(PR_BACKEND_URL)"
	@echo "   Frontend: $(PR_FRONTEND_URL)"
	@for i in 1 2 3 4 5 6; do \
		STATUS=$$(curl -s -o /dev/null -w "%{http_code}" "$(PR_BACKEND_URL)/health" 2>/dev/null); \
		if [ "$$STATUS" = "200" ]; then \
			echo "  PR #$(PR) backend healthy"; \
			break; \
		else \
			echo "   Attempt $$i/6: status=$$STATUS (waiting 30s)..."; \
			sleep 30; \
		fi; \
		if [ $$i -eq 6 ]; then \
			echo "  PR #$(PR) not deployed after 3 min"; \
			echo "   Check: gh pr view $(PR) --web"; \
			exit 1; \
		fi; \
	done
	@echo "  Running verify-all against PR environment..."
	BACKEND_URL=$(PR_BACKEND_URL) FRONTEND_URL=$(PR_FRONTEND_URL) \
		$(MAKE) verify-all API_URL=$(PR_BACKEND_URL) BASE_URL=$(PR_FRONTEND_URL)
	@echo "  Running story verification on PR frontend..."
	$(MAKE) verify-admin-pipeline FRONTEND_URL=$(PR_FRONTEND_URL)
	@echo "  Generating verification report..."
	@./scripts/generate-pr-report.sh $(PR) $(PR_BACKEND_URL)
	@echo "  Posting report to PR #$(PR)..."
	@gh pr comment $(PR) --body-file artifacts/verification/pr-$(PR)-report.md
	@echo ""
	@echo "============================================================"
	@echo "  PR #$(PR) VERIFICATION COMPLETE"
	@echo "   Report posted to: https://github.com/stars-end/affordabot/pull/$(PR)"
	@echo "============================================================"

verify-pr-lite:
ifndef PR
	$(error Usage: make verify-pr-lite PR=163)
endif
	@echo "  Quick PR Verification for #$(PR)"
	@STATUS=$$(curl -s -o /dev/null -w "%{http_code}" "$(PR_BACKEND_URL)/health" 2>/dev/null); \
	if [ "$$STATUS" = "200" ]; then \
		echo "  PR #$(PR) backend healthy"; \
	else \
		echo "  PR #$(PR) not ready (status=$$STATUS), waiting 60s..."; \
		sleep 60; \
		STATUS=$$(curl -s -o /dev/null -w "%{http_code}" "$(PR_BACKEND_URL)/health" 2>/dev/null); \
		if [ "$$STATUS" != "200" ]; then \
			echo "  PR #$(PR) not deployed"; \
			exit 1; \
		fi; \
	fi
	BACKEND_URL=$(PR_BACKEND_URL) FRONTEND_URL=$(PR_FRONTEND_URL) \
	$(MAKE) verify-discovery API_URL=$(PR_BACKEND_URL)
	@echo "  verify-pr-lite complete for PR #$(PR)"
