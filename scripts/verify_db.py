import os
from supabase import create_client, Client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    print("Error: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    exit(1)

supabase: Client = create_client(url, key)

try:
    response = supabase.table("sources").select("*").limit(1).execute()
    print("Success: Table 'sources' exists.")
    print(response)
except Exception as e:
    print(f"Error: {e}")
