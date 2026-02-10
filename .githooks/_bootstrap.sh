#!/usr/bin/env bash
set -euo pipefail

# Self-heal hook wiring:
# - Ensures `core.hooksPath` points at `.githooks`
# - Installs `.git/hooks/*` shims so hooks still run even if config is lost

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

git -C "$ROOT" config core.hooksPath .githooks >/dev/null 2>&1 || true

git_common_dir="$(git -C "$ROOT" rev-parse --git-common-dir 2>/dev/null || echo "$ROOT/.git")"
if [[ "$git_common_dir" != /* ]]; then
  git_common_dir="$ROOT/$git_common_dir"
fi
hooks_dir="$git_common_dir/hooks"
mkdir -p "$hooks_dir"

install_shim() {
  local name="$1"
  local shim="$hooks_dir/$name"

  if [[ -e "$shim" ]]; then
    if [[ -L "$shim" ]]; then
      : # ok to replace symlinks (common previous install pattern)
    elif grep -q "DX_GITHOOKS_SHIM" "$shim" 2>/dev/null; then
      : # ok to refresh our own shim
    else
      # Do not clobber unknown hooks (may be bespoke/local).
      return 0
    fi
  fi

  cat >"$shim" <<'SHIM'
#!/usr/bin/env bash
# DX_GITHOOKS_SHIM
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)"
HOOK="$(basename "$0")"
TARGET="$ROOT/.githooks/$HOOK"

if [[ -x "$TARGET" ]]; then
  exec "$TARGET" "$@"
fi

exit 0
SHIM

  chmod +x "$shim" 2>/dev/null || true
}

for h in pre-commit commit-msg pre-push post-merge post-checkout post-rewrite; do
  install_shim "$h"
done

exit 0
