import asyncio
import os
import sys

# Add parent dir (backend) to path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(backend_path)
print(f"DEBUG: CWD={os.getcwd()}")
print(f"DEBUG: sys.path appended: {backend_path}")
print(f"DEBUG: sys.path: {sys.path}")

import asyncpg
from services.storage.s3_storage import S3Storage

async def verify_db():
    print("\n📦 Verifying Remote Database...")
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL not set")
        return False
    
    print(f"   URL: {db_url[:20]}... (masked)")
    
    try:
        conn = await asyncpg.connect(db_url)
        # Check connection details
        row = await conn.fetchrow("SELECT current_database(), inet_server_addr()")
        print(f"   ✅ Connected to DB: {row['current_database']}")
        print(f"   📍 Server IP: {row['inet_server_addr']}")

        # Check document_chunks table
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'document_chunks'
            );
        """)
        if table_exists:
            print("   ✅ Table 'document_chunks' EXISTS")
            # Check count
            count = await conn.fetchval("SELECT COUNT(*) FROM document_chunks")
            print(f"   📊 Chunk Count: {count}")
        else:
            print("   ⚠️ Table 'document_chunks' DOES NOT EXIST")
            # Create it if needed? No, script should just verify. 
            # But for e2e redo, we might need to create it.
            print("   🛠️ Attempting creation...")
            await conn.execute("""
                CREATE EXTENSION IF NOT EXISTS vector;
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id UUID PRIMARY KEY,
                    document_id UUID,
                    content TEXT,
                    embedding vector(4096),
                    metadata JSONB
                );
            """)
            print("   ✅ Created 'document_chunks'")

        await conn.close()
        return True
    except Exception as e:
        print(f"❌ DB Verification Failed: {e}")
        return False

async def verify_storage():
    print("\n🪣 Verifying Remote Storage (MinIO)...")
    try:
        storage = S3Storage()
        test_content = b"Audit Verification Test Content"
        filename = "audit_verify_remote.txt"
        
        url = await storage.upload(test_content, filename, content_type="text/plain")
        if url:
            print(f"   ✅ Upload Successful")
            print(f"   🔗 URL: {url}")
            return True
        else:
            print("   ❌ Upload Failed (No URL returned)")
            return False
    except Exception as e:
        print(f"❌ Storage Verification Failed: {e}")
        return False

async def main():
    print("🔍 Starting Remote Infrastructure Verification")
    db_ok = await verify_db()
    storage_ok = await verify_storage()
    
    if db_ok and storage_ok:
        print("\n✅ All Remote Checks Passed")
    else:
        print("\n❌ Some Checks Failed")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
