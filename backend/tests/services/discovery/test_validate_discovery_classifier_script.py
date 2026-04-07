import json
import sys

import pytest

from scripts.verification import validate_discovery_classifier as script


@pytest.mark.asyncio
async def test_validate_discovery_classifier_with_stubbed_responses(tmp_path, monkeypatch):
    artifact_path = tmp_path / "report.json"
    fixture_path = (
        "backend/scripts/verification/fixtures/discovery_classifier_eval_set.json"
    )
    responses_path = (
        "backend/scripts/verification/fixtures/discovery_classifier_stubbed_responses.json"
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_discovery_classifier.py",
            "--fixture",
            fixture_path,
            "--responses",
            responses_path,
            "--artifact",
            str(artifact_path),
        ],
    )

    exit_code = await script.main()
    assert exit_code == 0
    assert artifact_path.exists()

    report = json.loads(artifact_path.read_text())
    assert report["recommendation"]["min_confidence"] == 0.70
    assert report["recommendation"]["passes_acceptance_gate"] is True
    assert report["sample_size"] > 0
