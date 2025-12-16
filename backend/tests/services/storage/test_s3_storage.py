import pytest
from unittest.mock import patch
import os
from services.storage.s3_storage import S3Storage
from minio.error import S3Error

@pytest.fixture
def mock_minio():
    with patch("services.storage.s3_storage.Minio") as mock:
        yield mock

@pytest.fixture
def s3_env():
    return {
        "MINIO_URL": "localhost:9000",
        "MINIO_ACCESS_KEY": "admin",
        "MINIO_SECRET_KEY": "password",
        "MINIO_BUCKET": "test-bucket"
    }

def test_init_with_env_vars(mock_minio, s3_env):
    with patch.dict(os.environ, s3_env):
        storage = S3Storage()
        assert storage.client is not None
        mock_minio.assert_called_with(
            "localhost:9000",
            access_key="admin",
            secret_key="password",
            secure=False
        )

def test_init_without_vars(mock_minio):
    # Ensure no env vars leak
    with patch.dict(os.environ, {}, clear=True):
        storage = S3Storage()
        assert storage.client is None

def test_ensure_bucket_exists(mock_minio, s3_env):
    with patch.dict(os.environ, s3_env):
        mock_client = mock_minio.return_value
        mock_client.bucket_exists.return_value = False
        
        S3Storage()
        # _ensure_bucket is called in __init__
        mock_client.make_bucket.assert_called_with("test-bucket")

def test_ensure_bucket_already_exists(mock_minio, s3_env):
    with patch.dict(os.environ, s3_env):
        mock_client = mock_minio.return_value
        mock_client.bucket_exists.return_value = True
        
        S3Storage()
        mock_client.make_bucket.assert_not_called()

@pytest.mark.asyncio
async def test_upload_success(mock_minio, s3_env):
    with patch.dict(os.environ, s3_env):
        storage = S3Storage()
        content = b"test content"
        path = "test/file.txt"
        
        result = await storage.upload(path, content)
        
        assert result == path
        storage.client.put_object.assert_called_once()
        args = storage.client.put_object.call_args
        assert args[0][0] == "test-bucket"
        assert args[0][1] == path
        # content stream is checked implicitly by successful call

@pytest.mark.asyncio
async def test_upload_failure(mock_minio, s3_env):
    with patch.dict(os.environ, s3_env):
        storage = S3Storage()
        storage.client.put_object.side_effect = S3Error("code", "message", "resource", "request_id", "host_id", "response")
        
        with pytest.raises(S3Error):
            await storage.upload("path", b"data")

@pytest.mark.asyncio
async def test_get_url(mock_minio, s3_env):
    with patch.dict(os.environ, s3_env):
        storage = S3Storage()
        storage.client.presigned_get_object.return_value = "http://url"
        
        url = await storage.get_url("path/to/file")
        assert url == "http://url"
        storage.client.presigned_get_object.assert_called_with(
            "test-bucket", "path/to/file", expires=3600
        )
