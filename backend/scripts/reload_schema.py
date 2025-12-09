
import os
import subprocess
import sys
from urllib.parse import unquote

def reload_schema():
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
    
    # Force 5432 (Transaction Mode / Direct?)
    port = "5432"
        
    user = unquote(user)
    password = unquote(password)
    
    print(f"Connecting to {host}:{port} as {user} ...")
    
    env = os.environ.copy()
    env["PGUSER"] = user
    env["PGPASSWORD"] = password
    env["PGHOST"] = host
    env["PGPORT"] = port
    env["PGDATABASE"] = dbname
    env["PGSSLMODE"] = "require"
    
    print("Reloading PostgREST schema cache via Port 5432...")
    
    try:
        subprocess.run(["psql", "-c", "NOTIFY pgrst, 'reload schema';"], env=env, check=True)
        print("✅ Schema cache reload signaled.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Reload failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    reload_schema()
