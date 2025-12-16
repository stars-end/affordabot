#!/usr/bin/env python3
"""
Verification script for S3/MinIO Connection.
Run this in the Railway environment to verify storage access.

Usage:
    python backend/scripts/verification/verify_s3_connection.py
"""
import os
import asyncio
import logging
import sys

# Add backend to path (resolve relative to script location)
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_root = os.path.dirname(os.path.dirname(script_dir)) # backend/scripts/verification -> backend
sys.path.append(backend_root)

from services.storage.s3_storage import S3Storage  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_s3")

async def verify_s3():
    logger.info("🧪 Starting S3 Connection Verification")
    
    # Check Env Vars
    required_vars = ["MINIO_URL", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY", "MINIO_BUCKET"]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        logger.error(f"❌ Missing Environment Variables: {', '.join(missing)}")
        sys.exit(1)
        
    logger.info("✅ Environment Variables Present")
    
    # Initialize Client
    try:
        storage = S3Storage()
        if not storage.client:
            logger.error("❌ Failed to initialize S3 Client (check logs)")
            sys.exit(1)
        logger.info(f"✅ Client Initialized (Endpoint: {storage.endpoint}, Bucket: {storage.bucket})")
    except Exception as e:
        logger.error(f"❌ Initialization Exception: {e}")
        sys.exit(1)

    # Test Upload
    test_filename = "verification_test.txt"
    test_content = b"Hello MinIO! This is a verification test."
    test_path = f"tests/{test_filename}"
    
    try:
        logger.info(f"📤 Attempting upload to {test_path}...")
        uploaded_path = await storage.upload(test_path, test_content, "text/plain")
        logger.info(f"✅ Upload Successful: {uploaded_path}")
    except Exception as e:
        logger.error(f"❌ Upload Failed: {e}")
        sys.exit(1)
        
    # Test Download
    try:
        logger.info(f"hz Downloading from {test_path}...")
        content = await storage.download(test_path)
        if content == test_content:
            logger.info("✅ Download Successful & Content Verified")
        else:
            logger.error("❌ Content Mismatch")
            logger.error(f"Expected: {test_content}")
            logger.error(f"Got: {content}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Download Failed: {e}")
        sys.exit(1)

    # Test URL Generation
    try:
        logger.info("🔗 Testing Presigned URL generation...")
        url = await storage.get_url(test_path)
        logger.info(f"✅ URL Generated: {url}")
    except Exception as e:
        logger.error(f"❌ URL Generation Failed: {e}")
        sys.exit(1)
        
    logger.info("🎉 S3 Verification Complete! Storage is operational.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_s3())
