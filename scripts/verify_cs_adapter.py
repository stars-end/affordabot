
import sys
import os
import asyncio
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.append(str(backend_path))

from services.scraper.city_scrapers_adapter import SanJoseCSAdapter

async def verify():
    print("Verifying SanJoseCSAdapter...")
    try:
        adapter = SanJoseCSAdapter()
        print(f"✅ Instantiation successful.")
        print(f"Project Dir: {adapter.project_dir}")
        
        if not os.path.exists(adapter.project_dir):
            print(f"❌ Project directory does not exist: {adapter.project_dir}")
            sys.exit(1)
            
        print("✅ Project directory exists.")
        
        # Check if scrapy.cfg exists
        if not os.path.exists(os.path.join(adapter.project_dir, "scrapy.cfg")):
             print(f"❌ scrapy.cfg not found in {adapter.project_dir}")
             sys.exit(1)
        
        print("✅ scrapy.cfg found.")

        # Try to run check_health (which defaults to True currently)
        # But let's try to run 'scrapy list' using the logic from adapter (simulated)
        import shutil
        import subprocess
        
        backend_python = shutil.which("python3")
        cmd = [backend_python, "-m", "scrapy", "list"]
        
        print(f"Running: {' '.join(cmd)} in {adapter.project_dir}")
        
        process = subprocess.run(
            cmd, 
            cwd=adapter.project_dir, 
            capture_output=True, 
            text=True,
            env={**os.environ, "PYTHONPATH": os.environ.get("PYTHONPATH", "") + ":" + os.getcwd()}
        )
        
        if process.returncode != 0:
            print(f"❌ Scrapy list failed: {process.stderr}")
            # It might fail if city-scrapers-core not installed?
            # It is in backend poetry env. We are running this script.
            # Are we running with poetry run?
        else:
            print(f"Scrapy Output:\n{process.stdout}")
            if "sanjose_meetings" in process.stdout:
                print("✅ sanjose_meetings spider found!")
            else:
                 print("❌ sanjose_meetings spider NOT found in output.")
                 sys.exit(1)

    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(verify())
