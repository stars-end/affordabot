"""
Path A Windmill script export for storage-boundary bakeoff.

This script intentionally models a Windmill step that shells into the deterministic
runner committed in backend/scripts/verification/windmill_bakeoff_direct_storage.py.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any


def main(
    run_date: str | None = None,
    scenario: str = "normal",
    state_dir: str = "docs/poc/windmill-storage-bakeoff/path-a-direct-storage/runtime_state",
    evidence_dir: str = "docs/poc/windmill-storage-bakeoff/path-a-direct-storage",
    emit_suite: bool = False,
) -> dict[str, Any]:
    mode = "suite" if emit_suite else "run"
    command = [
        "python3",
        "backend/scripts/verification/windmill_bakeoff_direct_storage.py",
        mode,
        "--state-dir",
        state_dir,
    ]
    if run_date:
        command.extend(["--run-date", run_date])
    if emit_suite:
        command.extend(["--evidence-dir", evidence_dir])
    else:
        command.extend(["--scenario", scenario])

    env = os.environ.copy()
    proc = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        env=env,
    )

    output: dict[str, Any]
    try:
        output = json.loads(proc.stdout)
    except json.JSONDecodeError:
        output = {"raw_stdout": proc.stdout}

    return {
        "status": "succeeded" if proc.returncode == 0 else "failed",
        "mode": mode,
        "command": command,
        "returncode": proc.returncode,
        "result": output,
        "stderr": proc.stderr,
    }
