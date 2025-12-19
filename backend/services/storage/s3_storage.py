"""
S3/MinIO Storage Backend for Affordabot.
Replaces Supabase Storage with S3-compatible MinIO.
"""

import os
import logging
from typing import Optional
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
        # v2.1: support public endpoint fallback for local dev/verification
        internal_url = os.getenv("MINIO_URL", "").replace("http://", "").replace("https://", "")
        public_url = os.getenv("MINIO_URL_PUBLIC", "").replace("http://", "").replace("https://", "")
        
        # If internal_url looks like it's only for Railway network and we have a public URL, 
        # use public URL unless we are actually in Railway.
        # Note: RAILWAY_ENVIRONMENT_NAME is set when running on Railway servers.
        is_on_railway = os.getenv("RAILWAY_ENVIRONMENT_NAME") is not None
        
        self.endpoint = endpoint or (internal_url if (is_on_railway or not public_url) else public_url)
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY")
        self.bucket = bucket or os.getenv("MINIO_BUCKET", "affordabot-artifacts")
        self.secure = secure or (self.endpoint == public_url and public_url != "")
        
        if not all([self.endpoint, self.access_key, self.secret_key]):
            logger.warning("MinIO credentials not fully configured. Storage operations may fail.")
            self.client = None
        else:
            self.client = self._initialize_client(self.endpoint, self.secure)
            
            # Fallback for local verification if internal DNS fails
            if not self.client and not is_on_railway:
                 # Already tried public if not on railway, so nothing to do
                 pass
            elif not self.client and is_on_railway and public_url:
                logger.warning(f"Internal MinIO ({self.endpoint}) failed/unreachable. Falling back to Public URL: {public_url}")
                self.endpoint = public_url
                self.secure = True
                self.client = self._initialize_client(self.endpoint, self.secure)

            if self.client:
                logger.info(f"S3Storage initialized: {self.endpoint}/{self.bucket}")
                self._ensure_bucket()
            else:
                logger.error("Failed to initialize MinIO client even after attempts.")

    def _initialize_client(self, endpoint, secure):
        """Helper to init Minio client without crashing on DNS errors."""
        try:
            client = Minio(
                endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=secure
            )
            # Connectivity check (will fail on DNS errors)
            # We use a non-existent bucket check to verify resolution
            # but wait, bucket_exists might also be slow.
            # Let's just return the object and let ensure_bucket catch the error.
            return client
        except Exception as e:
            logger.error(f"MinIO client init error: {e}")
            return None
    
    def _ensure_bucket(self):
        """Ensure bucket exists, create if not."""
        if not self.client:
            return
        
        try:
            if not self.client.bucket_exists(self.bucket):
                logger.info(f"Creating bucket: {self.bucket}")
                self.client.make_bucket(self.bucket)
                logger.info(f"Bucket created: {self.bucket}")
        except Exception as e:
            logger.error(f"Failed to ensure bucket exists (DNS or Connection issue): {e}")
            # If we fail here, maybe we should try to invalidate the client?
            # But let's keep it for now as a warning.
    
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
