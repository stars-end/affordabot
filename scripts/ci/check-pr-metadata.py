#!/usr/bin/env python3
"""Validate Feature-Key and Agent metadata for PRs."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

FEATURE_KEY_RE = re.compile(r"\bbd-[a-z0-9.]+\b")
BOT_AUTHORS = {"dependabot[bot]", "renovate[bot]", "github-actions[bot]"}


def _load_from_event(event_path: Path) -> tuple[str, str, str]:
    event = json.loads(event_path.read_text(encoding="utf-8"))
    pr = event.get("pull_request") or {}
    title = pr.get("title") or ""
    body = pr.get("body") or ""
    author = (pr.get("user") or {}).get("login") or ""
    return title, body, author


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", help="PR title for local checks")
    parser.add_argument("--body", help="PR body for local checks")
    parser.add_argument("--author", default="", help="PR author login (optional)")
    parser.add_argument("--event-path", help="Path to GitHub event JSON")
    args = parser.parse_args()

    event_path = args.event_path or os.environ.get("GITHUB_EVENT_PATH")
    if event_path:
        title, body, author = _load_from_event(Path(event_path))
    else:
        title = args.title or ""
        body = args.body or ""
        author = args.author or ""

    if not title:
        print("ERROR: missing PR title input")
        print("Local usage:")
        print('  python3 scripts/ci/check-pr-metadata.py --title "bd-xxxx: summary" --body "Agent: codex"')
        return 1

    if not FEATURE_KEY_RE.search(title):
        print("ERROR: PR title missing Feature-Key (bd-<beads-id>)")
        print("Example title:")
        print("  bd-1ebyt.6: harden affordabot CI preflights")
        return 1

    if author in BOT_AUTHORS:
        print(f"OK: bot PR detected ({author}); Agent metadata check skipped")
        return 0

    if "Agent:" not in body:
        print("ERROR: PR body missing 'Agent:'")
        print("Add line:")
        print("  Agent: codex")
        return 1

    print("OK: PR metadata enforcement passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
