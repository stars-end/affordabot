# CI and Testing Infrastructure

**Last Updated**: 2025-12-07
**Status**: Complete and Operational

## Overview

Comprehensive CI/CD and testing infrastructure for affordabot, including local development, automated testing, and GitHub Actions continuous integration.

## Local Development

### Makefile Commands

All common development tasks are available via Make:

```bash
# View all available commands
make help

# Install dependencies
make install          # Installs pnpm dependencies
                     # Backend uses venv: source backend/venv/bin/activate
                     # Then: pip install -r backend/requirements.txt

# Development
make dev-frontend    # Start Next.js dev server (localhost:3000)
make dev-backend     # Instructions for backend setup

# Building
make build           # Build frontend production bundle

# Testing
make test            # Run all Playwright tests
make e2e             # Run Playwright E2E tests explicitly

# CI
make ci              # Run full CI suite locally (build + e2e)

# Cleanup
make clean           # Remove build artifacts and caches
```

### Running Local CI

Before pushing, verify everything works:

```bash
# Full CI suite (what GitHub Actions runs)
make ci

# Expected output:
# === Build Check ===
# ✓ Route (app)                                  196 kB         102 kB
# ✓ Route (app)/admin                            136 kB         102 kB
#
# === E2E Tests ===
# ✓  [chromium] › smoke.spec.ts:4:3 › Smoke Tests › homepage loads successfully
# ✓  [chromium] › smoke.spec.ts:11:3 › Smoke Tests › dashboard page is accessible
# ✓  [chromium] › smoke.spec.ts:17:3 › Smoke Tests › admin page is accessible
#
# 3 passed (8.2s)
```

## Backend Testing (Python)

### Configuration
**File**: `backend/pyproject.toml`
**Framework**: `pytest`

### Running Tests
```bash
cd backend
poetry run pytest
```

### Test Structure
- `backend/tests/`
  - `test_ingestion_service.py`: Logic verification for Ingestion.
  - `test_source_service.py`: Logic verification for Source management.
  - `test_search_pipeline_service.py`: Search pipeline logic.
  - `conftest.py`: Fixtures (mock_supabase).

### Mocking Strategy
We use `unittest.mock.MagicMock` to mock `SupabaseDB` and external services.
This allows running tests without a real database connection.

Example:
```python
@pytest.fixture
def mock_supabase():
    mock = MagicMock()
    # Mock table().select().execute() chain
    mock.table.return_value.select.return_value.execute.return_value.data = []
    return mock
```

## E2E Testing with Playwright

### Configuration

**File**: `frontend/playwright.config.ts`

**Key Features**:
- Test directory: `frontend/tests/e2e/`
- Base URL: `http://localhost:3000` (configurable via `PLAYWRIGHT_BASE_URL`)
- Auto-starts dev server before tests
- Retries: 2 on CI, 0 locally
- Workers: 1 on CI, parallel locally
- Browser: Chromium only (for speed)
- Reports: HTML report in `frontend/playwright-report/`

**WebServer Configuration**:
```typescript
webServer: {
  command: 'pnpm dev',
  url: 'http://localhost:3000',
  reuseExistingServer: !process.env.CI,
  timeout: 120 * 1000,
}
```

### Test Suite

**File**: `frontend/tests/e2e/smoke.spec.ts`

**Current Tests** (3 total):
1. **Homepage loads successfully**
   - Navigates to `/`
   - Waits for network idle
   - Verifies page has title
   - Checks body is visible

2. **Dashboard page is accessible**
   - Navigates to `/dashboard/ca`
   - Waits for network idle
   - Checks body is visible

3. **Admin page is accessible**
   - Navigates to `/admin`
   - Waits for network idle
   - Checks body is visible

### Running Tests

```bash
# Run all tests (headless)
cd frontend && pnpm test

# Run with UI (interactive)
cd frontend && pnpm test:ui

# Run with browser visible
cd frontend && pnpm test:headed

# View last test report
cd frontend && pnpm test:report
```

### Writing New Tests

Add tests to `frontend/tests/e2e/`:

```typescript
import { test, expect } from '@playwright/test';

test.describe('Feature Name', () => {
  test('should do something', async ({ page }) => {
    await page.goto('/your-page');
    await page.waitForLoadState('networkidle');

    // Your assertions
    await expect(page.locator('.your-element')).toBeVisible();
  });
});
```

## GitHub Actions CI

### Workflow Configuration

**File**: `.github/workflows/ci.yml`

**Triggers**:
- Pull requests to `main` or `master`
- Pushes to `main` or `master`
- Manual workflow dispatch

**Concurrency**: Auto-cancels superseded runs per branch

### Jobs

#### 1. Frontend Lint & Build

**Duration**: ~42s
**Runs on**: `ubuntu-latest`

**Steps**:
1. Checkout code
2. Setup pnpm (auto-detects version from `packageManager` field)
3. Setup Node.js 20 with pnpm cache
4. Install dependencies (`pnpm install --frozen-lockfile`)
5. Build frontend (`cd frontend && pnpm build`)

**Success Criteria**: Build completes without errors

#### 2. Frontend E2E Tests

**Duration**: ~1m2s
**Runs on**: `ubuntu-latest`
**Depends on**: Frontend Lint & Build

**Steps**:
1. Checkout code
2. Setup pnpm and Node.js
3. Install dependencies
4. Install Playwright browsers (`playwright install --with-deps chromium`)
5. Run tests (`cd frontend && pnpm test` with `CI=true`)
6. Upload Playwright report (always, even on failure)

**Success Criteria**: All 3 smoke tests pass

**Artifacts**: Playwright report (retained 30 days)

#### 3. Beads Validation

**Runs on**: `ubuntu-latest`
**Condition**: Only on pull requests

**Steps**:
1. Checkout with full history (`fetch-depth: 0`)
2. Check for `Feature-Key:` trailer in commits

**Success Criteria**: At least one commit has `Feature-Key: bd-xyz` trailer

### Viewing CI Results

```bash
# View latest CI run
gh run list --limit 1

# View specific run details
gh run view <run-id>

# View failed job logs
gh run view <run-id> --log-failed

# Watch live run
gh run watch <run-id>
```

### CI Run Example

Latest successful run: [19803145451](https://github.com/fengning-starsend/affordabot/actions/runs/19803145451)

```
✓ Frontend Lint & Build in 42s
✓ Frontend E2E Tests in 1m2s
- Beads Validation (skipped - not a PR)

Total: 1m50s
Status: SUCCESS
```

## pnpm Configuration

### Package Manager Version

**Specified in**: `frontend/package.json`

```json
{
  "packageManager": "pnpm@9.1.0"
}
```

This ensures:
- GitHub Actions auto-detects correct pnpm version
- Railway RAILPACK uses correct version
- All developers use same version

### Monorepo vs Service Lockfiles

**Root lockfile**: `pnpm-lock.yaml` (134K)
- Used for local development
- Contains all workspace dependencies

**Frontend lockfile**: `frontend/pnpm-lock.yaml` (131K)
- Generated with `pnpm install --ignore-workspace`
- Used by Railway deployments
- No workspace dependencies (e.g., no `turbo`)

**Why both?**
- Root: Local development with workspace features
- Frontend: Railway needs service-specific lockfile matching package.json exactly

**Regenerate frontend lockfile**:
```bash
cd frontend
yes | pnpm install --ignore-workspace
```

## Railway Deployment

### Frontend Service

**Configuration**: `frontend/railway.toml`

```toml
[build]
builder = "RAILPACK"
# Auto-detects pnpm via packageManager field
watchPatterns = ["frontend/**/*", "pnpm-lock.yaml"]

[deploy]
startCommand = "pnpm start"
healthcheckPath = "/"
healthcheckTimeout = 100
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

### Checking Deployment Status

```bash
# List recent deployments
railway deployment list --limit 5

# View deployment logs
railway logs --deployment <deployment-id>

# View build logs
railway logs --build <build-id>
```

### Successful Deployment Example

```bash
$ railway deployment list --limit 1
6cc3e316-bd0b-413a-a6d8-0ce2d31e2006 | SUCCESS | frontend | ...
```

## Troubleshooting

### Local Testing Issues

| Issue | Solution |
|-------|----------|
| `make: command not found` | Install build-essential (Linux) or Xcode CLI tools (Mac) |
| `pnpm: command not found` | Run `npm install -g pnpm@9.1.0` |
| Playwright tests fail locally | Run `cd frontend && pnpm exec playwright install --with-deps chromium` |
| Port 3000 already in use | Kill process: `lsof -ti:3000 \| xargs kill -9` |

### CI Failures

| Issue | Solution |
|-------|----------|
| Build fails on lockfile | Run `pnpm install` locally and commit updated lockfile |
| E2E tests timeout | Check webServer configuration in playwright.config.ts |
| Playwright browser install fails | Verify `--with-deps chromium` in GitHub Actions |
| Feature-Key validation fails | Add `Feature-Key: bd-xyz` trailer to commits |

### Railway Deployment Issues

| Issue | Solution |
|-------|----------|
| `ERR_PNPM_OUTDATED_LOCKFILE` | Regenerate frontend lockfile with `--ignore-workspace` |
| Build timeout | Check watchPatterns in railway.toml |
| Health check fails | Verify healthcheckPath and timeout settings |

## Testing Strategy

### Test Pyramid

```
        /\
       /E2E\		← 3 smoke tests (Playwright)
      /    \
     /------\
    /  Unit  \       ← Future: Component tests
   /----------\
  / Integration \    ← Future: API integration tests
 /--------------\
```

**Current Focus**: E2E smoke tests to verify critical user paths

**Future**:
- Unit tests for components (React Testing Library)
- Integration tests for API routes
- Visual regression tests (Percy/Chromatic)

### Test Coverage Goals

**Current**: Critical path coverage (homepage, dashboard, admin)

**Short-term goals**:
- [ ] Add authentication flow tests
- [ ] Add form submission tests
- [ ] Add error state tests

**Long-term goals**:
- [ ] 80%+ component test coverage
- [ ] API contract testing
- [ ] Performance regression testing
- [ ] E2E tests for admin dashboard
- [ ] Mobile responsive tests
- [ ] Accessibility tests (a11y)

## Performance Metrics

### Build Times

| Environment | Build Time | Bundle Size |
|-------------|-----------|-------------|
| Local | ~15s | 365 kB total |
| CI (GitHub Actions) | ~42s | Same |
| Railway | ~2-3min | Same |

### Test Times

| Test Suite | Local | CI |
|-----------|-------|-----|
| E2E (3 tests) | ~8s | ~1m2s |
| Full CI | ~23s | ~1m50s |

**Why CI slower?**
- Cold start (no cache)
- Single worker (CI=true)
- Browser installation overhead

## File Structure

```
affordabot/
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions workflow
├── frontend/
│   ├── playwright.config.ts   # Playwright configuration
│   ├── tests/
│   │   └── e2e/
│   │       └── smoke.spec.ts  # Smoke tests
│   ├── .gitignore             # Ignores test-results/, playwright-report/
│   └── package.json           # packageManager: pnpm@9.1.0
├── Makefile                   # Local development commands
└── docs/
    └── CI_AND_TESTING.md      # This file
```

## Best Practices

### Before Committing

```bash
# 1. Run local CI
make ci

# 2. Check build output
# Look for: ✓ Route (app) ... kB

# 3. Review test results
# Look for: X passed (Xs)
```

### Before Creating PR

```bash
# 1. Ensure Feature-Key in commits
git log --format=%B -1 | grep "Feature-Key:"

# 2. Push and verify CI passes
git push origin <branch>
gh run watch
```

### When Adding Features

```bash
# 1. Add E2E test for critical path
# File: frontend/tests/e2e/<feature>.spec.ts

# 2. Verify test passes locally
cd frontend && pnpm test

# 3. Update documentation
# File: docs/CI_AND_TESTING.md (this file)
```

## Next Steps

### Immediate
- [x] Local CI with Makefile
- [x] Playwright E2E tests (3 smoke tests)
- [x] GitHub Actions CI workflow
- [x] Railway deployment integration
- [x] Backend Unit Tests (pytest)

### Short-term
- [ ] Add authentication flow tests
- [ ] Add component unit tests
- [ ] Add API integration tests
- [ ] Setup test coverage reporting

### Long-term
- [ ] Visual regression testing
- [ ] Performance regression testing
- [ ] E2E tests for admin dashboard
- [ ] Mobile responsive tests
- [ ] Accessibility tests (a11y)

## Resources

- **Playwright Docs**: https://playwright.dev/docs/intro
- **GitHub Actions Docs**: https://docs.github.com/en/actions
- **Railway Docs**: https://docs.railway.com/
- **pnpm Docs**: https://pnpm.io/

## Changelog

### 2025-12-07
- ✅ Added Backend Testing section
- ✅ Updated Next Steps (Backend Unit Tests done)

### 2025-11-30
- ✅ Created Makefile with 11 commands
- ✅ Added Playwright with 3 smoke tests
- ✅ Created GitHub Actions CI workflow (2 jobs)
- ✅ Fixed Railway deployment (pnpm lockfile)
- ✅ All CI passing (local + GitHub Actions + Railway)
- ✅ Created this documentation