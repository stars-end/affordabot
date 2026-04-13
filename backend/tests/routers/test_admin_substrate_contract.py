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


def test_pipeline_read_model_routes_exist_on_admin_router() -> None:
    source = _admin_source()
    assert '@router.get("/pipeline/jurisdictions/{jurisdiction_id}/status")' in source
    assert '@router.get("/pipeline/runs/{run_id}")' in source
    assert '@router.get("/pipeline/runs/{run_id}/steps")' in source
    assert '@router.get("/pipeline/runs/{run_id}/evidence")' in source
    assert '@router.post("/pipeline/jurisdictions/{jurisdiction_id}/refresh")' in source


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
    assert '"canonical_document_key": row.get("canonical_document_key")' in source
    assert '"previous_raw_scrape_id": str(row["previous_raw_scrape_id"]) if row.get("previous_raw_scrape_id") else None' in source
    assert '"revision_number": int(row["revision_number"]) if row.get("revision_number") is not None else None' in source
    assert '"last_seen_at": str(row["last_seen_at"]) if row.get("last_seen_at") else None' in source
    assert '"seen_count": int(row["seen_count"]) if row.get("seen_count") is not None else None' in source
