from __future__ import annotations

from pathlib import Path

from scripts.verification.verify_local_government_data_product_surface import (
    verify_surface,
)


def test_local_government_data_product_surface_artifacts_pass() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    artifact_dir = repo_root / "docs" / "poc" / "policy-evidence-quality-spine" / "artifacts"

    result = verify_surface(artifact_dir)

    assert result["status"] == "pass", result["failures"]
    assert result["jurisdiction_count"] >= 6
    assert result["non_ca_jurisdiction_count"] >= 2
    assert result["known_policy_count"] >= 10
    assert result["blind_holdout_count"] >= 5
