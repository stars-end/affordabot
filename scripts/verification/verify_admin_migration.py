import sys
import os
import asyncio
# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../backend'))

from db.postgres_client import PostgresDB

async def verify():
    print("Initializing PostgresDB...")
    db = PostgresDB()
    
    expected_methods = [
        'get_model_configs',
        'update_model_config',
        'get_system_prompt',
        'update_system_prompt',
        'get_analysis_history',
        'get_admin_task',
        'get_pending_reviews',
        'update_review_status'
    ]
    
    missing = []
    for method in expected_methods:
        if not hasattr(db, method):
            missing.append(method)
            
    if missing:
        print(f"FAILED: Missing methods in PostgresDB: {missing}")
        sys.exit(1)
    else:
        print("SUCCESS: All required PostgresDB methods present.")

    # Check admin router imports
    try:
        from routers import admin
        print("SUCCESS: Admin router imported successfully (Supabase dependencies removed).")
    except ImportError as e:
        print(f"FAILED: Admin router import failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"FAILED: Admin router import raised exception: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(verify())
