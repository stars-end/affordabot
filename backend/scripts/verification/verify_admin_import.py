import sys
from pathlib import Path
import os
from unittest.mock import MagicMock

# Setup paths
backend_root = str(Path(__file__).parent.parent.parent)
sys.path.append(backend_root)

# Mock dependencies that might require env vars or DB
sys.modules["db.postgres_client"] = MagicMock()

async def main():
    print("🚀 Verifying Admin Router Import...")
    try:
        # We need to set dummy env vars if needed
        os.environ["ZAI_API_KEY"] = "mock"
        
        # Import admin router
        from routers import admin
        print("✅ Successfully imported routers.admin")
        
        # Check specific function
        if hasattr(admin, "_run_analysis_task"):
            print("✅ Found _run_analysis_task")
        else:
            print("❌ _run_analysis_task NOT found")
            sys.exit(1)
            
        print("✅ Admin router verification passed.")

    except Exception as e:
        print(f"❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
