#!/usr/bin/env python3
"""Verifier for policy evidence package builder spike (bd-3wefe.4)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.pipeline.policy_evidence_package_builder import PolicyEvidencePackageBuilder
from schemas.policy_evidence_package import PolicyEvidencePackage


DEFAULT_OUTPUT = (
    REPO_ROOT
    / "docs"
    / "poc"
    / "policy-evidence-package-builder"
    / "artifacts"
    / "policy_evidence_package_builder_output.json"
)

INTEGRATION_FIXTURE = (
    REPO_ROOT / "docs" / "poc" / "source-integration" / "artifacts" / "scrape_structured_integration_report.json"
)

VERIFICATION_TIMESTAMP = "2026-04-15T00:00:00+00:00"


def _load_fixture() -> list[dict[str, Any]]:
    payload = json.loads(INTEGRATION_FIXTURE.read_text(encoding="utf-8"))
    return [dict(item) for item in payload.get("envelopes", []) if isinstance(item, dict)]


def _pick_envelope(*, source_lane: str, provider: str) -> dict[str, Any]:
    for envelope in _load_fixture():
        if envelope.get("source_lane") == source_lane and envelope.get("provider") == provider:
            return envelope
    raise RuntimeError(f"fixture missing lane={source_lane} provider={provider}")


def _build_sample() -> dict[str, Any]:
    scraped = _pick_envelope(source_lane="scrape_search", provider="private_searxng")
    structured = _pick_envelope(source_lane="structured", provider="legistar")
    insufficient = {
        "source_lane": "scrape_search",
        "provider": "private_searxng",
        "jurisdiction": "san_jose_ca",
        "source_family": "meeting_minutes",
        "artifact_url": "https://www.sanjoseca.gov/your-government/agendas-minutes",
        "artifact_type": "meeting_portal",
        "retrieved_at": VERIFICATION_TIMESTAMP,
        "selected_impact_mode": "qualitative_only",
        "prefetch_skip_reason": "/your-government/agendas-minutes",
        "reader_substance_reason": "reader_output_insufficient_substance",
    }
    builder = PolicyEvidencePackageBuilder()
    return builder.build(
        package_id="pkg-bd-3wefe-4-sample",
        jurisdiction="san_jose_ca",
        scraped_candidates=[scraped, insufficient],
        structured_candidates=[structured],
        freshness_gate={
            "freshness_status": "fresh",
            "snapshot_age_hours": 1.0,
            "decision_reason": "fresh",
            "retry_class": "none",
        },
        economic_hints={
            "impact_mode": "direct_fiscal",
            "mechanism_family": "direct_fiscal",
            "created_at": VERIFICATION_TIMESTAMP,
        },
        storage_refs={
            "raw_provider_response": "minio://policy-evidence/raw/provider/private_searxng.json",
            "reader_artifact": "minio://policy-evidence/reader/private_searxng/sj-13000001.txt",
        },
    )


def _report_payload(package: dict[str, Any]) -> dict[str, Any]:
    model = PolicyEvidencePackage.model_validate(package)
    normalized = model.model_dump(mode="json")
    evidence_cards = normalized.get("evidence_cards", [])
    has_scraped = "scraped" in normalized.get("source_lanes", [])
    reader_required = 0
    insufficient = 0
    for source in normalized.get("scraped_sources", []):
        if not source.get("reader_substance_passed", False):
            reader_required += 1
            insufficient += 1

    return {
        "feature_key": "bd-3wefe.4",
        "generated_at": VERIFICATION_TIMESTAMP,
        "report_version": "2026-04-15.policy-evidence-package-builder.v1",
        "schema_validation": {"schema_type": "pydantic", "error": None},
        "package": normalized,
        "readiness_summary": {
            "package_ready_evidence_count": len(evidence_cards) - insufficient,
            "reader_required_evidence_count": reader_required if has_scraped else 0,
            "insufficient_evidence_count": insufficient,
            "economic_handoff_ready": normalized.get("economic_handoff_ready", False),
            "fail_closed": not normalized.get("economic_handoff_ready", False),
            "insufficiency_reasons": normalized.get("insufficiency_reasons", []),
        },
        "open_proof_gaps": [
            "bd-3wefe.10 storage durability/readback not proven by this verifier",
            "bd-3wefe.12 windmill orchestration not exercised by this verifier",
            "bd-3wefe.5 final economic sufficiency gate not asserted by this verifier",
        ],
    }


def run(out_path: Path) -> dict[str, Any]:
    package = _build_sample()
    payload = _report_payload(package)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="Output JSON path")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    payload = run(args.out)
    summary = payload["readiness_summary"]
    print(
        "policy_evidence_package_builder verification complete: "
        f"ready={summary['package_ready_evidence_count']} "
        f"reader_required={summary['reader_required_evidence_count']} "
        f"insufficient={summary['insufficient_evidence_count']} "
        f"handoff_ready={summary['economic_handoff_ready']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
