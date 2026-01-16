#!/usr/bin/env python3
"""Nightly Dispatcher for Affordabot - OpenCode + Worktrees.

This script acts as the "Brain" of the fleet for Affordabot.
Uses OpenCode with worktree isolation for parallel bug fixing.

Routing Logic:
1. Poll Beads for open P0/P1 bugs (REPAIR MODE).
2. Deduplicate by error signature.
3. Dispatch to OpenCode VMs with worktree isolation.

Environment Variables:
  REPO: Repository name (default: affordabot)
  DX_DISPATCH_PATH: Path to dx-dispatch.py script
"""

import json
import logging
import os
import subprocess
import sys
import re
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from datetime import datetime

try:
    import httpx
except ImportError:
    print("Installing httpx...")
    subprocess.run([sys.executable, "-m", "pip", "install", "httpx"], check=True)
    import httpx

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Configuration
MAX_CRITICAL_BUGS = 10
MAX_PARALLEL = 2
MAX_DISPATCHES_PER_RUN = 3
MAX_DISPATCHES_DEGRADED = 1  # When overloaded

# VM Configuration
DEFAULT_VM = "epyc6"
REPO = os.environ.get("REPO", "affordabot")
SLACK_CHANNEL = "C09MQGMFKDE"


def run_cmd(cmd: List[str], check: bool = True) -> str:
    """Run a shell command and return stdout."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout.strip()


def get_beads_issues(query_type: str = "bug", priorities: List[int] = None) -> List[Dict]:
    """Query Beads for issues."""
    if priorities is None:
        priorities = [0, 1]
    
    issues = []
    for priority in priorities:
        try:
            output = run_cmd(["bd", "list", "--type", query_type, "--priority", str(priority), "--status", "open", "--json"], check=False)
            if output:
                data = json.loads(output)
                issues.extend(data if isinstance(data, list) else [data])
        except Exception as e:
            logger.warning(f"Failed to query Beads for P{priority} {query_type}s: {e}")
    
    return issues


def normalize_error(text: str) -> str:
    """Normalize error text for deduplication."""
    if not text:
        return ""
    # Remove timestamps, line numbers, paths
    text = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', '', text)
    text = re.sub(r'line \d+', 'line X', text, flags=re.IGNORECASE)
    text = re.sub(r'/[^\s]+/', '/PATH/', text)
    text = re.sub(r'\s+', ' ', text).strip().lower()
    return text


def deduplicate_bugs(bugs: List[Dict]) -> List[Dict]:
    """Deduplicate bugs by normalized error signature."""
    seen = set()
    unique = []
    for bug in bugs:
        desc = bug.get("description", "") + bug.get("title", "")
        sig = hashlib.md5(normalize_error(desc).encode()).hexdigest()[:12]
        if sig not in seen:
            seen.add(sig)
            unique.append(bug)
    return unique


def build_fix_prompt(issue: Dict) -> str:
    """Build the prompt for OpenCode agent."""
    title = issue.get("title", "Unknown issue")
    desc = issue.get("description", "No description")
    issue_id = issue.get("id", "unknown")
    
    return f"""Fix the following Affordabot bug:

## Issue: {issue_id}
## Title: {title}

## Description:
{desc}

## Instructions:
1. Analyze the error and identify the root cause
2. Implement a fix that addresses the issue
3. Add or update tests if applicable
4. The fix should be minimal and focused
5. Commit with message: fix({issue_id}): <brief description>
"""


def dispatch_to_opencode(issue: Dict, dry_run: bool = False) -> bool:
    """Dispatch via dx-dispatch with worktree isolation."""
    issue_id = issue.get("id", "unknown")
    prompt = build_fix_prompt(issue)
    
    if dry_run:
        logger.info(f"[DRY RUN] Would dispatch {issue_id} to {DEFAULT_VM}")
        return True
    
    try:
        dx_dispatch = os.environ.get("DX_DISPATCH_PATH", "dx-dispatch")
        
        # Build dispatch command
        cmd = [
            sys.executable, dx_dispatch,
            "--backend", f"opencode:{DEFAULT_VM}",
            "--repo", REPO,
            "--beads-id", issue_id,
            "--prompt", prompt,
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            logger.info(f"✅ Dispatched {issue_id} successfully")
            return True
        else:
            logger.error(f"❌ Failed to dispatch {issue_id}: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Dispatch error for {issue_id}: {e}")
        return False


def dispatch_parallel(work_queue: List[Dict], max_dispatch: int, dry_run: bool) -> int:
    """Dispatch bugs in parallel (up to MAX_PARALLEL)."""
    dispatched = 0
    
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as executor:
        futures = {}
        for issue in work_queue[:max_dispatch]:
            issue_id = issue.get("id", "unknown")
            logger.info(f"🚀 Dispatching {issue_id} to {DEFAULT_VM} (timeout: 20min)...")
            future = executor.submit(dispatch_to_opencode, issue, dry_run)
            futures[future] = issue_id
        
        for future in as_completed(futures):
            issue_id = futures[future]
            try:
                if future.result():
                    dispatched += 1
            except Exception as e:
                logger.error(f"Dispatch failed for {issue_id}: {e}")
    
    return dispatched


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Nightly Dispatcher for Affordabot')
    parser.add_argument('--dry-run', action='store_true', help='Simulate only')
    args = parser.parse_args()
    
    logger.info("=" * 50)
    logger.info("🌙 Nightly Dispatcher - Affordabot")
    logger.info("=" * 50)
    
    # Health check for VM
    logger.info("Running pre-dispatch health check...")
    try:
        resp = httpx.get(f"http://localhost:4105/global/health", timeout=10)
        if resp.status_code == 200:
            logger.info(f"✅ {DEFAULT_VM} health check passed")
        else:
            logger.warning(f"⚠️ {DEFAULT_VM} health check returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"⚠️ Health check failed: {e}")
    
    # Get bugs
    bugs = get_beads_issues("bug", [0, 1])
    logger.info(f"Found {len(bugs)} critical (P0/P1) bugs (raw)")
    
    # Deduplicate
    unique_bugs = deduplicate_bugs(bugs)
    logger.info(f"After deduplication: {len(unique_bugs)} unique bugs")
    
    if not unique_bugs:
        logger.info("No bugs to process. Fleet is idle.")
        return 0
    
    # Determine dispatch count
    max_dispatch = MAX_DISPATCHES_PER_RUN
    if len(unique_bugs) > MAX_CRITICAL_BUGS:
        logger.warning(f"⚠️ Fleet overloaded ({len(unique_bugs)} bugs), reducing dispatches")
        max_dispatch = MAX_DISPATCHES_DEGRADED
    
    logger.info("Fleet Mode: REPAIR")
    logger.info(f"Dispatching {min(len(unique_bugs), max_dispatch)} issues in parallel (max {MAX_PARALLEL})")
    
    # Dispatch
    dispatched = dispatch_parallel(unique_bugs, max_dispatch, args.dry_run)
    
    logger.info(f"📊 Dispatched {dispatched}/{min(len(unique_bugs), max_dispatch)} issues")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
