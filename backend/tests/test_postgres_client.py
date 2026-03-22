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
