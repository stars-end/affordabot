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
        "alameda-county",
        "milpitas",
        "san-jose",
        "sunnyvale",
        "cupertino",
        "mountain-view",
        "san-mateo-county",
    }


def test_manifest_entries_are_truthful_legistar_calendar_roots() -> None:
    manifest = _load_manifest()
    legistar_entries = [
        entry
        for entry in manifest
        if entry["metadata"].get("provider_family") == "legistar_calendar"
    ]
    assert {entry["jurisdiction_slug"] for entry in legistar_entries} == {
        "san-jose",
        "sunnyvale",
        "cupertino",
        "mountain-view",
        "san-mateo-county",
    }
    for entry in legistar_entries:
        metadata = entry["metadata"]
        assert entry["type"] == "meeting_calendar"
        assert metadata["provider_family"] == "legistar_calendar"
        assert metadata["document_type"] == "meeting_calendar"
        assert metadata["trust_tier"] == "official"
        assert metadata["inventory_scope"] == "existing_family_deepening"
        assert set(metadata["supported_asset_classes"]) == {"agendas", "minutes"}
        assert "municipal_code" not in metadata["supported_asset_classes"]


def test_manifest_entries_include_custom_archive_document_center_family() -> None:
    manifest = _load_manifest()
    custom_entries = [
        entry
        for entry in manifest
        if entry["metadata"].get("provider_family") == "custom_archive_document_center"
    ]
    assert {entry["jurisdiction_slug"] for entry in custom_entries} == {
        "milpitas",
        "alameda-county",
    }
    for entry in custom_entries:
        metadata = entry["metadata"]
        assert entry["type"] == "meeting_archive_root"
        assert entry["handler"] == "substrate_custom_archive_document_center"
        assert metadata["document_type"] == "meeting_archive_root"
        assert metadata["inventory_scope"] == "new_family_bootstrap"
        assert metadata["supported_document_types"] == ["agenda", "minutes"]
        assert set(metadata["supported_asset_classes"]) == {"agendas", "minutes"}
