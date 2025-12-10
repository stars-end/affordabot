import pytest
import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

from db.supabase_client import SupabaseDB

@pytest.mark.asyncio
async def test_write():
    print("Testing DB upsert with metadata column via PostgREST...")
    db = SupabaseDB()
    if not db.client:
        print("❌ Connect failed")
        sys.exit(1)
        
    try:
        # Exact payload from verification script
        dummy_url = f"https://example.com/test-{os.getpid()}"
        payload = {
            'jurisdiction_id': '33eb6b12-0019-482b-89f9-debfbd09271a', # San Jose ID from logs
            'name': 'Test Source',
            'type': 'web',
            'url': dummy_url,
            'scrape_url': dummy_url,
            'metadata': {'test_run': True}
        }
        print(f"Upserting: {payload}")
        
        res = db.client.table('sources').upsert(payload, on_conflict='jurisdiction_id,url').execute()
        print("✅ Upsert Success!")
        print(res.data)
        
        # Cleanup
        db.client.table('sources').delete().eq('url', dummy_url).execute()
        
    except Exception as e:
        print(f"❌ Upsert Failed: {e}")
        # Try without metadata to see if that's the trigger
        try:
            print("Retrying without metadata...")
            payload.pop('metadata')
            res = db.client.table('sources').upsert(payload, on_conflict='jurisdiction_id,url').execute()
            print("✅ Upsert (No Metadata) Success! - Problem IS metadata column.")
             # Cleanup
            db.client.table('sources').delete().eq('url', dummy_url).execute()
        except Exception as e2:
            print(f"❌ Upsert (No Metadata) Failed too: {e2}")

if __name__ == "__main__":
    asyncio.run(test_write())
