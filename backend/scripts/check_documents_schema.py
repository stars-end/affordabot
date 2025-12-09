
import os
import sys
import subprocess
from urllib.parse import urlparse

def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL not set")
        sys.exit(1)
        
    try:
        p = urlparse(db_url)
        env = os.environ.copy()
        env["PGPASSWORD"] = p.password
        env["PGSSLMODE"] = "require"
        
        cmd = ["psql", "-h", p.hostname, "-U", p.username, "-d", p.path[1:], "-c", "\\d documents"]
        print(f"Connecting to {p.hostname}...")
        subprocess.run(cmd, env=env, check=True)
        
    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
