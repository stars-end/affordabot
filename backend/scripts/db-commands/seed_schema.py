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

    print(f"🚀 Connecting to database...")
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
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
            print(f"  ✅ Done.")
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            # Identify if it's a critical error or acceptable (e.g. "already exists" in simplistic scripts)
            # For CI empty DB, it should not fail.
            sys.exit(1)

    print("🏁 All migrations applied successfully.")
    conn.close()

if __name__ == "__main__":
    run_migrations()
