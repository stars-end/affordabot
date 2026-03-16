"""
Windmill job: Run Discovery
Executes the discovery pipeline for legislation search.

Owner: Windmill (schedule)
Execution: CLI script (preserves exit-code observability)
Auth: Bearer token via CRON_SECRET env var
"""
import subprocess
import sys
import os

def main():
    result = subprocess.run(
        [sys.executable, "backend/scripts/cron/run_discovery.py"],
        cwd="/workspace",
        env={**os.environ},
    )
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
