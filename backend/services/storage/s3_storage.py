"""
S3/MinIO Storage Backend for Affordabot.
Replaces Supabase Storage with S3-compatible MinIO.
"""

import os
import logging
from typing import Optional, BinaryIO
from minio import Minio
from minio.error import S3Error
from io import BytesIO

logger = logging.getLogger(__name__)


class S3Storage:
    """S3-compatible storage backend using MinIO."""
    
    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket: Optional[str] = None,
        secure: bool = False
    ):
        """
        Initialize S3Storage client.
        
        Args:
            endpoint: MinIO endpoint (e.g., "bucket.railway.internal:9000")
            access_key: MinIO access key
            secret_key: MinIO secret key
            bucket: Bucket name
            secure: Use HTTPS (default False for internal Railway network)
        """
        self.endpoint = endpoint or os.getenv("MINIO_URL", "").replace("http://", "").replace("https://", "")
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY")
        self.bucket = bucket or os.getenv("MINIO_BUCKET", "affordabot-artifacts")
        self.secure = secure
        
        if not all([self.endpoint, self.access_key, self.secret_key]):
            logger.warning("MinIO credentials not fully configured. Storage operations may fail.")
            self.client = None
        else:
            try:
                self.client = Minio(
                    self.endpoint,
                    access_key=self.access_key,
                    secret_key=self.secret_key,
                    secure=self.secure
                )
                logger.info(f"S3Storage initialized: {self.endpoint}/{self.bucket}")
                self._ensure_bucket()
            except Exception as e:
                logger.error(f"Failed to initialize MinIO client: {e}")
                self.client = None
    
    def _ensure_bucket(self):
        """Ensure bucket exists, create if not."""
        if not self.client:
            return
        
        try:
            if not self.client.bucket_exists(self.bucket):
                logger.info(f"Creating bucket: {self.bucket}")
                self.client.make_bucket(self.bucket)
                logger.info(f"Bucket created: {self.bucket}")
        except S3Error as e:
            logger.error(f"Failed to ensure bucket exists: {e}")
    
    async def upload(self, path: str, content: bytes, content_type: str = "application/octet-stream") -> str:
        """
        Upload file to S3.
        
        Args:
            path: Path/key for the file in the bucket
            content: File data as bytes
            content_type: MIME type of the file
            
        Returns:
            Path of uploaded file
        """
        if not self.client:
            logger.error("MinIO client not initialized")
            raise RuntimeError("MinIO client not initialized")
        
        try:
            data_stream = BytesIO(content)
            self.client.put_object(
                self.bucket,
                path,
                data_stream,
                length=len(content),
                content_type=content_type
            )
            logger.info(f"Uploaded: {path} ({len(content)} bytes)")
            return path
        except S3Error as e:
            logger.error(f"Failed to upload {path}: {e}")
            raise
    
    async def download(self, path: str) -> bytes:
        """
        Download file from S3.
        
        Args:
            path: Path/key for the file in the bucket
            
        Returns:
            File data as bytes
        """
        if not self.client:
            logger.error("MinIO client not initialized")
            raise RuntimeError("MinIO client not initialized")
        
        try:
            response = self.client.get_object(self.bucket, path)
            data = response.read()
            response.close()
            response.release_conn()
            logger.info(f"Downloaded: {path} ({len(data)} bytes)")
            return data
        except S3Error as e:
            logger.error(f"Failed to download {path}: {e}")
            raise
    
    async def get_url(self, path: str, expiry_seconds: int = 3600) -> str:
        """
        Get presigned URL for file access.
        
        Args:
            path: Path/key for the file in the bucket
            expiry_seconds: URL expiration time in seconds (default 1 hour)
            
        Returns:
            Presigned URL
        """
        if not self.client:
            logger.error("MinIO client not initialized")
            raise RuntimeError("MinIO client not initialized")
        
        try:
            url = self.client.presigned_get_object(self.bucket, path, expires=expiry_seconds)
            logger.info(f"Generated presigned URL for: {path}")
            return url
        except S3Error as e:
            logger.error(f"Failed to generate URL for {path}: {e}")
            raise
