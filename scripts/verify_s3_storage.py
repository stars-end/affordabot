#!/usr/bin/env python3
"""
Verify S3/MinIO storage connectivity and operations.
Run via: cd backend && poetry run python ../scripts/verify_s3_storage.py
"""

import asyncio
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../backend'))

from services.storage.s3_storage import S3Storage


async def main():
    print("🧪 Testing S3/MinIO Storage...")
    
    # Initialize storage
    storage = S3Storage()
    
    if not storage.client:
        print("❌ S3Storage client not initialized (check MINIO_* env vars)")
        sys.exit(1)
    
    print(f"✅ Connected to MinIO: {storage.endpoint}/{storage.bucket}")
    
    # Test 1: Upload
    test_path = "test/verify_upload.txt"
    test_content = b"Hello from Affordabot S3 verification!"
    
    try:
        print(f"\n📤 Testing upload: {test_path}")
        result = await storage.upload(test_path, test_content, "text/plain")
        print(f"✅ Upload successful: {result}")
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        sys.exit(1)
    
    # Test 2: Download
    try:
        print(f"\n📥 Testing download: {test_path}")
        downloaded = await storage.download(test_path)
        if downloaded == test_content:
            print(f"✅ Download successful ({len(downloaded)} bytes)")
        else:
            print(f"❌ Downloaded content mismatch")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Download failed: {e}")
        sys.exit(1)
    
    # Test 3: Get URL
    try:
        print(f"\n🔗 Testing presigned URL: {test_path}")
        url = await storage.get_url(test_path, expiry_seconds=300)
        print(f"✅ Presigned URL generated: {url[:80]}...")
    except Exception as e:
        print(f"❌ Get URL failed: {e}")
        sys.exit(1)
    
    # Test 4: Delete (cleanup)
    try:
        print(f"\n🗑️  Cleaning up: {test_path}")
        if storage.delete(test_path):
            print(f"✅ Cleanup successful")
        else:
            print(f"⚠️  Cleanup failed (non-critical)")
    except Exception as e:
        print(f"⚠️  Cleanup error (non-critical): {e}")
    
    print("\n✅ All S3/MinIO storage tests passed!")

if __name__ == "__main__":
    asyncio.run(main())
