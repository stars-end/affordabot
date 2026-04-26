#!/usr/bin/env python3
"""Probe/fail-close structured-source runtime proof for local-government corpus rows."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib import error, request


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MATRIX_PATH = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-evidence-quality-spine"
    / "artifacts"
    / "local_government_corpus_matrix.json"
)
DEFAULT_OUTPUT_PATH = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-evidence-quality-spine"
    / "artifacts"
    / "local_government_corpus_structured_source_proof.json"
)
DEFAULT_TARGET_ROW_IDS = ("lgm-065",)
FEATURE_KEY = "bd-3wefe.13.4.11"
SCHEMA_VERSION = "local_government_corpus_structured_source_proof_v1"
CONTRACT_VERSION = "2026-04-25.structured-source-proof.v1"


@dataclass(frozen=True)
class ProbeRecipe:
    endpoint_url: str
    access_method: str
    normalized_fields: tuple[str, ...]


PROBE_RECIPES: dict[tuple[str, str, str], ProbeRecipe] = {
    (
        "austin_tx",
        "socrata_api",
        "affordability_units",
    ): ProbeRecipe(
        endpoint_url="https://data.austintexas.gov/resource/2h5e-ntwt.json?$limit=5",
        access_method="http_get_json",
        normalized_fields=(
            "_10_to_19_units",
            "_20_units",
            "_2023_population",
        ),
    ),
}


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"expected object JSON at {path}"
        raise ValueError(msg)
    return payload


def _hash_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _hash_bytes(encoded)


def _row_by_id(matrix: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in matrix.get("rows", []):
        if not isinstance(row, dict):
            continue
        if row.get("row_type") != "corpus_package":
            continue
        row_id = str(row.get("corpus_row_id") or "")
        if row_id:
            rows[row_id] = row
    return rows


def _first_matching_observation(row: dict[str, Any]) -> dict[str, Any] | None:
    observations = row.get("structured_source_observations")
    if not isinstance(observations, list):
        return None
    for observation in observations:
        if not isinstance(observation, dict):
            continue
        if not bool(observation.get("true_structured")):
            continue
        if str(observation.get("proof_status") or "") != "cataloged_intent":
            continue
        return observation
    return None


def _blocked_attempt(
    *,
    row: dict[str, Any] | None,
    corpus_row_id: str,
    source_family: str,
    extraction_depth: str,
    blocker_class: str,
    blocker_detail: str,
    proof_source: str = "structured_source_runtime_probe",
) -> dict[str, Any]:
    jurisdiction_id = ""
    package_id = ""
    known_policy_reference_id = ""
    if isinstance(row, dict):
        jurisdiction_id = str((row.get("jurisdiction") or {}).get("id") or "")
        package_id = str(row.get("package_id") or "")
        known_policy_reference_id = str(row.get("known_policy_reference_id") or "")
    return {
        "corpus_row_id": corpus_row_id,
        "package_id": package_id,
        "known_policy_reference_id": known_policy_reference_id,
        "jurisdiction_id": jurisdiction_id,
        "source_family": source_family,
        "extraction_depth": extraction_depth,
        "proof_status": "blocked",
        "proof_source": proof_source,
        "blocker_class": blocker_class,
        "blocker_detail": blocker_detail,
        "retrieved_at": _iso_now(),
    }


def _probe_row(
    *,
    row: dict[str, Any],
    source_family: str,
    extraction_depth: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    jurisdiction_id = str((row.get("jurisdiction") or {}).get("id") or "")
    package_id = str(row.get("package_id") or "")
    known_policy_reference_id = str(row.get("known_policy_reference_id") or "")
    corpus_row_id = str(row.get("corpus_row_id") or "")

    recipe = PROBE_RECIPES.get((jurisdiction_id, source_family, extraction_depth))
    if recipe is None:
        return _blocked_attempt(
            row=row,
            corpus_row_id=corpus_row_id,
            source_family=source_family,
            extraction_depth=extraction_depth,
            blocker_class="probe_recipe_missing",
            blocker_detail=(
                "No runtime probe recipe for jurisdiction/source_family/depth tuple."
            ),
        )

    request_obj = request.Request(
        recipe.endpoint_url,
        headers={"User-Agent": "affordabot-cycle53-structured-proof/1.0"},
    )
    try:
        with request.urlopen(request_obj, timeout=timeout_seconds) as response:
            response_body = response.read()
            http_status = int(response.getcode() or 0)
    except error.HTTPError as exc:
        return _blocked_attempt(
            row=row,
            corpus_row_id=corpus_row_id,
            source_family=source_family,
            extraction_depth=extraction_depth,
            blocker_class="http_error",
            blocker_detail=f"HTTP {exc.code}: {exc.reason}",
        )
    except error.URLError as exc:
        return _blocked_attempt(
            row=row,
            corpus_row_id=corpus_row_id,
            source_family=source_family,
            extraction_depth=extraction_depth,
            blocker_class="network_error",
            blocker_detail=str(exc.reason),
        )

    retrieved_at = _iso_now()
    response_hash = _hash_bytes(response_body)
    try:
        payload = json.loads(response_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        return _blocked_attempt(
            row=row,
            corpus_row_id=corpus_row_id,
            source_family=source_family,
            extraction_depth=extraction_depth,
            blocker_class="invalid_json",
            blocker_detail=str(exc),
        )

    rows: list[dict[str, Any]] = []
    if isinstance(payload, list):
        rows = [item for item in payload if isinstance(item, dict)]
    elif isinstance(payload, dict):
        rows = [payload]
    sample_row_count = len(rows)
    if sample_row_count == 0:
        return _blocked_attempt(
            row=row,
            corpus_row_id=corpus_row_id,
            source_family=source_family,
            extraction_depth=extraction_depth,
            blocker_class="empty_payload",
            blocker_detail="Structured endpoint returned no object/list rows.",
        )

    first_row = rows[0]
    normalized_fields_proven = [
        field for field in recipe.normalized_fields if field in first_row
    ]
    schema_fields = sorted(first_row.keys())
    schema_hash = _hash_bytes(
        json.dumps(schema_fields, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )

    proof_status = "live_proven"
    blocker_class = ""
    blocker_detail = ""
    if http_status != 200:
        proof_status = "blocked"
        blocker_class = "non_200_status"
        blocker_detail = f"Expected HTTP 200, received {http_status}."
    elif not normalized_fields_proven:
        proof_status = "blocked"
        blocker_class = "normalized_fields_missing"
        blocker_detail = "No required normalized fields present in first row."

    result = {
        "corpus_row_id": corpus_row_id,
        "package_id": package_id,
        "known_policy_reference_id": known_policy_reference_id,
        "jurisdiction_id": jurisdiction_id,
        "source_family": source_family,
        "extraction_depth": extraction_depth,
        "proof_status": proof_status,
        "proof_source": "structured_source_runtime_probe",
        "endpoint_url": recipe.endpoint_url,
        "access_method": recipe.access_method,
        "retrieved_at": retrieved_at,
        "http_status": http_status,
        "response_hash": response_hash,
        "schema_hash": schema_hash,
        "sample_row_count": sample_row_count,
        "normalized_fields_proven": normalized_fields_proven,
    }
    if blocker_class:
        result["blocker_class"] = blocker_class
    if blocker_detail:
        result["blocker_detail"] = blocker_detail
    return result


def run(
    *,
    matrix_path: Path,
    target_row_ids: list[str],
    timeout_seconds: int,
    out_path: Path,
) -> dict[str, Any]:
    matrix = _load_json(matrix_path)
    rows_by_id = _row_by_id(matrix)

    attempts: list[dict[str, Any]] = []
    for row_id in target_row_ids:
        row = rows_by_id.get(row_id)
        if row is None:
            attempts.append(
                _blocked_attempt(
                    row=None,
                    corpus_row_id=row_id,
                    source_family="unknown",
                    extraction_depth="unknown",
                    blocker_class="row_not_found",
                    blocker_detail="Target row id not present in matrix.",
                )
            )
            continue

        observation = _first_matching_observation(row)
        if observation is None:
            attempts.append(
                _blocked_attempt(
                    row=row,
                    corpus_row_id=row_id,
                    source_family="unknown",
                    extraction_depth="unknown",
                    blocker_class="cataloged_target_missing",
                    blocker_detail=(
                        "No true_structured cataloged_intent observation found on row."
                    ),
                )
            )
            continue

        source_family = str(observation.get("source_family") or "")
        extraction_depth = str(observation.get("depth") or "")
        attempts.append(
            _probe_row(
                row=row,
                source_family=source_family,
                extraction_depth=extraction_depth,
                timeout_seconds=timeout_seconds,
            )
        )

    live_proven_rows = [
        str(item.get("corpus_row_id") or "")
        for item in attempts
        if str(item.get("proof_status") or "") == "live_proven"
    ]
    blocked_rows = [
        str(item.get("corpus_row_id") or "")
        for item in attempts
        if str(item.get("proof_status") or "") == "blocked"
    ]

    artifact = {
        "schema_version": SCHEMA_VERSION,
        "feature_key": FEATURE_KEY,
        "contract_version": CONTRACT_VERSION,
        "generated_at": _iso_now(),
        "benchmark_id": str(matrix.get("benchmark_id") or ""),
        "matrix_digest": _hash_payload(matrix),
        "attempts": attempts,
        "rows": attempts,
        "summary": {
            "attempted_row_count": len(attempts),
            "live_proven_count": len(live_proven_rows),
            "blocked_count": len(blocked_rows),
            "attempted_row_ids": target_row_ids,
            "live_proven_row_ids": live_proven_rows,
            "blocked_row_ids": blocked_rows,
        },
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return artifact


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-path", type=Path, default=DEFAULT_MATRIX_PATH)
    parser.add_argument("--target-row-id", action="append", default=[])
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    target_row_ids = (
        [str(row_id) for row_id in args.target_row_id if str(row_id).strip()]
        or list(DEFAULT_TARGET_ROW_IDS)
    )
    artifact = run(
        matrix_path=args.matrix_path,
        target_row_ids=target_row_ids,
        timeout_seconds=args.timeout_seconds,
        out_path=args.out,
    )
    summary = artifact.get("summary") or {}
    print(
        "local_government_corpus_structured_source_proof: "
        f"attempted={summary.get('attempted_row_count')} "
        f"live_proven={summary.get('live_proven_count')} "
        f"blocked={summary.get('blocked_count')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
