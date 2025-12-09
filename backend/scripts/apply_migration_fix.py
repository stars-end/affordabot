
import os
import subprocess
import sys
from urllib.parse import unquote

def apply_migration():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL not found")
        sys.exit(1)
        
    # Decompose URL manually to handle '@' in password
    # Format: postgresql://user:pass@host:port/dbname
    
    if not db_url.startswith("postgresql://"):
        print("❌ Unknown URL scheme")
        sys.exit(1)
        
    remainder = db_url[len("postgresql://"):]
    
    # Split dbname
    if "/" in remainder:
        auth_host_port, dbname = remainder.split("/", 1)
        # remove query params if any
        dbname = dbname.split("?")[0]
    else:
        auth_host_port = remainder
        dbname = "postgres"
    
    # Split auth from host (use last @)
    if "@" in auth_host_port:
        auth, host_port = auth_host_port.rsplit("@", 1)
    else:
        auth = ""
        host_port = auth_host_port
        
    # Split user:pass
    if ":" in auth:
        user, password = auth.split(":", 1)
    else:
        user = auth
        password = ""
        
    # Split host:port
    if ":" in host_port:
        host, port = host_port.split(":", 1)
    else:
        host = host_port
        port = "5432"
        
    # Unquote user/pass just in case (though Railway sends raw usually)
    user = unquote(user)
    password = unquote(password)
    
    print(f"Connecting to {host}:{port} as {user}")
    
    # Set Env Vars for psql
    env = os.environ.copy()
    env["PGUSER"] = user
    env["PGPASSWORD"] = password
    env["PGHOST"] = host
    env["PGPORT"] = port
    env["PGDATABASE"] = dbname
    # Force SSL
    env["PGSSLMODE"] = "require"
    
    # Path to your migration file (relative to backend/scripts)
    migration_file = os.path.join(os.path.dirname(__file__), '../../supabase/migrations/20251209081500_add_scrape_history_notes.sql')
    migration_file = os.path.abspath(migration_file)
    
    print(f"Applying {migration_file}...")
    
    try:
        # Don't pass db_url, rely on env
        subprocess.run(["psql", "-f", migration_file], env=env, check=True)
        print("✅ Migration applied successfully.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    apply_migration()
