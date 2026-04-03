"""Create a test source for Web Reader verification."""

import asyncio
import os
import sys

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.append(str(BACKEND_ROOT))

from db.postgres_client import PostgresDB


TEST_SOURCE_URL = "https://www.sanjoseca.gov/your-government/departments-offices/planning-building-code-enforcement"


async def _get_or_create_jurisdiction(db: PostgresDB) -> str:
    row = await db._fetchrow(
        "SELECT id FROM jurisdictions WHERE name = $1 LIMIT 1",
        "San Jose",
    )
    if row:
        return str(row["id"])

    created = await db._fetchrow(
        """
        INSERT INTO jurisdictions (name, type, scrape_url)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        "San Jose",
        "city",
        TEST_SOURCE_URL,
    )
    return str(created["id"])


async def create_test_source() -> str:
    db = PostgresDB()
    await db.connect()
    try:
        existing = await db._fetchrow(
            "SELECT id FROM sources WHERE url = $1 LIMIT 1",
            TEST_SOURCE_URL,
        )
        if existing:
            source_id = str(existing["id"])
            print(f"Test source already exists: {source_id}")
            return source_id

        jurisdiction_id = await _get_or_create_jurisdiction(db)
        source = await db.create_source(
            {
                "jurisdiction_id": jurisdiction_id,
                "url": TEST_SOURCE_URL,
                "type": "permits",
                "source_method": "manual",
                "status": "active",
                "handler": "web_reader",
                "name": "San Jose Planning Building Code Enforcement",
                "scrape_url": TEST_SOURCE_URL,
            }
        )
        source_id = str(source["id"])
        print(f"Created test source: {source_id}")
        return source_id
    finally:
        await db.close()


if __name__ == "__main__":
    print(f"\nTest Source ID: {asyncio.run(create_test_source())}")
