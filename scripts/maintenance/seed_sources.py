import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.append(str(BACKEND_ROOT))

from db.postgres_client import PostgresDB


def _load_manifest() -> list[dict[str, Any]]:
    manifest_path = REPO_ROOT / "scripts" / "lib" / "substrate_source_inventory.json"
    return json.loads(manifest_path.read_text())


def _resolve_jurisdiction_id_supabase(client: Any, jurisdiction_name: str) -> str | None:
    result = (
        client.table("jurisdictions")
        .select("id")
        .eq("name", jurisdiction_name)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]["id"]
    return None


def _payload_for_source(source: dict[str, Any], jurisdiction_id: str) -> dict[str, Any]:
    return {
        "jurisdiction_id": jurisdiction_id,
        "url": source["url"],
        "type": source["type"],
        "status": source["status"],
        "source_method": source["source_method"],
        "handler": source["handler"],
        "metadata": source["metadata"],
        "name": source["source_name"],
        "scrape_url": source["scrape_url"],
    }


async def _resolve_jurisdiction_id_postgres(db: PostgresDB, jurisdiction_name: str) -> str | None:
    row = await db._fetchrow(
        """
        SELECT id
        FROM jurisdictions
        WHERE name = $1
        LIMIT 1
        """,
        jurisdiction_name,
    )
    return str(row["id"]) if row else None


async def _sync_with_postgres(manifest: list[dict[str, Any]]) -> None:
    db = PostgresDB()
    await db.connect()
    try:
        for source in manifest:
            try:
                jurisdiction_id = await _resolve_jurisdiction_id_postgres(db, source["jurisdiction_name"])
                if not jurisdiction_id:
                    print(f"Skipping {source['jurisdiction_name']} ({source['url']}) - jurisdiction not found")
                    continue

                payload = _payload_for_source(source, jurisdiction_id)
                existing = await db._fetchrow(
                    "SELECT id FROM sources WHERE url = $1 LIMIT 1",
                    source["url"],
                )
                if existing:
                    await db.update_source(str(existing["id"]), payload)
                    print(f"Updated {source['url']}")
                else:
                    await db.create_source(payload)
                    print(f"Inserted {source['url']}")
            except Exception as exc:
                print(f"Error syncing {source['url']}: {exc}")
    finally:
        await db.close()


def _sync_with_supabase(manifest: list[dict[str, Any]], url: str, key: str) -> None:
    from supabase import create_client

    supabase = create_client(url, key)

    for source in manifest:
        try:
            jurisdiction_id = _resolve_jurisdiction_id_supabase(supabase, source["jurisdiction_name"])
            if not jurisdiction_id:
                print(f"Skipping {source['jurisdiction_name']} ({source['url']}) - jurisdiction not found")
                continue

            payload = _payload_for_source(source, jurisdiction_id)
            existing = supabase.table("sources").select("id").eq("url", source["url"]).limit(1).execute()
            if existing.data:
                source_id = existing.data[0]["id"]
                supabase.table("sources").update(payload).eq("id", source_id).execute()
                print(f"Updated {source['url']}")
            else:
                supabase.table("sources").insert(payload).execute()
                print(f"Inserted {source['url']}")
        except Exception as exc:
            print(f"Error syncing {source['url']}: {exc}")


def main() -> None:
    manifest = _load_manifest()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    database_url = os.environ.get("DATABASE_URL_PUBLIC") or os.environ.get("DATABASE_URL")

    if url and key:
        _sync_with_supabase(manifest, url, key)
        return
    if database_url:
        asyncio.run(_sync_with_postgres(manifest))
        return

    print("Error: Missing SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY and DATABASE_URL/DATABASE_URL_PUBLIC")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
