import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
backend_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, backend_root)

from db.postgres_client import PostgresDB


async def apply_migration():
    print("🚀 Connecting to database...")
    db = PostgresDB()
    await db.connect()

    migration_file = Path(backend_root) / "migrations/003_create_pipeline_steps.sql"
    print(f"📄 Reading migration: {migration_file}")

    try:
        with open(migration_file, "r") as f:
            sql = f.read()

        print("⚡ Executing migration...")
        await db._execute(sql)
        print("✅ Migration applied successfully!")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise e
    finally:
        await db.disconnect()


if __name__ == "__main__":
    if "DATABASE_URL" not in os.environ:
        print("DATABASE_URL missing. Run via: scripts/dx-railway-run.sh -- <command>")
        sys.exit(1)

    asyncio.run(apply_migration())
