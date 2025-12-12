#!/usr/bin/env bash
set -euo pipefail

echo "DX Doctor — quick preflight"

# Always run from repo root (avoids relative-path confusion for agents).
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

# 0) Agent bootstrap (idempotent, non-fatal)
if command -v python3 >/dev/null 2>&1 && [[ -f scripts/cli/agent_bootstrap.py ]]; then
  python3 scripts/cli/agent_bootstrap.py || true
fi

# 1) Railway env
if [[ -z "${RAILWAY_ENVIRONMENT:-}" ]]; then
  echo "[!] Railway env: missing (run 'railway shell' for protected steps)"
else
  echo "[✓] Railway env: ${RAILWAY_ENVIRONMENT}"
fi

# 2) Git hooks
if [[ -x .githooks/pre-push ]]; then
  echo "[✓] Git hooks installed (.githooks/pre-push)"
else
  echo "[!] Git hooks not installed — run: make setup-git-hooks"
fi

# 3) GH auth
if gh auth status >/dev/null 2>&1; then
  echo "[✓] gh auth: ok"
else
  echo "[!] gh auth: please run 'gh auth login'"
fi

# 4) Guardrails stamp
if [[ -f .command-proof/guardrails.json ]]; then
  echo "[✓] guardrails stamp present (.command-proof/guardrails.json)"
else
  echo "[!] missing guardrails stamp. Run '/sync-i --force true' in CC/OC"
fi

# 5) Agent Mail (optional)
if [[ -n "${AGENT_MAIL_URL:-}" && -n "${AGENT_MAIL_BEARER_TOKEN:-}" ]]; then
  echo "[✓] Agent Mail env: configured"
else
  echo "[i] Agent Mail env: not configured yet (coordinator will provide token + setup)"
fi

echo "Done. See AGENTS.md for next steps."
