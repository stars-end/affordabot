
import os
import sys
import subprocess
from urllib.parse import urlparse

def main():
    if len(sys.argv) > 1:
        migration_file = sys.argv[1]
    else:
        print("Error: migration file path argument is required.")
        sys.exit(1)

    if not os.path.exists(migration_file):
        print(f"Error: Migration file not found: {migration_file}")
        sys.exit(1)

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL not set")
        sys.exit(1)
        
    try:
        p = urlparse(db_url)
        env = os.environ.copy()
        env["PGPASSWORD"] = p.password
        env["PGSSLMODE"] = "require"
        
        # Construct psql command
        # psql -h HOST -U USER -d DBNAME -f FILE
        cmd = [
            "psql", 
            "-h", p.hostname, 
            "-U", p.username, 
            "-d", p.path[1:], 
            "-f", migration_file
        ]
        
        print(f"Applying migration {migration_file} to {p.hostname}...")
        subprocess.run(cmd, env=env, check=True)
        print("✅ Migration applied successfully.")
        
    except Exception as e:
        print(f"❌ Failed to apply migration: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
