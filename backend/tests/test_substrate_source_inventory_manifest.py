import json
from pathlib import Path


def _load_manifest() -> list[dict]:
    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = repo_root / "scripts" / "lib" / "substrate_source_inventory.json"
    return json.loads(manifest_path.read_text())


def test_manifest_targets_existing_family_deepening_jurisdictions() -> None:
    manifest = _load_manifest()
    slugs = {entry["jurisdiction_slug"] for entry in manifest}
    assert slugs == {
        "san-jose",
        "sunnyvale",
        "cupertino",
        "mountain-view",
        "san-mateo-county",
    }


def test_manifest_entries_are_truthful_legistar_calendar_roots() -> None:
    manifest = _load_manifest()
    for entry in manifest:
        metadata = entry["metadata"]
        assert entry["type"] == "meeting_calendar"
        assert metadata["provider_family"] == "legistar_calendar"
        assert metadata["document_type"] == "meeting_calendar"
        assert metadata["trust_tier"] == "official"
        assert metadata["inventory_scope"] == "existing_family_deepening"
        assert set(metadata["supported_asset_classes"]) == {"agendas", "minutes"}
        assert "municipal_code" not in metadata["supported_asset_classes"]
