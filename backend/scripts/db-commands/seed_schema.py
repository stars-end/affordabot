import os
import sys
import psycopg2
from pathlib import Path

# Setup paths
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
MIGRATIONS_DIR = BACKEND_DIR.parent / "supabase" / "migrations"

def run_migrations():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL is not set.")
        sys.exit(1)

    print("🚀 Connecting to database...")
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        
        # Bootstrap Supabase roles if missing (for CI/Generic Postgres)
        print("🔧 Checking Supabase roles...")
        roles_sql = """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'anon') THEN
            CREATE ROLE anon NOLOGIN;
          END IF;
          IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'authenticated') THEN
            CREATE ROLE authenticated NOLOGIN;
          END IF;
          IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'service_role') THEN
            CREATE ROLE service_role NOLOGIN;
            GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
            ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO postgres, service_role;
          END IF;
        END
        $$;
        """
        cur.execute(roles_sql)
        print("  ✅ Roles valid.")
        
    except Exception as e:
        print(f"❌ Failed to connect/init: {e}")
        sys.exit(1)

    # Get migration files
    if not MIGRATIONS_DIR.exists():
        print(f"❌ Migrations directory not found: {MIGRATIONS_DIR}")
        sys.exit(1)
        
    sql_files = sorted([f for f in MIGRATIONS_DIR.iterdir() if f.suffix == '.sql'])
    
    print(f"📂 Found {len(sql_files)} migration files in {MIGRATIONS_DIR}")

    for sql_file in sql_files:
        print(f"▶️ applying {sql_file.name}...")
        try:
            sql = sql_file.read_text()
            cur.execute(sql)
            print("  ✅ Done.")
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            # Identify if it's a critical error or acceptable (e.g. "already exists" in simplistic scripts)
            # For CI empty DB, it should not fail.
            sys.exit(1)

    print("🏁 All migrations applied successfully.")
    conn.close()

if __name__ == "__main__":
    run_migrations()
