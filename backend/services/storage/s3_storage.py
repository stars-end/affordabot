"""
S3/MinIO Storage Backend for Affordabot.
Uses S3-compatible MinIO for artifact storage.
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
        # v2.3: support both legacy MINIO_* and Railway-style S3_*/AWS_* env shape.
        internal_url = self._normalize_endpoint(
            os.getenv("MINIO_URL") or os.getenv("S3_ENDPOINT", "")
        )
        # Check both MINIO_URL_PUBLIC and RAILWAY_SERVICE_BUCKET_URL for public endpoint.
        public_url = self._normalize_endpoint(os.getenv("MINIO_URL_PUBLIC", ""))
        if not public_url:
            # Fallback to RAILWAY_SERVICE_BUCKET_URL (automatically set by Railway)
            railway_bucket_url = os.getenv("RAILWAY_SERVICE_BUCKET_URL", "")
            if railway_bucket_url:
                public_url = self._normalize_endpoint(railway_bucket_url)

        # Use public URL if available, otherwise fall back to internal URL.
        # This resolves DNS issues inside Railway's network where the internal hostname
        # may not be resolvable, but the public one always is.
        chosen_endpoint = public_url if public_url else internal_url
        
        self.endpoint = endpoint or chosen_endpoint
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY") or os.getenv(
            "AWS_ACCESS_KEY_ID"
        )
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY") or os.getenv(
            "AWS_SECRET_ACCESS_KEY"
        )
        self.bucket = (
            bucket
            or os.getenv("MINIO_BUCKET")
            or os.getenv("S3_BUCKET_NAME")
            or "affordabot-artifacts"
        )
        
        # Secure should be true if we are using the public URL.
        is_using_public_url = (self.endpoint == public_url and public_url != "")
        self.secure = secure or is_using_public_url
        
        if not all([self.endpoint, self.access_key, self.secret_key]):
            logger.warning("MinIO credentials not fully configured. Storage operations may fail.")
            self.client = None
        else:
            self.client = self._initialize_client(self.endpoint, self.secure)

            if self.client:
                logger.info(f"S3Storage initialized: {self.endpoint}/{self.bucket}")
                self._ensure_bucket()
            else:
                logger.error("Failed to initialize MinIO client even after attempts.")

    @staticmethod
    def _normalize_endpoint(raw: str) -> str:
        return raw.replace("http://", "").replace("https://", "").rstrip("/")

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
            from datetime import timedelta
            url = self.client.presigned_get_object(self.bucket, path, expires=timedelta(seconds=expiry_seconds))
            logger.info(f"Generated presigned URL for: {path}")
            return url
        except S3Error as e:
            logger.error(f"Failed to generate URL for {path}: {e}")
            raise
