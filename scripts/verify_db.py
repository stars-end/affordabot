#!/usr/bin/env python3
import os
import asyncio
import asyncpg
import sys

async def verify_connection():
    # Prioritize Public URL for local dev
    database_url = os.getenv("DATABASE_URL_PUBLIC") or os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ Neither DATABASE_URL_PUBLIC nor DATABASE_URL is set.")
        sys.exit(1)

    source = "PUBLIC" if os.getenv("DATABASE_URL_PUBLIC") else "DEFAULT"
    print(f"Checking connection using {source} URL: {database_url.split('@')[-1]}") # Hide credentials
    
    try:
        # Check if we need SSL (Railway usually does for remote)
        # But 'railway run' might provide an internal URL? 
        # Usually it provides a public URL or internal one. 
        # We'll rely on asyncpg defaults or explicit ssl='require' if it looks like a remote host.
        
        # Simple attempt with standard params
        conn = await asyncpg.connect(database_url)
        version = await conn.fetchval("SELECT version()")
        print(f"✅ Connected! DB Version: {version}")
        await conn.close()
        sys.exit(0)
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        # Try with SSL explicit if failed
        if "ssl" not in str(e).lower():
            print("Retrying with ssl='require'...")
            try:
                conn = await asyncpg.connect(database_url, ssl='require')
                version = await conn.fetchval("SELECT version()")
                print(f"✅ Connected with SSL! DB Version: {version}")
                await conn.close()
                sys.exit(0)
            except Exception as e2:
                print(f"❌ SSL Connection failed: {e2}")

        sys.exit(1)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_connection())
