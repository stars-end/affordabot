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
    update_sql = db._fetchrow.await_args_list[1].args[0]
    assert update_sql.startswith("UPDATE sources SET")


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
