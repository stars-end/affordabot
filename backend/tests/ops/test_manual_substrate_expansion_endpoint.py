from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


def _manifest():
    return {
        "run_label": "broad-manual-2026-04-02",
        "jurisdictions": ["san-jose", "oakland"],
        "asset_classes": ["agendas", "minutes", "municipal_code"],
        "max_documents_per_source": 5,
        "run_mode": "capture_only",
        "ocr_mode": "hard_doc_only",
        "sample_size_per_bucket": 3,
        "notes": "manual validation run",
    }


def test_manual_substrate_expansion_requires_auth(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "test-secret")
    response = client.post("/cron/manual-substrate-expansion", json=_manifest())
    assert response.status_code == 401


def test_manual_substrate_expansion_returns_structured_contract(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "test-secret")
    monkeypatch.setattr(
        main,
        "run_manual_substrate_expansion",
        AsyncMock(
            return_value={
                "job": "manual_substrate_expansion",
                "status": "succeeded",
                "run_id": "manual-substrate-test-run",
                "run_label": "broad-manual-2026-04-02",
                "requested": _manifest(),
                "resolved_targets": {
                    "count": 6,
                    "by_jurisdiction": {"san-jose": 3, "oakland": 3},
                    "by_asset_class": {"agendas": 2, "minutes": 2, "municipal_code": 2},
                    "max_documents_per_source": 5,
                    "potential_target_documents": 30,
                },
                "capture_summary": {
                    "raw_scrapes_created": 0,
                    "by_content_class": {},
                    "by_trust_tier": {},
                },
                "ingestion_summary": {
                    "status": "skipped_by_run_mode",
                    "run_mode": "capture_only",
                    "ocr_mode": "hard_doc_only",
                    "ocr_fallback_invocations": 0,
                    "by_stage": {},
                },
                "promotion_summary": {
                    "status": "planned",
                    "captured_candidate": 0,
                    "durable_raw": 0,
                    "promoted_substrate": 0,
                },
                "failures": [],
                "inspection_report": {
                    "available": True,
                    "run_id": "manual-substrate-test-run",
                    "artifact_path": "/tmp/manual-substrate-test-run.json",
                },
                "triggered_at": "2026-04-02T00:00:00+00:00",
            }
        ),
    )

    response = client.post(
        "/cron/manual-substrate-expansion",
        headers={"Authorization": "Bearer test-secret"},
        json=_manifest(),
    )
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "succeeded"
    assert body["run_id"] == "manual-substrate-test-run"
    assert body["requested"]["run_label"] == "broad-manual-2026-04-02"
    assert body["resolved_targets"]["count"] == 6
    assert body["resolved_targets"]["by_jurisdiction"]["san-jose"] == 3
    assert body["resolved_targets"]["by_asset_class"]["agendas"] == 2
    assert body["ingestion_summary"]["status"] == "skipped_by_run_mode"
    assert body["promotion_summary"]["captured_candidate"] == 0
    assert body["failures"] == []
    assert body["inspection_report"]["available"] is True
    assert body["inspection_report"]["run_id"] == body["run_id"]
    assert body["inspection_report"]["artifact_path"] == "/tmp/manual-substrate-test-run.json"


def test_manual_substrate_expansion_capture_and_ingest_mode_sets_ingestion_planned(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "test-secret")
    manifest = _manifest()
    manifest["run_mode"] = "capture_and_ingest"
    monkeypatch.setattr(
        main,
        "run_manual_substrate_expansion",
        AsyncMock(
            return_value={
                "job": "manual_substrate_expansion",
                "status": "succeeded",
                "run_id": "manual-substrate-test-run",
                "run_label": manifest["run_label"],
                "requested": manifest,
                "resolved_targets": {
                    "count": 6,
                    "by_jurisdiction": {"san-jose": 3, "oakland": 3},
                    "by_asset_class": {"agendas": 2, "minutes": 2, "municipal_code": 2},
                    "max_documents_per_source": 5,
                    "potential_target_documents": 30,
                },
                "capture_summary": {
                    "raw_scrapes_created": 1,
                    "by_content_class": {"html_text": 1},
                    "by_trust_tier": {"official_partner": 1},
                },
                "ingestion_summary": {
                    "status": "planned",
                    "run_mode": "capture_and_ingest",
                    "ocr_mode": "hard_doc_only",
                    "ocr_fallback_invocations": 0,
                    "by_stage": {"retrievable": 1},
                },
                "promotion_summary": {
                    "captured_candidate": 0,
                    "durable_raw": 1,
                    "promoted_substrate": 0,
                },
                "failures": [],
                "inspection_report": {
                    "available": True,
                    "run_id": "manual-substrate-test-run",
                    "artifact_path": "/tmp/manual-substrate-test-run.json",
                },
                "triggered_at": "2026-04-02T00:00:00+00:00",
            }
        ),
    )

    response = client.post(
        "/cron/manual-substrate-expansion",
        headers={"X-PR-CRON-SECRET": "test-secret"},
        json=manifest,
    )
    assert response.status_code == 200
    assert response.json()["ingestion_summary"]["status"] == "planned"
