# SPEC-003: S3 Storage Backend

**Status**: Ready to Implement
**Epic**: `affordabot-hkg`

## 1. Overview
Implement S3-compatible storage (MinIO/R2) to replace object storage.

## 2. Technical Readiness
- **Code**: `backend.services.storage.s3_storage.S3Storage` implemented.
- **Contracts**: `BlobStorage` interface stable.
- **Dependencies**: `minio` in `pyproject.toml`.

## 3. Configuration
**Secrets Verified**:
The following are populated in Railway Shared Variables:
- `MINIO_URL`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `MINIO_BUCKET`
- `MINIO_SECURE`

## 4. Implementation Plan
1.  **Update Scripts**: Modify `scripts/cron/run_rag_spiders.py` to instantiate `S3Storage` using these env vars.
2.  **Verify**: Run a test upload/download cycle in the Railway environment (using `verify_sanjose_pipeline.py` or dedicated script).
