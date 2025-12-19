import asyncio
import os
import json
from db.postgres_client import PostgresDB

async def verify():
    print("🔍 Auditing E2E Pipeline Results for San Jose...")
    db = PostgresDB()
    await db.connect()
    
    # 1. Check Jurisdiction
    row = await db._fetchrow("SELECT id FROM jurisdictions WHERE slug = 'san-jose'")
    if not row:
        print("❌ Jurisdiction 'san-jose' not found.")
        return
    jur_id = row['id']
    print(f"✅ Jurisdiction ID: {jur_id}")
    
    # 2. Check Legislation
    rows = await db._fetch("SELECT id, bill_number, title FROM legislation WHERE jurisdiction_id = $1", jur_id)
    print(f"✅ Legislation: {len(rows)} bills found.")
    for r in rows[:3]:
        print(f"   - {r['bill_number']}: {r['title'][:50]}...")
        
    # 3. Check Raw Scrapes
    rows = await db._fetch("""
        SELECT rs.id, rs.url, rs.content_hash 
        FROM raw_scrapes rs
        JOIN sources s ON rs.source_id = s.id
        WHERE s.jurisdiction_id = $1
    """, jur_id)
    print(f"✅ Raw Scrapes: {len(rows)} records found.")
    
    # 4. Check Document Chunks
    rows = await db._fetch("""
        SELECT dc.id, dc.document_id, LEFT(dc.content, 50) as snippet
        FROM document_chunks dc
        JOIN raw_scrapes rs ON dc.document_id = rs.id
        JOIN sources s ON rs.source_id = s.id
        WHERE s.jurisdiction_id = $1
    """, jur_id)
    print(f"✅ Document Chunks: {len(rows)} chunks embedded.")
    if rows:
        print(f"   Sample: {rows[0]['snippet']}...")

    await db.close()

if __name__ == "__main__":
    asyncio.run(verify())
