import os
from supabase import create_client, Client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    print("Error: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    exit(1)

supabase: Client = create_client(url, key)

try:
    response = supabase.table("raw_scrapes").select("*").limit(5).execute()
    print(f"Found {len(response.data)} raw scrapes.")
    for row in response.data:
        print(f"ID: {row['id']}, Source: {row['source_id']}, Hash: {row['content_hash'][:8]}")
        # print(f"Data: {row['data']}") # Too verbose
except Exception as e:
    print(f"Error: {e}")
