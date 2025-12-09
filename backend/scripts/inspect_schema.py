
import os
import subprocess
import sys
from urllib.parse import unquote

def inspect_raw_scrapes():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL not found")
        sys.exit(1)
        
    remainder = db_url[len("postgresql://"):]
    if "/" in remainder:
        auth_host_port, dbname = remainder.split("/", 1)
        dbname = dbname.split("?")[0]
    else:
        auth_host_port = remainder
        dbname = "postgres"
    if "@" in auth_host_port:
        auth, host_port = auth_host_port.rsplit("@", 1)
    else:
        auth = ""
        host_port = auth_host_port
    if ":" in auth:
        user, password = auth.split(":", 1)
    else:
        user = auth
        password = ""
    if ":" in host_port:
        host, port = host_port.split(":", 1)
    else:
        host = host_port
    
    port = "5432"
        
    user = unquote(user)
    password = unquote(password)
    
    env = os.environ.copy()
    env["PGUSER"] = user
    env["PGPASSWORD"] = password
    env["PGHOST"] = host
    env["PGPORT"] = port
    env["PGDATABASE"] = dbname
    env["PGSSLMODE"] = "require"
    
    try:
        subprocess.run(["psql", "-c", "\\d raw_scrapes"], env=env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Inspect failed: {e}")

if __name__ == "__main__":
    inspect_raw_scrapes()
