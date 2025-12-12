#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CmdResult:
    returncode: int
    stdout: str
    stderr: str


def _run(cmd: list[str], cwd: Path | None = None, timeout_s: float = 30.0) -> CmdResult:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
        )
        return CmdResult(proc.returncode, proc.stdout.strip(), proc.stderr.strip())
    except Exception as e:  # noqa: BLE001 - bootstrap should never crash
        return CmdResult(1, "", f"{type(e).__name__}: {e}")


def _repo_root() -> Path:
    res = _run(["git", "rev-parse", "--show-toplevel"], timeout_s=5.0)
    if res.returncode == 0 and res.stdout:
        return Path(res.stdout)
    return Path.cwd()


def _is_git_dirty(root: Path) -> tuple[bool, int]:
    res = _run(["git", "status", "--porcelain=v1"], cwd=root, timeout_s=5.0)
    if res.returncode != 0:
        return False, 0
    lines = [ln for ln in res.stdout.splitlines() if ln.strip()]
    return (len(lines) > 0), len(lines)


def _http_ok(url: str, timeout_s: float = 0.75) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "dx-doctor/agent_bootstrap"})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 - controlled URL
            return 200 <= int(resp.status) < 300
    except Exception:
        return False


def _try_agent_mail_health() -> tuple[bool, str]:
    base = os.environ.get("AGENT_MAIL_URL", "").strip()
    candidates: list[str] = []
    if base:
        candidates.append(base.rstrip("/") + "/health/liveness")
    candidates.extend(
        [
            "http://127.0.0.1:8765/health/liveness",
            "http://localhost:8765/health/liveness",
        ]
    )
    for url in candidates:
        if _http_ok(url):
            return True, url
    return False, candidates[0] if candidates else "http://127.0.0.1:8765/health/liveness"


def _find_agent_skills_dir() -> Path | None:
    candidates: list[Path] = []
    env_path = os.environ.get("AGENT_SKILLS_DIR") or os.environ.get("DX_AGENT_SKILLS_DIR")
    if env_path:
        candidates.append(Path(env_path).expanduser())
    candidates.extend(
        [
            Path.home() / "agent-skills",
            Path.home() / ".agent" / "skills",
        ]
    )
    for path in candidates:
        if path.exists() and (path / ".git").exists():
            return path
    return None


def _agent_skills_update() -> tuple[bool, str]:
    skills_dir = _find_agent_skills_dir()
    if not skills_dir:
        return False, "not found (set AGENT_SKILLS_DIR)"

    inside = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=skills_dir, timeout_s=5.0)
    if inside.returncode != 0 or inside.stdout != "true":
        return False, f"not a git repo ({skills_dir})"

    dirty, dirty_count = _is_git_dirty(skills_dir)
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=skills_dir, timeout_s=5.0).stdout or "unknown"

    origin_head = _run(
        ["git", "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"],
        cwd=skills_dir,
        timeout_s=5.0,
    ).stdout
    default_branch = origin_head.split("/")[-1] if origin_head else "master"
    upstream = f"origin/{default_branch}"

    _run(["git", "fetch", "--quiet", "--prune", "origin"], cwd=skills_dir, timeout_s=15.0)

    behind = _run(["git", "rev-list", "--count", f"HEAD..{upstream}"], cwd=skills_dir, timeout_s=5.0)
    behind_n = int(behind.stdout) if behind.returncode == 0 and behind.stdout.isdigit() else 0

    if behind_n <= 0:
        return True, f"up-to-date ({branch})"

    if dirty:
        return False, f"behind {behind_n} commits but dirty ({dirty_count} changes) — pull manually"

    pulled = _run(["git", "pull", "--ff-only", "--quiet", "origin", default_branch], cwd=skills_dir, timeout_s=30.0)
    if pulled.returncode == 0:
        return True, f"updated (pulled {behind_n} commits → {branch})"
    return False, f"behind {behind_n} commits (pull failed; branch={branch})"


def _beads_import(root: Path) -> tuple[bool, str]:
    jsonl_path = root / ".beads" / "issues.jsonl"
    if not jsonl_path.exists():
        return False, "no .beads/issues.jsonl"

    bd = _run(["bd", "--help"], cwd=root, timeout_s=5.0)
    if bd.returncode != 0:
        return False, "bd not found"

    res = _run(
        [
            "bd",
            "import",
            "-i",
            str(jsonl_path),
            "--force",
            "--json",
            "--no-auto-flush",
        ],
        cwd=root,
        timeout_s=60.0,
    )
    if res.returncode != 0:
        return False, "bd import failed"

    combined = "\n".join([res.stdout, res.stderr]).strip()
    for line in combined.splitlines():
        m = re.search(r"Import complete:\s*(\d+)\s*created,\s*(\d+)\s*updated,\s*(\d+)\s*unchanged", line)
        if m:
            created, updated, unchanged = m.group(1), m.group(2), m.group(3)
            return True, f"created={created} updated={updated} unchanged={unchanged}"

    try:
        payload = json.loads(combined)
        parts = []
        for key in ("created", "updated", "unchanged"):
            if key in payload:
                parts.append(f"{key}={payload[key]}")
        return True, " ".join(parts) if parts else "ok"
    except Exception:
        return True, "ok"


def main() -> int:
    root = _repo_root()
    os.chdir(root)

    print("DX Bootstrap — quick sync")

    agent_name = os.environ.get("AGENT_NAME") or os.environ.get("DX_AGENT_NAME") or ""
    node = os.environ.get("AGENT_NODE") or socket.gethostname().split(".")[0]
    if agent_name:
        print(f"[i] agent: {agent_name}")
    else:
        print(f"[i] agent: (unset) node={node}")

    dirty, dirty_count = _is_git_dirty(root)
    if dirty:
        print(f"[!] git: dirty ({dirty_count} changes) — proceed, but expect surprises")
    else:
        print("[✓] git: clean")

    ok_mail, mail_url = _try_agent_mail_health()
    if ok_mail:
        print(f"[✓] agent-mail: alive ({mail_url})")
    else:
        print("[i] agent-mail: not reachable (ok if not using multi-agent mail yet)")

    ok_skills, skills_msg = _agent_skills_update()
    if ok_skills:
        print(f"[✓] agent-skills: {skills_msg}")
    else:
        print(f"[i] agent-skills: {skills_msg}")

    ok_beads, beads_msg = _beads_import(root)
    if ok_beads:
        print(f"[✓] beads: import ok ({beads_msg})")
    else:
        print(f"[i] beads: import skipped ({beads_msg})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

