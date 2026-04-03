#!/usr/bin/env python3
"""
Create MinIO bucket for Affordabot artifacts.
Run this via:
  railway run -p <project-id> -e <env> -s backend -- python scripts/create_minio_bucket.py
"""

import os
import sys
from minio import Minio
from minio.error import S3Error


def _normalize_endpoint(raw: str) -> str:
    return raw.replace("http://", "").replace("https://", "").rstrip("/")


def _resolve_endpoint() -> tuple[str, bool, str]:
    """
    Resolve endpoint using the same precedence as runtime storage:
    MINIO_URL_PUBLIC -> RAILWAY_SERVICE_BUCKET_URL -> MINIO_URL.
    """
    internal = _normalize_endpoint(os.environ.get("MINIO_URL", ""))
    public = _normalize_endpoint(os.environ.get("MINIO_URL_PUBLIC", ""))
    if public:
        return public, True, "MINIO_URL_PUBLIC"

    railway_public = _normalize_endpoint(os.environ.get("RAILWAY_SERVICE_BUCKET_URL", ""))
    if railway_public:
        return railway_public, True, "RAILWAY_SERVICE_BUCKET_URL"

    if internal:
        return internal, False, "MINIO_URL"

    return "", False, ""


def main():
    # Get MinIO credentials from env
    minio_url, secure, endpoint_source = _resolve_endpoint()
    access_key = os.environ.get("MINIO_ACCESS_KEY")
    secret_key = os.environ.get("MINIO_SECRET_KEY")
    bucket_name = os.environ.get("MINIO_BUCKET", "affordabot-artifacts")
    
    if not all([minio_url, access_key, secret_key]):
        print("❌ Missing MinIO credentials in environment")
        print(f"MINIO_URL: {'set' if os.environ.get('MINIO_URL') else 'missing'}")
        print(f"MINIO_URL_PUBLIC: {'set' if os.environ.get('MINIO_URL_PUBLIC') else 'missing'}")
        print(f"RAILWAY_SERVICE_BUCKET_URL: {'set' if os.environ.get('RAILWAY_SERVICE_BUCKET_URL') else 'missing'}")
        print(f"MINIO_ACCESS_KEY: {'set' if access_key else 'missing'}")
        print(f"MINIO_SECRET_KEY: {'set' if secret_key else 'missing'}")
        sys.exit(1)
    
    print(f"Connecting to MinIO at {minio_url} (source={endpoint_source}, secure={secure})...")
    
    # Create MinIO client
    client = Minio(
        minio_url,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure,
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
