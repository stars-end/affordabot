
# Unit Test Plan (affordabot-4yz)

## Goal
Achieve high confidence in core data pipeline components (`IngestionService`, `DiscoveryServices`) via unit tests.

## Scope
1. **IngestionService**
   - Verify text extraction logic (HTML cleaning).
   - Verify chunking logic.
   - Verify integration with `EmbeddingService` and `VectorBackend` (Mocks).
   - Verify raw content upload to `BlobStorage`.

2. **DiscoveryServices**
   - `CityScrapersDiscoveryService`: Verify `subprocess` execution and JSON parsing.
   - `MunicodeDiscoveryService`: Verify Playwright interaction (Mocked).

## Test Strategy
- Use `pytest` + `pytest-asyncio`.
- Use `unittest.mock` (or `pytest-mock`) for external dependencies (Supabase, OpenAI, Playwright).

## Implementation
### `backend/tests/test_ingestion_service.py`
- `test_process_raw_scrape_success`: Happy path.
- `test_process_raw_scrape_with_blob_storage`: Verify `upload` call.
- `test_extract_text_html`: Verify cleaning regex.
- `test_chunk_text`: Verify overlap and size.

### `backend/tests/test_discovery_services.py`
- `test_city_scrapers_parsing`: Mock `json.load` and `subprocess`.
