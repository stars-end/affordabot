import json
import os
from pathlib import Path

from supabase import Client
from supabase import create_client


def _load_manifest() -> list[dict]:
    manifest_path = Path(__file__).resolve().parent / "lib" / "substrate_source_inventory.json"
    return json.loads(manifest_path.read_text())


def _resolve_jurisdiction_id(client: Client, jurisdiction_name: str) -> str | None:
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


url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    print("Error: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    raise SystemExit(1)

supabase: Client = create_client(url, key)

for source in _load_manifest():
    try:
        jurisdiction_id = _resolve_jurisdiction_id(supabase, source["jurisdiction_name"])
        if not jurisdiction_id:
            print(f"Skipping {source['jurisdiction_name']} ({source['url']}) - jurisdiction not found")
            continue

        payload = {
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

        existing = supabase.table("sources").select("id").eq("url", source["url"]).limit(1).execute()
        if existing.data:
            source_id = existing.data[0]["id"]
            supabase.table("sources").update(payload).eq("id", source_id).execute()
            print(f"Updated {source['url']}")
        else:
            supabase.table("sources").insert(payload).execute()
            print(f"Inserted {source['url']}")
    except Exception as e:
        print(f"Error syncing {source['url']}: {e}")
