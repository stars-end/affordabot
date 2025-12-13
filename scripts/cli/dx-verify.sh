#!/bin/bash
# DX V3 Workflow Verification Script
# Runs smoke tests to verify DX setup is correct
# Usage: ./scripts/dx-verify.sh [--verbose]

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

VERBOSE=false
if [[ "${1:-}" == "--verbose" ]]; then
    VERBOSE=true
fi

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Logging
log_test() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}TEST:${NC} $*"
    fi
}

log_pass() {
    echo -e "${GREEN}✅${NC} $*"
    ((PASSED++))
}

log_fail() {
    echo -e "${RED}❌${NC} $*"
    ((FAILED++))
}

log_warn() {
    echo -e "${YELLOW}⚠️${NC}  $*"
    ((WARNINGS++))
}

# Banner
cat <<'EOF'
╔══════════════════════════════════════════════════╗
║     DX V3 Workflow Verification                  ║
╚══════════════════════════════════════════════════╝

EOF

# Test 1: Plugin configuration
log_test "Checking plugin configuration..."
if [ -f .claude/settings.json ]; then
    if grep -q 'dx-v3-workflow' .claude/settings.json 2>/dev/null; then
        log_pass "Plugin configured in .claude/settings.json"
    else
        log_warn "Plugin not found in .claude/settings.json (install with '/plugin install dx-v3-workflow@your-org')"
    fi
else
    log_fail ".claude/settings.json missing"
fi

# Test 2: Git hooks
log_test "Checking git hooks..."
HOOK_ERRORS=0
for hook in pre-commit post-merge pre-push; do
    if [ -f ".git/hooks/$hook" ]; then
        if [ -x ".git/hooks/$hook" ]; then
            log_pass "Git hook $hook is executable"
        else
            log_fail "Git hook $hook exists but is not executable (run: chmod +x .git/hooks/$hook)"
            ((HOOK_ERRORS++))
        fi
    else
        log_fail "Git hook $hook missing"
        ((HOOK_ERRORS++))
    fi
done

# Test 3: CI workflow
log_test "Checking CI workflow..."
if [ -f .github/workflows/ci.yml ]; then
    # Validate YAML syntax
    if command -v python3 >/dev/null 2>&1; then
        if python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" 2>/dev/null; then
            log_pass "CI workflow YAML is valid"
        else
            log_fail "CI workflow has invalid YAML syntax"
        fi
    else
        log_warn "Python3 not available, skipping YAML validation"
    fi

    # Check for env variables (fixed in commit 3/3 of PR #185)
    if grep -q 'env:' .github/workflows/ci.yml && grep -q 'BACKEND_FRAMEWORK:' .github/workflows/ci.yml; then
        log_pass "CI workflow has environment variables configured"
    else
        log_fail "CI workflow missing env: section (update from dx-v3-workflow template)"
    fi

    # Check if expressions use env correctly
    if grep -q 'if: env\\.BACKEND_FRAMEWORK' .github/workflows/ci.yml || \
       grep -q 'if: env\\.FRONTEND_FRAMEWORK' .github/workflows/ci.yml; then
        log_pass "CI workflow uses env variables in if expressions"
    else
        log_warn "CI workflow may have incorrect if expressions (should use 'env.BACKEND_FRAMEWORK')"
    fi
else
    log_fail "CI workflow missing (.github/workflows/ci.yml)"
fi

# Test 4: Specialist skills
log_test "Checking specialist skills..."
SKILLS_FOUND=0
if [ -f .claude/skills/backend-engineer/SKILL.md ]; then
    # Validate frontmatter
    if grep -q '^name: backend-engineer$' .claude/skills/backend-engineer/SKILL.md; then
        log_pass "Backend engineer skill configured correctly"
        ((SKILLS_FOUND++))
    else
        log_fail "Backend engineer skill has invalid frontmatter"
    fi
else
    log_warn "Backend engineer skill not found (expected for backend projects)"
fi

if [ -f .claude/skills/frontend-engineer/SKILL.md ]; then
    if grep -q '^name: frontend-engineer$' .claude/skills/frontend-engineer/SKILL.md; then
        log_pass "Frontend engineer skill configured correctly"
        ((SKILLS_FOUND++))
    else
        log_fail "Frontend engineer skill has invalid frontmatter"
    fi
else
    log_warn "Frontend engineer skill not found (expected for frontend projects)"
fi

if [ $SKILLS_FOUND -eq 0 ]; then
    log_fail "No specialist skills found"
fi

# Test 5: Beads scripts
log_test "Checking Beads scripts..."
SCRIPT_ERRORS=0
for script in bd-context bd-what bd-link-pr bd-retroactive; do
    if [ -f "scripts/$script" ]; then
        if [ -x "scripts/$script" ]; then
            log_pass "Script $script is executable"
        else
            log_fail "Script $script exists but is not executable (run: chmod +x scripts/$script)"
            ((SCRIPT_ERRORS++))
        fi
    else
        log_warn "Script $script not found (optional)"
    fi
done

# Test 6: Beads initialization
log_test "Checking Beads initialization..."
if [ -f .beads/config.yml ]; then
    log_pass "Beads initialized (.beads/config.yml exists)"
else
    log_warn "Beads not initialized (run: bd init <prefix>)"
fi

if [ -f .beads/issues.jsonl ]; then
    # Check if JSONL is valid
    if command -v jq >/dev/null 2>&1; then
        if cat .beads/issues.jsonl | while read -r line; do [ -z "$line" ] || echo "$line" | jq . >/dev/null; done 2>/dev/null; then
            log_pass "Beads issues.jsonl is valid JSON Lines"
        else
            log_fail "Beads issues.jsonl has invalid format"
        fi
    else
        log_warn "jq not available, skipping JSONL validation"
    fi
fi

# Test 7: Workflow skills (plugin)
log_test "Checking workflow skills..."
# These are in the plugin, so we can't directly check them
# But we can check if the plugin reference exists
if grep -q 'dx-v3-workflow' .claude/settings.json 2>/dev/null; then
    log_pass "Workflow skills available via plugin"
else
    log_warn "Plugin not configured (workflow skills may not be available)"
fi

# Test 8: Navigation commands
log_test "Checking navigation commands..."
COMMANDS_FOUND=0
for cmd in search find refs overview tree help-dx; do
    if [ -f ".claude/commands/${cmd}.md" ]; then
        log_pass "Command /$cmd available"
        ((COMMANDS_FOUND++))
    fi
done

if [ $COMMANDS_FOUND -eq 0 ]; then
    log_warn "No navigation commands found (should be in plugin or .claude/commands/)"
fi

# Summary
echo ""
echo "═══════════════════════════════════════════════════"
echo -e "${GREEN}PASSED:${NC}   $PASSED"
echo -e "${RED}FAILED:${NC}   $FAILED"
echo -e "${YELLOW}WARNINGS:${NC} $WARNINGS"
echo "═══════════════════════════════════════════════════"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ DX V3 setup verified successfully!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Open this repo in Claude Code"
    echo "  2. Trust the folder when prompted"
    echo "  3. Plugin should auto-install (or run: /plugin install dx-v3-workflow@your-org)"
    echo "  4. Try: /search \"your-keyword\""
    echo "  5. Say: \"commit my work\" to test workflow skills"
    echo ""
    exit 0
else
    echo -e "${RED}❌ DX V3 setup has $FAILED error(s)${NC}"
    echo ""
    echo "Common fixes:"
    echo "  • Git hooks not executable: chmod +x .git/hooks/*"
    echo "  • Missing files: Re-run ./dx-bootstrap.sh"
    echo "  • Plugin not installed: /plugin install dx-v3-workflow@your-org"
    echo "  • Beads not initialized: bd init <your-prefix>"
    echo ""
    echo "For help, see: dx-workflow-system/README.md"
    exit 1
fi
