from supabase import Client
import logging
from contracts.storage import BlobStorage

logger = logging.getLogger(__name__)

class SupabaseBlobStorage(BlobStorage):
    """
    Blob Storage implementation using Supabase Storage (S3 wrapper).
    """

    def __init__(self, supabase_client: Client, bucket_name: str = "raw_scrapes"):
        self.client = supabase_client
        self.bucket_name = bucket_name

    async def upload(self, path: str, content: bytes, content_type: str = "application/octet-stream") -> str:
        """
        Uploads file to Supabase Storage.
        """
        try:
            # Upsert is safer for idempotency
            self.client.storage.from_(self.bucket_name).upload(
                path=path,
                file=content,
                file_options={"content-type": content_type, "upsert": "true"}
            )
            logger.info(f"Uploaded {path} to Supabase Storage")
            return path
        except Exception as e:
            logger.error(f"Failed to upload {path} to Supabase Storage: {e}")
            raise e

    async def download(self, path: str) -> bytes:
        """
        Downloads file from Supabase Storage.
        """
        try:
            res = self.client.storage.from_(self.bucket_name).download(path)
            return res
        except Exception as e:
            logger.error(f"Failed to download {path} from Supabase Storage: {e}")
            raise e

    async def get_url(self, path: str, expiry_seconds: int = 3600) -> str:
        """
        Get signed URL for the object.
        """
        try:
            res = self.client.storage.from_(self.bucket_name).create_signed_url(path, expiry_seconds)
            return res.get("signedURL")
        except Exception as e:
            logger.error(f"Failed to generate URL for {path}: {e}")
            raise e
