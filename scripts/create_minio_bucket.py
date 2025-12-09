#!/usr/bin/env python3
"""
Create MinIO bucket for Affordabot artifacts.
Run this via: railway run python scripts/create_minio_bucket.py
"""

import os
import sys
from minio import Minio
from minio.error import S3Error

def main():
    # Get MinIO credentials from env
    minio_url = os.environ.get("MINIO_URL", "").replace("http://", "").replace("https://", "")
    access_key = os.environ.get("MINIO_ACCESS_KEY")
    secret_key = os.environ.get("MINIO_SECRET_KEY")
    bucket_name = os.environ.get("MINIO_BUCKET", "affordabot-artifacts")
    
    if not all([minio_url, access_key, secret_key]):
        print("❌ Missing MinIO credentials in environment")
        print(f"MINIO_URL: {minio_url}")
        print(f"MINIO_ACCESS_KEY: {'set' if access_key else 'missing'}")
        print(f"MINIO_SECRET_KEY: {'set' if secret_key else 'missing'}")
        sys.exit(1)
    
    print(f"Connecting to MinIO at {minio_url}...")
    
    # Create MinIO client
    client = Minio(
        minio_url,
        access_key=access_key,
        secret_key=secret_key,
        secure=False  # Internal Railway network uses HTTP
    )
    
    # Check if bucket exists
    try:
        if client.bucket_exists(bucket_name):
            print(f"✅ Bucket '{bucket_name}' already exists")
        else:
            print(f"Creating bucket '{bucket_name}'...")
            client.make_bucket(bucket_name)
            print(f"✅ Bucket '{bucket_name}' created successfully")
    except S3Error as e:
        print(f"❌ MinIO Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
