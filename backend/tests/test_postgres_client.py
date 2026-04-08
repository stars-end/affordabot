from unittest.mock import AsyncMock
import sys
import types

import pytest

if "asyncpg" not in sys.modules:
    sys.modules["asyncpg"] = types.SimpleNamespace(Pool=object, Record=object)

from db.postgres_client import PostgresDB


@pytest.mark.asyncio
async def test_store_legislation_update_uses_coalesce_for_nullable_title() -> None:
    db = PostgresDB("postgresql://example.test/db")
    db._fetchrow = AsyncMock(return_value={"id": "leg-1"})
    db._execute = AsyncMock(return_value="UPDATE 1")

    legislation_id = await db.store_legislation(
        "jur-1",
        {
            "bill_number": "SB 277",
            "title": None,
            "text": "bill text",
            "status": "analyzed",
            "sufficiency_state": "insufficient_evidence",
            "quantification_eligible": False,
            "total_impact_p50": None,
        },
    )

    assert legislation_id == "leg-1"
    update_sql = db._execute.await_args.args[0]
    assert "COALESCE($1, title)" in update_sql
    assert db._execute.await_args.args[1] is None


@pytest.mark.asyncio
async def test_store_legislation_insert_falls_back_to_bill_number_for_title() -> None:
    db = PostgresDB("postgresql://example.test/db")

    async def fake_fetchrow(query: str, *args):
        if query.strip().startswith("SELECT id FROM legislation"):
            return None
        assert query.strip().startswith("INSERT INTO legislation")
        assert args[2] == "SB 277"
        return {"id": "leg-2"}

    db._fetchrow = AsyncMock(side_effect=fake_fetchrow)

    legislation_id = await db.store_legislation(
        "jur-1",
        {
            "bill_number": "SB 277",
            "title": None,
            "text": "bill text",
            "status": "analyzed",
            "sufficiency_state": "insufficient_evidence",
            "quantification_eligible": False,
            "total_impact_p50": None,
        },
    )

    assert legislation_id == "leg-2"


@pytest.mark.asyncio
async def test_create_raw_scrape_seeds_revision_identity_fields() -> None:
    db = PostgresDB("postgresql://example.test/db")
    db._fetchrow = AsyncMock(return_value={"id": "scrape-1"})

    scrape_id = await db.create_raw_scrape(
        {
            "source_id": "source-123",
            "content_hash": "abc123",
            "content_type": "text/html",
            "data": {"title": "Council Agenda"},
            "url": "https://city.example.gov/agendas?id=42&utm_source=email",
            "metadata": {"document_type": "agenda"},
            "storage_uri": None,
            "document_id": None,
        }
    )

    assert scrape_id == "scrape-1"
    insert_sql = db._fetchrow.await_args.args[0]
    assert "canonical_document_key" in insert_sql
    assert "previous_raw_scrape_id" in insert_sql
    assert "revision_number" in insert_sql
    assert "last_seen_at" in insert_sql
    assert "seen_count" in insert_sql

    args = db._fetchrow.await_args.args
    assert "utm_source" not in args[9]
    assert args[9].startswith(
        "v1|source=source-123|doctype=agenda|url=https://city.example.gov/agendas?id=42"
    )
    assert args[10] is None
    assert args[11] == 1
    assert args[13] == 1


@pytest.mark.asyncio
async def test_get_latest_raw_scrape_for_canonical_document_queries_revision_order() -> None:
    db = PostgresDB("postgresql://example.test/db")
    db._fetchrow = AsyncMock(
        return_value={
            "id": "scrape-latest",
            "canonical_document_key": "v1|source=s1|doctype=agenda|url=https://example.gov/a",
            "revision_number": 3,
            "content_hash": "hash-3",
        }
    )

    row = await db.get_latest_raw_scrape_for_canonical_document(
        "v1|source=s1|doctype=agenda|url=https://example.gov/a"
    )

    assert row is not None
    assert row["id"] == "scrape-latest"
    sql = db._fetchrow.await_args.args[0]
    assert "WHERE canonical_document_key = $1" in sql
    assert "ORDER BY revision_number DESC, created_at DESC" in sql


@pytest.mark.asyncio
async def test_mark_raw_scrape_seen_updates_seen_count_and_last_seen_at() -> None:
    db = PostgresDB("postgresql://example.test/db")
    db._execute = AsyncMock(return_value="UPDATE 1")

    ok = await db.mark_raw_scrape_seen("scrape-1")

    assert ok is True
    sql = db._execute.await_args.args[0]
    assert "last_seen_at = $1" in sql
    assert "seen_count = COALESCE(seen_count, 0) + 1" in sql
    assert db._execute.await_args.args[2] == "scrape-1"


@pytest.mark.asyncio
async def test_create_source_serializes_metadata_dict() -> None:
    db = PostgresDB("postgresql://example.test/db")
    db._fetchrow = AsyncMock(
        return_value={
            "id": "src-1",
            "jurisdiction_id": "jur-1",
            "url": "https://example.gov/agenda",
            "type": "web",
            "name": "Agenda",
            "metadata": '{"k":"v"}',
        }
    )

    await db.create_source(
        {
            "jurisdiction_id": "jur-1",
            "name": "Agenda",
            "type": "web",
            "url": "https://example.gov/agenda",
            "scrape_url": "https://example.gov/agenda",
            "metadata": {"k": "v"},
        }
    )

    args = db._fetchrow.await_args.args
    assert args[6] == '{"k": "v"}'


@pytest.mark.asyncio
async def test_get_discovery_query_cache_returns_list() -> None:
    db = PostgresDB("postgresql://example.test/db")
    db._fetchrow = AsyncMock(return_value={"queries": '["q1", "q2"]'})

    queries = await db.get_discovery_query_cache(
        jurisdiction_name="San Jose",
        jurisdiction_type="city",
        prompt_version="db-v1",
    )

    assert queries == ["q1", "q2"]


@pytest.mark.asyncio
async def test_upsert_discovery_query_cache_writes_json_payload() -> None:
    db = PostgresDB("postgresql://example.test/db")
    db._execute = AsyncMock(return_value="INSERT 0 1")

    ok = await db.upsert_discovery_query_cache(
        jurisdiction_name="San Jose",
        jurisdiction_type="city",
        prompt_version="db-v1",
        queries=["q1", "q2"],
        ttl_hours=24,
    )

    assert ok is True
    args = db._execute.await_args.args
    assert args[4] == '["q1", "q2"]'


@pytest.mark.asyncio
async def test_get_discovery_classifier_cache_returns_dict() -> None:
    db = PostgresDB("postgresql://example.test/db")
    db._fetchrow = AsyncMock(return_value={"decision": '{"is_scrapable": true}'})

    payload = await db.get_discovery_classifier_cache(
        normalized_url="https://example.gov/agenda",
        classifier_version="discovery-classifier-v1",
    )

    assert payload == {"is_scrapable": True}


@pytest.mark.asyncio
async def test_upsert_discovery_classifier_cache_writes_json_payload() -> None:
    db = PostgresDB("postgresql://example.test/db")
    db._execute = AsyncMock(return_value="INSERT 0 1")

    ok = await db.upsert_discovery_classifier_cache(
        normalized_url="https://example.gov/agenda",
        classifier_version="discovery-classifier-v1",
        decision={"is_scrapable": True, "confidence": 0.92},
    )

    assert ok is True
    args = db._execute.await_args.args
    assert args[2] == "discovery-classifier-v1"
    assert args[3] == '{"is_scrapable": true, "confidence": 0.92}'
