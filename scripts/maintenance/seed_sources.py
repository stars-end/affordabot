import os
from supabase import create_client, Client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    print("Error: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    exit(1)

supabase: Client = create_client(url, key)

sources = [
    {
        "jurisdiction_id": "san_jose_ca",
        "url": "https://sanjose.legistar.com/Calendar.aspx",
        "type": "meeting",
        "status": "active",
        "source_method": "scrape",
        "handler": "sanjose_meetings"
    },
    {
        "jurisdiction_id": "san_jose_ca",
        "url": "https://library.municode.com/ca/san_jose/codes/code_of_ordinances",
        "type": "code",
        "status": "active",
        "source_method": "scrape",
        "handler": "sanjose_municode"
    }
]

for source in sources:
    try:
        # Check if exists
        existing = supabase.table("sources").select("id").eq("url", source["url"]).execute()
        if existing.data:
            print(f"Skipping {source['url']} (already exists)")
        else:
            data = supabase.table("sources").insert(source).execute()
            print(f"Inserted {source['url']}")
    except Exception as e:
        print(f"Error inserting {source['url']}: {e}")
