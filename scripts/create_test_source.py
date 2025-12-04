"""Create a test source for Web Reader verification."""

from supabase import create_client
import os
import sys

def create_test_source():
    client = create_client(
        os.environ['SUPABASE_URL'],
        os.environ['SUPABASE_SERVICE_ROLE_KEY']
    )
    
    # Check if test source already exists
    existing = client.table('sources').select('*').eq('url', 'https://www.sanjoseca.gov/your-government/departments-offices/planning-building-code-enforcement').execute()
    
    if existing.data:
        print(f"✅ Test source already exists: {existing.data[0]['id']}")
        return existing.data[0]['id']
    
    # Get a jurisdiction_id (assuming San Jose exists)
    jurisdictions = client.table('jurisdictions').select('id').eq('name', 'San Jose').execute()
    if not jurisdictions.data:
        print("❌ San Jose jurisdiction not found. Creating...")
        jur = client.table('jurisdictions').insert({
            'name': 'San Jose',
            'state': 'CA',
            'type': 'city'
        }).execute()
        jurisdiction_id = jur.data[0]['id']
    else:
        jurisdiction_id = jurisdictions.data[0]['id']
    
    # Create test source
    source = client.table('sources').insert({
        'jurisdiction_id': jurisdiction_id,
        'url': 'https://www.sanjoseca.gov/your-government/departments-offices/planning-building-code-enforcement',
        'type': 'permits',
        'source_method': 'web_reader',
        'status': 'active',
        'handler': 'web_reader'
    }).execute()
    
    print(f"✅ Created test source: {source.data[0]['id']}")
    return source.data[0]['id']

if __name__ == "__main__":
    source_id = create_test_source()
    print(f"\nTest Source ID: {source_id}")
