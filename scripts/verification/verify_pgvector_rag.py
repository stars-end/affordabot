#!/usr/bin/env python3
"""
PgVector RAG Verification Script

Run this in Railway shell to verify PgVector RAG deployment.
Usage: poetry run python scripts/verify_pgvector_rag.py
"""

import asyncio
import os
import sys
from typing import Optional


async def check_environment():
    """Verify environment variables and configuration."""
    print("=" * 60)
    print("ENVIRONMENT CHECK")
    print("=" * 60)
    
    required_vars = [
        "DATABASE_URL",
        "MINIO_URL",
        "MINIO_ACCESS_KEY",
        "MINIO_SECRET_KEY",
        "MINIO_BUCKET",
    ]
    
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if "KEY" in var or "URL" in var:
                display = f"{value[:10]}...{value[-10:]}" if len(value) > 20 else "***"
            else:
                display = value
            print(f"✓ {var}: {display}")
        else:
            print(f"✗ {var}: NOT SET")
            missing.append(var)
    
    use_pgvector = os.getenv("USE_PGVECTOR_RAG", "false").lower() == "true"
    print(f"\n{'✓' if use_pgvector else '○'} USE_PGVECTOR_RAG: {use_pgvector}")
    
    if missing:
        print(f"\n❌ Missing required variables: {', '.join(missing)}")
        return False
    
    print("\n✅ Environment configuration OK")
    return True


async def check_imports():
    """Verify critical imports."""
    print("\n" + "=" * 60)
    print("IMPORT CHECK")
    print("=" * 60)
    
    imports = [
        ("llm_common.retrieval", "RetrievalBackend"),
        ("llm_common.retrieval.backends", "PgVectorBackend"),
        ("services.vector_backend_factory", "create_vector_backend"),
        ("services.storage.s3_storage", "S3Storage"),
    ]
    
    for module, item in imports:
        try:
            exec(f"from {module} import {item}")
            print(f"✓ {module}.{item}")
        except ImportError as e:
            print(f"✗ {module}.{item}: {e}")
            return False
    
    print("\n✅ All imports successful")
    return True


async def check_database():
    """Verify database connectivity and schema."""
    print("\n" + "=" * 60)
    print("DATABASE CHECK")
    print("=" * 60)
    
    try:
        import asyncpg
        
        database_url = os.getenv("DATABASE_URL")
        conn = await asyncpg.connect(database_url)
        
        print("✓ Database connection established")
        
        # Check if documents table exists
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'documents'
            )
        """)
        
        if table_exists:
            print("✓ 'documents' table exists")
            
            # Get row count
            count = await conn.fetchval("SELECT COUNT(*) FROM documents")
            print(f"  - Row count: {count}")
            
            # Check embedding dimensions if data exists
            if count > 0:
                sample = await conn.fetchrow("""
                    SELECT 
                        id,
                        array_length(embedding, 1) as dims,
                        created_at
                    FROM documents 
                    LIMIT 1
                """)
                print(f"  - Sample document ID: {sample['id']}")
                print(f"  - Embedding dimensions: {sample['dims']} (expected: 4096)")
                print(f"  - Created at: {sample['created_at']}")
                
                if sample['dims'] != 4096:
                    print(f"  ⚠️  WARNING: Expected 4096 dimensions, got {sample['dims']}")
        else:
            print("⚠️  'documents' table does not exist")
        
        await conn.close()
        print("\n✅ Database check complete")
        return True
        
    except Exception as e:
        print(f"\n❌ Database check failed: {e}")
        return False


async def check_vector_backend():
    """Verify vector backend configuration."""
    print("\n" + "=" * 60)
    print("VECTOR BACKEND CHECK")
    print("=" * 60)
    
    try:
        from services.vector_backend_factory import create_vector_backend
        
        backend = create_vector_backend()
        backend_type = backend.__class__.__name__
        
        # V3: We always expect LocalPgVectorBackend or similar Postgres-native backend
        expected = "LocalPgVectorBackend"
        
        print(f"Backend type: {backend_type}")
        print(f"Expected: {expected}")
        
        if backend_type == expected:
            print(f"\n✅ Correct backend active: {backend_type}")
            return True
        else:
            print(f"\n⚠️  Backend mismatch! Using {backend_type}, expected {expected}")
            return False
            
    except Exception as e:
        print(f"\n❌ Vector backend check failed: {e}")
        return False


async def check_minio():
    """Verify MinIO storage connectivity."""
    print("\n" + "=" * 60)
    print("MINIO STORAGE CHECK")
    print("=" * 60)
    
    try:
        from services.storage.s3_storage import S3Storage
        
        storage = S3Storage(
            endpoint=os.getenv("MINIO_URL"),
            access_key=os.getenv("MINIO_ACCESS_KEY"),
            secret_key=os.getenv("MINIO_SECRET_KEY"),
            bucket_name=os.getenv("MINIO_BUCKET"),
            secure=os.getenv("MINIO_SECURE", "true").lower() == "true"
        )
        
        print("✓ S3Storage client initialized")
        
        # List files
        files = await storage.list_files()
        print(f"✓ Bucket accessible")
        print(f"  - Total files: {len(files)}")
        
        if files:
            print(f"  - Recent files:")
            for f in files[:5]:
                print(f"    • {f}")
        
        print("\n✅ MinIO storage check complete")
        return True
        
    except Exception as e:
        print(f"\n❌ MinIO storage check failed: {e}")
        return False


async def run_verification():
    """Run all verification checks."""
    print("\n" + "=" * 60)
    print("PGVECTOR RAG VERIFICATION")
    print("=" * 60)
    print()
    
    checks = [
        ("Environment", check_environment),
        ("Imports", check_imports),
        ("Database", check_database),
        ("Vector Backend", check_vector_backend),
        ("MinIO Storage", check_minio),
    ]
    
    results = {}
    for name, check_func in checks:
        try:
            results[name] = await check_func()
        except Exception as e:
            print(f"\n❌ {name} check crashed: {e}")
            results[name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL CHECKS PASSED")
        print("=" * 60)
        print("\nPgVector RAG deployment is ready!")
        return 0
    else:
        print("❌ SOME CHECKS FAILED")
        print("=" * 60)
        print("\nPlease review the failures above and fix before proceeding.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_verification())
    sys.exit(exit_code)
