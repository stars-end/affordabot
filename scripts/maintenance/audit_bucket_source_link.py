#!/usr/bin/env python3
"""
Read-only Railway Bucket source-link audit.

This script intentionally performs no write operations against Railway services.
It only:
1) links local CLI context non-interactively
2) reads `railway status --json`
3) reports whether the target service is still linked to a stale template repo
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _require_ok(result: subprocess.CompletedProcess[str], step: str) -> None:
    if result.returncode == 0:
        return
    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    detail = stderr or stdout or "no output"
    raise RuntimeError(f"{step} failed: {detail}")


def _parse_json_from_mixed_output(text: str, step: str) -> dict[str, Any]:
    """
    Railway CLI can emit prompt text before `--json` payloads.
    Parse the first valid top-level JSON object from mixed stdout text.
    """
    payload = (text or "").strip()
    if not payload:
        raise RuntimeError(f"{step} returned empty output")

    decoder = json.JSONDecoder()
    for idx, char in enumerate(payload):
        if char != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(payload[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj

    raise RuntimeError(f"{step} returned non-JSON output")


def _link_context(project: str, environment: str) -> dict[str, Any]:
    link = _run(
        [
            "railway",
            "link",
            "--project",
            project,
            "--environment",
            environment,
            "--json",
        ]
    )
    _require_ok(link, "railway link")
    return _parse_json_from_mixed_output(link.stdout or "", "railway link")


def _status_json() -> dict[str, Any]:
    status = _run(["railway", "status", "--json"])
    _require_ok(status, "railway status")
    return _parse_json_from_mixed_output(status.stdout or "", "railway status")


def _find_service_instance(
    status_payload: dict[str, Any],
    environment_name: str,
    service_name: str,
) -> dict[str, Any]:
    env_edges = (
        status_payload.get("environments", {})
        .get("edges", [])
    )
    for env_edge in env_edges:
        env_node = env_edge.get("node", {})
        if env_node.get("name") != environment_name:
            continue
        for svc_edge in env_node.get("serviceInstances", {}).get("edges", []):
            svc_node = svc_edge.get("node", {})
            if str(svc_node.get("serviceName", "")).lower() == service_name.lower():
                return svc_node
    raise RuntimeError(
        f"service '{service_name}' not found in environment '{environment_name}'"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Railway Bucket source-link drift")
    parser.add_argument("--project", required=True, help="Railway project ID or name")
    parser.add_argument("--environment", required=True, help="Railway environment name")
    parser.add_argument(
        "--service",
        default="Bucket",
        help="Service name to inspect (default: Bucket)",
    )
    parser.add_argument(
        "--expected-template-repo",
        default="railwayapp-templates/minio",
        help="Template repo to flag as stale source link",
    )
    args = parser.parse_args()

    try:
        link_info = _link_context(args.project, args.environment)
        status_payload = _status_json()
        service = _find_service_instance(
            status_payload,
            args.environment,
            args.service,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    repo = (service.get("source") or {}).get("repo")
    source_image = (service.get("source") or {}).get("image")
    deployment_repo = (
        (service.get("latestDeployment") or {})
        .get("meta", {})
        .get("repo")
    )

    stale_template_link = bool(
        repo and str(repo).lower() == args.expected_template_repo.lower()
    )

    report = {
        "project_id": link_info.get("projectId"),
        "project_name": link_info.get("projectName"),
        "environment_id": link_info.get("environmentId"),
        "environment_name": link_info.get("environmentName"),
        "service_name": service.get("serviceName"),
        "service_id": service.get("serviceId"),
        "source_repo": repo,
        "source_image": source_image,
        "latest_deployment_repo": deployment_repo,
        "expected_template_repo": args.expected_template_repo,
        "stale_template_link_detected": stale_template_link,
        "automatable_via_current_cli": False,
        "recommended_action": (
            "manual_ui_disconnect"
            if stale_template_link
            else "no_source_cleanup_needed"
        ),
    }
    print(json.dumps(report, indent=2))

    if stale_template_link:
        print(
            "STATUS: stale template source link detected; manual UI disconnect required.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
