#!/usr/bin/env bash
set -euo pipefail

echo "DX Doctor — quick preflight"

# Always run from repo root (avoids relative-path confusion for agents).
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"
# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RESET='\033[0m'

ERRORS=0
# 0) Agent bootstrap (idempotent, non-fatal)
if command -v python3 >/dev/null 2>&1 && [[ -f scripts/cli/agent_bootstrap.py ]]; then
  python3 scripts/cli/agent_bootstrap.py || true
fi

# 1) Railway CLI
if command -v railway >/dev/null 2>&1; then
  echo "[✓] railway cli: installed"
else
  echo "[!] railway cli: missing (install Railway CLI)"
fi

# 2) Railway env
if [[ -z "${RAILWAY_ENVIRONMENT:-}" ]]; then
  echo "[!] Railway env: missing (run 'railway shell' for protected steps)"
else
  echo "[✓] Railway env: ${RAILWAY_ENVIRONMENT}"
fi

# 3) Git hooks
if [[ -x .githooks/pre-push ]]; then
  echo "[✓] Git hooks installed (.githooks/pre-push)"
else
  echo "[!] Git hooks not installed — run: make setup-git-hooks"
fi

# 4) GH auth
if gh auth status >/dev/null 2>&1; then
  echo "[✓] gh auth: ok"
else
  echo "[!] gh auth: please run 'gh auth login'"
fi

# 5) Guardrails stamp
if [[ -f .command-proof/guardrails.json ]]; then
  echo "[✓] guardrails stamp present (.command-proof/guardrails.json)"
else
  echo "[!] missing guardrails stamp. Run '/sync-i --force true' in CC/OC"
fi

# 6) Agent Mail (optional)
if [[ -n "${AGENT_MAIL_URL:-}" && -n "${AGENT_MAIL_BEARER_TOKEN:-}" ]]; then
  echo "[✓] Agent Mail env: configured"
else
  echo "[i] Agent Mail env: not configured yet (coordinator will provide token + setup)"
fi

# 7) Agent Skills Check (Fail-Open but Loud)
# We expect the mount at ~/.agent/skills -> ~/agent-skills
# But we also run the check script if distinct
SKILLS_CHECK_SCRIPT=~/agent-skills/mcp-doctor/check.sh

echo "--- Agent Skills Check ---"
if [ -f "$SKILLS_CHECK_SCRIPT" ]; then
    # Validate mount invariant
    if [ -L ~/.agent/skills ]; then
        echo -e "${GREEN}✅ Skills mount invariant (~/.agent/skills) verified${RESET}"
    else
        echo -e "${RED}❌ Skills mount missing or not a symlink: ~/.agent/skills${RESET}"
        echo "   Fix: ln -sfn ~/agent-skills ~/.agent/skills"
        ERRORS=$((ERRORS+1))
    fi
    
    echo "Running skills check..."
    if [ -n "${CI:-}" ]; then
        # CI Mode: Strict failure on skills check
        # Pass failing return code back up
        if ! bash "$SKILLS_CHECK_SCRIPT"; then
            echo -e "${RED}❌ Skills check failed in CI${RESET}"
            ERRORS=$((ERRORS+1))
        fi
    else
         # Local Mode: Warn only
         bash "$SKILLS_CHECK_SCRIPT" || true
    fi
else
    echo -e "${YELLOW}⚠️  Skills check script not found at $SKILLS_CHECK_SCRIPT${RESET}"
    echo "   Is ~/agent-skills checked out?"
    # Fail open, don't block
fi

# 8) MCP config doctor (optional, from agent-skills)
if [[ "${DX_SKIP_MCP:-}" == "1" ]]; then
  echo "[i] mcp-doctor: skipped (DX_SKIP_MCP=1)"
  echo "Done. If anything above is missing, re-run without DX_SKIP_MCP."
  exit 0
fi

# 9) MCP Checks (Affordabot-specific: Only Agent Mail is required)
echo "--- MCP Check ---"

# Helper to find string in config files
have_in_files() {
  local needle="$1"
  local FILES=(
    "$REPO_ROOT/.claude/settings.json"
    "$HOME/.claude/settings.json"
    "$HOME/.claude.json"
    "$HOME/.codex/config.toml"
    "$HOME/.gemini/settings.json"
  )
  for f in "${FILES[@]}"; do
    [[ -f "$f" ]] || continue
    if grep -F -q "$needle" "$f" 2>/dev/null; then
      echo "$f"
      return 0
    fi
  done
  return 1
}

# Agent Mail (Required-ish, weak warning)
if f="$(have_in_files "agent-mail")" || f="$(have_in_files "mcp-agent-mail")"; then
  echo "[✓] agent-mail config found ($f)"
else
  echo "[!] agent-mail config missing (Required for v3 coordination)"
fi

# Extensions (Optional)
if f="$(have_in_files "universal-skills")"; then
  echo "[✓] universal-skills found"
else
  echo "[i] universal-skills missing (optional)"
fi

if f="$(have_in_files "serena")"; then
  echo "[✓] serena found"
else
  echo "[i] serena missing (optional)"
fi

if f="$(have_in_files "z.ai")"; then
  echo "[✓] z.ai found"
else
  echo "[i] z.ai missing (optional)"
fi

echo "Done. See AGENTS.md for next steps."
exit 0
