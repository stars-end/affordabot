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
    assert report["recommendation"]["min_confidence"] == 0.75
    assert report["recommendation"]["passes_acceptance_gate"] is True
    assert report["sample_size"] > 0
    assert report["positive_examples"] > 0
    assert report["negative_examples"] > 0
    assert any(
        item["provenance_source"] == "scripts/lib/substrate_source_inventory.json"
        for item in report["candidate_provenance"]
    )


def test_live_runtime_preflight_requires_deps_and_api_key(monkeypatch):
    monkeypatch.setattr(script.importlib.util, "find_spec", lambda _name: None)
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    missing = script._live_runtime_preflight()

    assert any("instructor" in item for item in missing)
    assert any("openai" in item for item in missing)
    assert any("ZAI_API_KEY" in item for item in missing)
