from abc import ABC, abstractmethod

class BlobStorage(ABC):
    """
    Abstract base class for Blob Storage (Object Store).
    Used to store raw files (PDFs, HTML) before processing.
    """

    @abstractmethod
    async def upload(self, path: str, content: bytes, content_type: str = "application/octet-stream") -> str:
        """
        Upload content to storage.
        Returns the URI/Path of the stored object.
        """
        pass

    @abstractmethod
    async def download(self, path: str) -> bytes:
        """
        Download content from storage.
        """
        pass

    @abstractmethod
    async def get_url(self, path: str, expiry_seconds: int = 3600) -> str:
        """
        Get a public or signed URL for the object.
        """
        pass
