"""
Windmill job: Daily Scrape
Runs all configured scrapers with concurrency control and DB logging.

Owner: Windmill (schedule)
Execution: CLI script (preserves exit-code observability)
Auth: Bearer token via CRON_SECRET env var
"""
import subprocess
import sys
import os

def main():
    result = subprocess.run(
        [sys.executable, "scripts/daily_scrape.py"],
        cwd="/workspace",
        env={**os.environ},
    )
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
