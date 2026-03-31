"""Tests for retrieval-quality verification script (bd-bkco.4)."""

import json
import sys
from pathlib import Path

# Ensure backend root is importable when test is run directly.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.verification.verify_retrieval_quality import (
    check_conclusion_sensitivity,
    check_decisive_evidence,
    evaluate_retrieval_quality,
    expected_conclusion_label,
    infer_conclusion_label,
)


class TestConclusionInference:
    def test_worker_classification_label(self) -> None:
        label = infer_conclusion_label(
            [{"content": "AB 5 codifies the ABC test for worker classification."}]
        )
        assert label == "worker_classification"

    def test_parental_rights_label(self) -> None:
        label = infer_conclusion_label(
            [
                {
                    "content": "Parents Bill of Rights establishes rights for parents in education and schools."
                }
            ]
        )
        assert label == "parental_rights_education"

    def test_fail_closed_label(self) -> None:
        label = infer_conclusion_label(
            [{"content": "This is a non-binding resolution with no fiscal appropriation."}]
        )
        assert label == "fail_closed_non_fiscal"


class TestExpectedConclusionLabel:
    def test_control_type_mapping(self) -> None:
        label = expected_conclusion_label(
            bill_id="ca-acr-117-2024",
            title="Ceremonial California Assembly Concurrent Resolution",
            manifest_record={"control_type": "ceremonial_resolution"},
        )
        assert label == "fail_closed_non_fiscal"

    def test_anchor_mapping(self) -> None:
        label = expected_conclusion_label(
            bill_id="ca-ab-5-2019",
            title="Worker Status: Employees and Independent Contractors",
            manifest_record={"control_type": "cross_jurisdiction_id_collision_anchor"},
        )
        assert label == "worker_classification"


class TestQualityChecks:
    def test_decisive_evidence_passes_for_matching_chunk(self) -> None:
        result = check_decisive_evidence(
            bill_id="us-hr-5-2023",
            title="Parents Bill of Rights Act",
            top_chunks=[
                {
                    "chunk_id": "c1",
                    "content": "Parents Bill of Rights establishes parental rights in education.",
                }
            ],
            expected_label="parental_rights_education",
        )
        assert result["passed"] is True

    def test_conclusion_sensitivity_detects_change(self) -> None:
        result = check_conclusion_sensitivity(
            bill_id="ca-ab-5-2019",
            baseline_chunks=[
                {"content": "Worker classification and ABC test in labor code."}
            ],
            contrast_bill_id="us-hr-5-2023",
            contrast_chunks=[
                {"content": "Parents rights in school education are codified."}
            ],
        )
        assert result["passed"] is True


class TestEndToEndFixtureEvaluation:
    def test_fixture_set_passes_retrieval_quality_checks(self) -> None:
        report = evaluate_retrieval_quality(top_k=1)
        assert report["feature_key"] == "bd-bkco.4"
        assert report["summary"]["passed"] is True
        assert report["fixtures_evaluated"] >= 4
        # Ensure report remains machine-readable.
        json.dumps(report)
