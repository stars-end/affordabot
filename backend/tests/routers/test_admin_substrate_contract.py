from pathlib import Path


def _admin_source() -> str:
    admin_path = Path(__file__).resolve().parents[2] / "routers" / "admin.py"
    return admin_path.read_text()


def test_substrate_routes_exist_on_admin_router() -> None:
    source = _admin_source()
    assert '@router.get("/substrate/runs")' in source
    assert '@router.get("/substrate/runs/{run_id}")' in source
    assert '@router.get("/substrate/runs/{run_id}/failure-buckets")' in source
    assert '@router.get("/substrate/runs/{run_id}/raw-scrapes")' in source
    assert '@router.get("/substrate/raw-scrapes/{raw_scrape_id}")' in source


def test_substrate_run_query_uses_manual_run_stamp() -> None:
    source = _admin_source()
    assert "COALESCE(rs.metadata->>$1, '') AS run_id" in source
    assert "WHERE COALESCE(rs.metadata->>$1, '') <> ''" in source


def test_substrate_raw_row_payload_includes_debuggable_fields() -> None:
    source = _admin_source()
    assert '"promotion_state": metadata.get("promotion_state")' in source
    assert '"content_class": metadata.get("content_class")' in source
    assert '"trust_tier": metadata.get("trust_tier")' in source
    assert '"ingestion_truth_stage": truth.get("stage")' in source
    assert '"storage_uri": row.get("storage_uri")' in source
    assert '"document_id": str(row["document_id"]) if row.get("document_id") else None' in source
