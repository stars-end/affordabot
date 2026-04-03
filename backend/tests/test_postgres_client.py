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
async def test_upsert_source_updates_existing_url_row() -> None:
    db = PostgresDB("postgresql://example.test/db")
    db._fetchrow = AsyncMock(
        side_effect=[
            {"id": "src-1"},
            {"id": "src-1", "url": "https://example.gov/agenda", "name": "Agenda source"},
        ]
    )

    source = await db.upsert_source(
        {
            "jurisdiction_id": "jur-1",
            "name": "Agenda source",
            "type": "meetings",
            "url": "https://example.gov/agenda",
            "source_method": "scrape",
            "handler": "legistar_calendar",
            "metadata": {"document_type": "agenda"},
        }
    )

    assert source["id"] == "src-1"
    lookup_sql = db._fetchrow.await_args_list[0].args[0]
    update_sql = db._fetchrow.await_args_list[1].args[0]
    assert "jurisdiction_id = $1 AND type = $2 AND name = $3" in lookup_sql
    assert update_sql.startswith("UPDATE sources SET")


@pytest.mark.asyncio
async def test_upsert_source_serializes_metadata_dict_for_insert() -> None:
    db = PostgresDB("postgresql://example.test/db")
    db._fetchrow = AsyncMock(
        side_effect=[
            None,
            None,
            {"id": "src-2", "name": "Agenda source"},
        ]
    )

    await db.upsert_source(
        {
            "jurisdiction_id": "jur-1",
            "name": "Agenda source",
            "type": "meetings",
            "url": "https://example.gov/agenda",
            "source_method": "scrape",
            "handler": "legistar_calendar",
            "metadata": {"document_type": "agenda"},
        }
    )

    insert_args = db._fetchrow.await_args_list[2].args
    assert insert_args[-1] == '{"document_type": "agenda"}'


@pytest.mark.asyncio
async def test_upsert_source_url_lookup_is_document_type_aware() -> None:
    db = PostgresDB("postgresql://example.test/db")
    db._fetchrow = AsyncMock(
        side_effect=[
            None,
            None,
            {"id": "src-3", "name": "Agenda source"},
        ]
    )

    await db.upsert_source(
        {
            "jurisdiction_id": "jur-1",
            "name": "Agenda source",
            "type": "meetings",
            "url": "https://example.gov/calendar",
            "source_method": "scrape",
            "handler": "legistar_calendar",
            "metadata": {"document_type": "agenda"},
        }
    )

    url_lookup_args = db._fetchrow.await_args_list[1].args
    assert "metadata->>'document_type'" in url_lookup_args[0]
    assert url_lookup_args[1:] == (
        "jur-1",
        "meetings",
        "https://example.gov/calendar",
        "agenda",
    )


@pytest.mark.asyncio
async def test_get_or_create_source_uses_upsert_source() -> None:
    db = PostgresDB("postgresql://example.test/db")
    db.upsert_source = AsyncMock(return_value={"id": "src-2"})

    source_id = await db.get_or_create_source(
        "jur-2",
        "County agendas",
        "meetings",
        url="https://sccgov.legistar.com/Calendar.aspx",
    )

    assert source_id == "src-2"
    db.upsert_source.assert_awaited_once()
