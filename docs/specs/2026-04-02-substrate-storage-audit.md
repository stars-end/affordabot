# Substrate Storage Audit (bd-osue)

Date: 2026-04-02  
Repo: affordabot (`/tmp/agents/bd-5wd9/affordabot`)  
Scope: broad manual substrate run storage path (Postgres + pgvector + MinIO/S3)

## Scope Evidence
- Plan/spec: `docs/specs/2026-04-02-broad-substrate-expansion-plan.md`
- Run orchestration: `backend/scripts/substrate/manual_expansion_runner.py`
- Run inspection: `backend/scripts/substrate/substrate_inspection_report.py`
- Capture path: `backend/scripts/substrate/manual_capture.py`
- Ingestion + chunk/vector write path: `backend/services/ingestion_service.py`
- S3 backend: `backend/services/storage/s3_storage.py`
- Vector backend wiring: `backend/services/vector_backend_factory.py`
- Vector backend implementation: `backend/services/retrieval/local_pgvector.py`
- Schema baseline: `backend/migrations/002_schema_recovery_v2.sql`
- DB write API: `backend/db/postgres_client.py`
- Endpoint contract: `backend/main.py`

Path note:
- Requested reads `backend/services/vector_backend.py` and `backend/services/local_pgvector_backend.py` are not present in this worktree.
- Active equivalents are `backend/services/vector_backend_factory.py` and `backend/services/retrieval/local_pgvector.py`.

## 1) Where Raw Captured Artifacts Live
- Primary capture ledger is Postgres `raw_scrapes`:
  - raw payload in `raw_scrapes.data` (JSONB)
  - metadata/provenance in `raw_scrapes.metadata` (JSONB)
  - optional object key pointer in `raw_scrapes.storage_uri` (TEXT)
- For binary captures (`pdf_binary` / `binary_blob`), manual capture uploads object bytes to S3/MinIO and stores:
  - `raw_scrapes.storage_uri`
  - `raw_scrapes.data.content_storage_uri`
- For text-like captures, content lives inline in `raw_scrapes.data.content`; object storage may be added later during ingestion if `storage_uri` is still empty.
- Post-run inspection artifact JSON is written to:
  - `backend/scripts/substrate/artifacts/<run_id>_substrate_inspection_report.json`

## 2) How MinIO/S3 Object Keys Are Created and Referenced
- Manual capture binary key format (`manual_capture.upload_binary_artifact`):
  - `<source_id>/<year>/<month>/<content_hash>.<ext>`
  - `ext` from response content type (`pdf`, `html`, `json`, `txt`, fallback `bin`)
- Ingestion fallback key format (`IngestionService.process_raw_scrape`), only when `storage_uri` is missing:
  - `<source_id>/<year>/<month>/<scrape_id>.<ext>`
  - `ext` defaults to `.html`, uses `.pdf` for `application/pdf`
- `S3Storage.upload()` returns the key string (not a full URL), and the code persists that key in Postgres fields above.
- Bucket/endpoint are resolved from env (`MINIO_BUCKET`, `MINIO_URL_PUBLIC`/`RAILWAY_SERVICE_BUCKET_URL`/`MINIO_URL`) inside `S3Storage`.

## 3) How `raw_scrapes`, `documents`, `chunks`, and Vector Storage Relate
- `raw_scrapes` is the run/capture source-of-truth table (FK: `raw_scrapes.source_id -> sources.id`).
- `IngestionService` creates a generated `document_id` per processed scrape and writes it to:
  - `raw_scrapes.document_id`
  - each chunk row in `document_chunks.document_id`
  - each chunk metadata payload (`metadata.document_id`)
- `LocalPgVectorBackend.upsert()` writes vectors directly into `document_chunks`:
  - columns: `id, content, embedding, metadata, document_id`
- In this repo’s active SQL migrations, there is no `documents` table definition and no FK from `document_chunks.document_id` to a document table.
  - Practical result: “document” is currently an ID convention carried between `raw_scrapes` and `document_chunks`, not a relational entity.

## 4) What Broad Manual Runs Write to Each Layer
- Endpoint layer:
  - `POST /cron/manual-substrate-expansion` validates manifest and calls `run_manual_substrate_expansion`.
- Raw capture layer:
  - each source target runs `capture_document(...)` (HTTP fetch + source resolution + `raw_scrapes` insert)
  - manual run stamping updates `raw_scrapes.metadata` with:
    - `manual_run_id`, `manual_run_label`, `manual_asset_class`, `manual_jurisdiction_slug`, `manual_trigger_source`
  - legislation path inserts `raw_scrapes` records directly and includes same manual run metadata.
- Object storage layer:
  - non-text manual captures upload immediately at capture-time.
  - text captures may upload during ingestion if `storage_uri` absent.
- Vector layer (only when `run_mode = capture_and_ingest`):
  - ingestion creates chunks + embeddings and writes to `document_chunks` via pgvector backend.
  - `raw_scrapes` gets updated with `document_id`, `processed`, `ingestion_truth` stage and retrievability flags.
- Inspection layer:
  - report queries `raw_scrapes` by `metadata->>'manual_run_id' = run_id`
  - report artifact JSON is persisted to substrate artifacts directory.

## 5) What the Inspection Report Proves vs Cannot Prove
- It proves (for rows stamped with this run id):
  - row counts and distributions by `promotion_state`, `ingestion_truth.stage`, `trust_tier`, `content_class`
  - sampled row-level evidence for promoted/durable/candidate/denied buckets
  - failure bucket summaries based on stage/error/promotion reason
- It cannot prove:
  - S3 object existence/readability for `storage_uri` keys (no object-store verification)
  - actual vector row integrity by direct join/count against `document_chunks` (relies on `ingestion_truth` fields)
  - complete run coverage if a row was created but never stamped with `manual_run_id`
  - true OCR fallback count (`ocr_fallback_invocations` in runner response is currently hard-coded to `0`)

## 6) Storage-Layer Blind Spots / Safety Rails Before Real Broad Operator Proof
- Needed safety rail A (object durability check):
  - For all run rows with binary `content_class` or non-null `storage_uri`, verify object existence in bucket (HEAD/get-object).
- Needed safety rail B (vector integrity check):
  - Post-run SQL check: for `manual_run_id = <run_id>`, compare retrievable/raw counts against actual `document_chunks` rows by `document_id`.
- Needed safety rail C (run coverage check):
  - Compare resolved targets and attempted captures vs stamped rows (`manual_run_id`) to catch unstamped inserts.

Recommended decision for this lane:
- `ALL_IN_NOW` for adding the three checks above before claiming broad operator proof for storage durability/retrievability.
