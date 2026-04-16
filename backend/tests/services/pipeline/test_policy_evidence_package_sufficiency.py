from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.pipeline.policy_evidence_package_builder import PolicyEvidencePackageBuilder
from services.pipeline.policy_evidence_package_storage import (
    InMemoryArtifactProbe,
    InMemoryArtifactWriter,
    InMemoryPolicyEvidencePackageStore,
    PersistedPackageRecord,
    PolicyEvidencePackageStorageService,
)
from services.pipeline.policy_evidence_package_sufficiency import (
    PackageReadinessLevel,
    PolicyEvidencePackageSufficiencyService,
    SufficiencyBlockingGate,
)


ROOT = Path(__file__).resolve().parents[4]
INTEGRATION_REPORT = (
    ROOT / "docs" / "poc" / "source-integration" / "artifacts" / "scrape_structured_integration_report.json"
)


def _load_envelopes() -> list[dict[str, Any]]:
    payload = json.loads(INTEGRATION_REPORT.read_text(encoding="utf-8"))
    return [dict(item) for item in payload.get("envelopes", []) if isinstance(item, dict)]


def _pick_envelope(*, source_lane: str, provider: str) -> dict[str, Any]:
    for envelope in _load_envelopes():
        if envelope.get("source_lane") == source_lane and envelope.get("provider") == provider:
            return envelope
    raise AssertionError(f"missing fixture envelope lane={source_lane} provider={provider}")


def _build_package(*, package_id: str) -> dict[str, Any]:
    scraped = _pick_envelope(source_lane="scrape_search", provider="private_searxng")
    structured = _pick_envelope(source_lane="structured", provider="legistar")
    return PolicyEvidencePackageBuilder().build(
        package_id=package_id,
        jurisdiction="san_jose_ca",
        scraped_candidates=[scraped],
        structured_candidates=[structured],
        freshness_gate={"freshness_status": "fresh"},
        economic_hints={"impact_mode": "direct_fiscal", "mechanism_family": "direct_fiscal"},
        storage_refs={
            "postgres_package_row": "policy_evidence_packages:pending",
            "reader_artifact": f"minio://policy-evidence/reader/private_searxng/{package_id}.txt",
            "pgvector_chunk_ref": "chunk:meeting-minutes-1",
        },
    )


def _persisted_record(
    *,
    package_id: str,
    known_uris: set[str] | None,
    mutate_payload: dict[str, Any] | None = None,
) -> PersistedPackageRecord:
    payload = _build_package(package_id=package_id)
    if mutate_payload:
        payload.update(mutate_payload)

    store = InMemoryPolicyEvidencePackageStore()
    service = PolicyEvidencePackageStorageService(
        store=store,
        artifact_writer=InMemoryArtifactWriter(),
        artifact_probe=InMemoryArtifactProbe(known_uris=known_uris) if known_uris is not None else None,
    )
    result = service.persist(package_payload=payload, idempotency_key=f"idem-{package_id}")
    assert result.stored is True
    record = store.get_by_idempotency(idempotency_key=f"idem-{package_id}")
    assert record is not None
    return record


def test_persisted_readback_positive_package_passes() -> None:
    package_id = "pkg-suff-pass"
    artifact_uri = f"minio://policy-evidence/packages/{package_id}.json"
    reader_uri = f"minio://policy-evidence/reader/private_searxng/{package_id}.txt"
    record = _persisted_record(
        package_id=package_id,
        known_uris={artifact_uri, reader_uri},
    )

    result = PolicyEvidencePackageSufficiencyService().evaluate(record=record)

    assert result.passed is True
    assert result.blocking_gate is None
    assert result.readiness_level == PackageReadinessLevel.ECONOMIC_HANDOFF_READY


def test_unproven_readback_fails_closed() -> None:
    record = _persisted_record(
        package_id="pkg-suff-unproven",
        known_uris=None,
    )

    result = PolicyEvidencePackageSufficiencyService().evaluate(record=record)

    assert result.passed is False
    assert result.blocking_gate == SufficiencyBlockingGate.STORAGE_READBACK
    assert result.readiness_level == PackageReadinessLevel.FAIL_CLOSED
    assert "readback is not proven" in result.failure_reasons[0]


def test_stale_assumption_blocks_quantitative_handoff() -> None:
    package_id = "pkg-suff-stale-assumption"
    artifact_uri = f"minio://policy-evidence/packages/{package_id}.json"
    reader_uri = f"minio://policy-evidence/reader/private_searxng/{package_id}.txt"
    record = _persisted_record(
        package_id=package_id,
        known_uris={artifact_uri, reader_uri},
    )
    payload = dict(record.package_payload)
    if not payload.get("assumption_cards"):
        raise AssertionError("fixture package does not include assumption_cards")
    payload["assumption_usage"] = [
        {
            "assumption_id": payload["assumption_cards"][0]["id"],
            "used_for_quantitative_claim": True,
            "applicable": True,
            "stale": False,
        }
    ]
    payload["freshness_status"] = "stale_blocked"
    stale_record = PersistedPackageRecord(
        record_id=record.record_id,
        package_id=record.package_id,
        idempotency_key=record.idempotency_key,
        content_hash=record.content_hash,
        schema_version=record.schema_version,
        jurisdiction=record.jurisdiction,
        canonical_document_key=record.canonical_document_key,
        policy_identifier=record.policy_identifier,
        package_status=record.package_status,
        economic_handoff_ready=record.economic_handoff_ready,
        fail_closed=record.fail_closed,
        gate_state=record.gate_state,
        insufficiency_reasons=record.insufficiency_reasons,
        storage_refs=record.storage_refs,
        package_payload=payload,
        artifact_write_status=record.artifact_write_status,
        artifact_readback_status=record.artifact_readback_status,
        pgvector_truth_role=record.pgvector_truth_role,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )

    result = PolicyEvidencePackageSufficiencyService().evaluate(record=stale_record)

    assert result.passed is False
    assert result.blocking_gate == SufficiencyBlockingGate.ASSUMPTION_STALENESS
    assert result.readiness_level == PackageReadinessLevel.FAIL_CLOSED


def test_missing_parameter_support_fails_closed() -> None:
    package_id = "pkg-suff-missing-params"
    artifact_uri = f"minio://policy-evidence/packages/{package_id}.json"
    reader_uri = f"minio://policy-evidence/reader/private_searxng/{package_id}.txt"
    record = _persisted_record(
        package_id=package_id,
        known_uris={artifact_uri, reader_uri},
    )
    payload = dict(record.package_payload)
    payload["parameter_cards"] = []
    payload["model_cards"] = []
    payload["economic_handoff_ready"] = False
    payload["gate_projection"] = {
        **payload["gate_projection"],
        "runtime_sufficiency_state": "quantified",
    }
    modified_record = PersistedPackageRecord(
        record_id=record.record_id,
        package_id=record.package_id,
        idempotency_key=record.idempotency_key,
        content_hash=record.content_hash,
        schema_version=record.schema_version,
        jurisdiction=record.jurisdiction,
        canonical_document_key=record.canonical_document_key,
        policy_identifier=record.policy_identifier,
        package_status=record.package_status,
        economic_handoff_ready=False,
        fail_closed=record.fail_closed,
        gate_state=record.gate_state,
        insufficiency_reasons=record.insufficiency_reasons,
        storage_refs=record.storage_refs,
        package_payload=payload,
        artifact_write_status=record.artifact_write_status,
        artifact_readback_status=record.artifact_readback_status,
        pgvector_truth_role=record.pgvector_truth_role,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )

    result = PolicyEvidencePackageSufficiencyService().evaluate(record=modified_record)

    assert result.passed is False
    assert result.blocking_gate == SufficiencyBlockingGate.PARAMETER_READINESS
    assert result.readiness_level == PackageReadinessLevel.FAIL_CLOSED


def test_qualitative_only_package_allowed_for_qualitative_handoff() -> None:
    package_id = "pkg-suff-qual-only"
    artifact_uri = f"minio://policy-evidence/packages/{package_id}.json"
    reader_uri = f"minio://policy-evidence/reader/private_searxng/{package_id}.txt"
    record = _persisted_record(
        package_id=package_id,
        known_uris={artifact_uri, reader_uri},
    )
    payload = dict(record.package_payload)
    payload["parameter_cards"] = []
    payload["model_cards"] = []
    payload["economic_handoff_ready"] = False
    payload["gate_projection"] = {
        **payload["gate_projection"],
        "runtime_sufficiency_state": "qualitative_only",
    }
    payload["gate_report"] = {
        **payload["gate_report"],
        "verdict": "qualitative_only",
        "blocking_gate": "parameterization",
    }
    payload["gate_report"]["stage_results"] = [
        {
            "stage": "parameterization",
            "passed": False,
            "failure_codes": ["parameter_missing"],
            "note": "qualitative fallback",
        }
    ]
    qualitative_record = PersistedPackageRecord(
        record_id=record.record_id,
        package_id=record.package_id,
        idempotency_key=record.idempotency_key,
        content_hash=record.content_hash,
        schema_version=record.schema_version,
        jurisdiction=record.jurisdiction,
        canonical_document_key=record.canonical_document_key,
        policy_identifier=record.policy_identifier,
        package_status=record.package_status,
        economic_handoff_ready=False,
        fail_closed=record.fail_closed,
        gate_state="qualitative_only",
        insufficiency_reasons=record.insufficiency_reasons,
        storage_refs=record.storage_refs,
        package_payload=payload,
        artifact_write_status=record.artifact_write_status,
        artifact_readback_status=record.artifact_readback_status,
        pgvector_truth_role=record.pgvector_truth_role,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )

    result = PolicyEvidencePackageSufficiencyService().evaluate(record=qualitative_record)

    assert result.passed is True
    assert result.blocking_gate == SufficiencyBlockingGate.PARAMETER_READINESS
    assert result.readiness_level == PackageReadinessLevel.QUALITATIVE_ONLY


def test_unsupported_claim_with_fail_closed_verdict_is_treated_as_compatible() -> None:
    package_id = "pkg-suff-unsupported-fail-closed"
    artifact_uri = f"minio://policy-evidence/packages/{package_id}.json"
    reader_uri = f"minio://policy-evidence/reader/private_searxng/{package_id}.txt"
    record = _persisted_record(
        package_id=package_id,
        known_uris={artifact_uri, reader_uri},
    )
    payload = dict(record.package_payload)
    payload["economic_handoff_ready"] = False
    payload["gate_projection"] = {
        **payload["gate_projection"],
        "runtime_sufficiency_state": "insufficient_evidence",
        "runtime_failure_codes": ["parameter_unverifiable"],
    }
    payload["gate_report"] = {
        **payload["gate_report"],
        "verdict": "fail_closed",
        "blocking_gate": "parameterization",
        "unsupported_claim_count": 1,
        "failure_codes": ["parameter_unverifiable"],
        "stage_results": [
            {
                "stage": "parameterization",
                "passed": False,
                "failure_codes": ["parameter_unverifiable"],
                "note": "unsupported quantitative claim",
            }
        ],
    }
    payload["parameter_cards"] = []
    payload["model_cards"] = []
    fail_closed_record = PersistedPackageRecord(
        record_id=record.record_id,
        package_id=record.package_id,
        idempotency_key=record.idempotency_key,
        content_hash=record.content_hash,
        schema_version=record.schema_version,
        jurisdiction=record.jurisdiction,
        canonical_document_key=record.canonical_document_key,
        policy_identifier=record.policy_identifier,
        package_status=record.package_status,
        economic_handoff_ready=False,
        fail_closed=record.fail_closed,
        gate_state="insufficient_evidence",
        insufficiency_reasons=record.insufficiency_reasons,
        storage_refs=record.storage_refs,
        package_payload=payload,
        artifact_write_status=record.artifact_write_status,
        artifact_readback_status=record.artifact_readback_status,
        pgvector_truth_role=record.pgvector_truth_role,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )

    result = PolicyEvidencePackageSufficiencyService().evaluate(record=fail_closed_record)

    assert result.passed is False
    assert result.blocking_gate == SufficiencyBlockingGate.PARAMETER_READINESS
    assert result.readiness_level == PackageReadinessLevel.FAIL_CLOSED
    assert "No resolved parameters or quantification-eligible model support path." in result.failure_reasons


def test_quant_model_referential_integrity_violation_fails_schema_validation() -> None:
    package_id = "pkg-suff-ref-integrity"
    artifact_uri = f"minio://policy-evidence/packages/{package_id}.json"
    reader_uri = f"minio://policy-evidence/reader/private_searxng/{package_id}.txt"
    record = _persisted_record(
        package_id=package_id,
        known_uris={artifact_uri, reader_uri},
    )
    payload = dict(record.package_payload)
    payload["parameter_cards"] = []
    payload["model_cards"] = [
        {
            "id": "model-ref-integrity",
            "mechanism_family": "direct_fiscal",
            "formula_id": "broken.v1",
            "input_parameter_ids": ["param-missing"],
            "assumption_ids": [],
            "scenario_bounds": {
                "conservative": 1.0,
                "central": 2.0,
                "aggressive": 3.0,
            },
            "arithmetic_valid": True,
            "unit_validation_status": "valid",
            "quantification_eligible": True,
            "failure_codes": [],
        }
    ]
    broken_record = PersistedPackageRecord(
        record_id=record.record_id,
        package_id=record.package_id,
        idempotency_key=record.idempotency_key,
        content_hash=record.content_hash,
        schema_version=record.schema_version,
        jurisdiction=record.jurisdiction,
        canonical_document_key=record.canonical_document_key,
        policy_identifier=record.policy_identifier,
        package_status=record.package_status,
        economic_handoff_ready=False,
        fail_closed=record.fail_closed,
        gate_state=record.gate_state,
        insufficiency_reasons=record.insufficiency_reasons,
        storage_refs=record.storage_refs,
        package_payload=payload,
        artifact_write_status=record.artifact_write_status,
        artifact_readback_status=record.artifact_readback_status,
        pgvector_truth_role=record.pgvector_truth_role,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )

    result = PolicyEvidencePackageSufficiencyService().evaluate(record=broken_record)

    assert result.passed is False
    assert result.blocking_gate == SufficiencyBlockingGate.SCHEMA_VALIDATION
    assert result.readiness_level == PackageReadinessLevel.FAIL_CLOSED
