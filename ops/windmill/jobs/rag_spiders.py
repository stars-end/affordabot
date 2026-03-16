"""
Windmill job: RAG Spiders
Runs RAG spider pipeline for document retrieval augmentation.

Owner: Windmill (schedule)
Execution: CLI script (preserves exit-code observability)
Auth: Bearer token via CRON_SECRET env var
"""
import subprocess
import sys
import os

def main():
    result = subprocess.run(
        [sys.executable, "backend/scripts/cron/run_rag_spiders.py"],
        cwd="/workspace",
        env={**os.environ},
    )
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
