import pytest
from tests.utils.fake_supabase import FakeSupabaseClient
from services.source_service import SourceService, SourceCreate
from services.ingestion_service import IngestionService
from db.supabase_client import SupabaseDB
from unittest.mock import MagicMock, AsyncMock

@pytest.mark.asyncio
async def test_admin_source_flow():
    """
    Integration Test: Admin creates source -> Raw Scrape inserted -> Ingestion processes it.
    """
    # 1. Setup
    fake_db = FakeSupabaseClient()
    source_service = SourceService(fake_db)
    
    # 2. Create Source
    source_data = SourceCreate(
        jurisdiction_id="san-jose",
        url="http://example.com/meetings",
        type="meeting"
    )
    source = await source_service.create_source(source_data)
    
    assert source["id"] is not None
    assert len(fake_db.data_store["sources"]) == 1
    
    # 3. Simulate Scraper output (Raw Scrape)
    scrape_data = {
        "source_id": source["id"],
        "content_hash": "hash123",
        "content_type": "text/html",
        "data": "<html><body>Meeting Minutes</body></html>",
        "processed": None # Explicitly null
    }
    fake_db.table("raw_scrapes").insert(scrape_data).execute()
    
    # 4. Setup Ingestion Service
    mock_vector = AsyncMock()
    mock_embed = AsyncMock()
    # Mock embedding return (1 chunk -> 1 vector)
    mock_embed.embed_documents.return_value = [[0.1]*1536]
    
    ingestion_service = IngestionService(
        supabase_client=fake_db,
        vector_backend=mock_vector,
        embedding_service=mock_embed
    )
    
    # Fetch the scrape ID that was inserted
    scrapes = fake_db.table("raw_scrapes").select().execute().data
    scrape_id = scrapes[0]["id"]
    
    # 5. Run Ingestion
    count = await ingestion_service.process_raw_scrape(scrape_id)
    
    # 6. Verify
    assert count == 1 # 1 chunk created
    
    # Check raw_scrape is marked processed
    resp = fake_db.table("raw_scrapes").select().eq("id", scrape_id).single().execute()
    updated_scrape = resp.data
    assert updated_scrape["processed"] is True
    assert updated_scrape["document_id"] is not None
    
    # Check vector backend was called (stored in vector db)
    mock_vector.upsert.assert_called_once()

@pytest.mark.asyncio
async def test_db_client_storage_flow():
    """
    Integration Test: SupabaseDB logic for Jurisdiction/Legislation storage.
    """
    fake_db = FakeSupabaseClient()
    db_wrapper = SupabaseDB(client=fake_db)
    
    # 1. Get/Create Jurisdiction
    jur_id = await db_wrapper.get_or_create_jurisdiction("Test City", "city")
    assert jur_id is not None
    assert len(fake_db.data_store["jurisdictions"]) == 1
    assert fake_db.data_store["jurisdictions"][0]["name"] == "Test City"
    
    # 2. Idempotency Check (Get existing)
    jur_id_2 = await db_wrapper.get_or_create_jurisdiction("Test City", "city")
    assert jur_id == jur_id_2
    assert len(fake_db.data_store["jurisdictions"]) == 1
    
    # 3. Store Legislation (New)
    bill = {
        "bill_number": "B1",
        "title": "Bill 1",
        "text": "Text",
        "status": "active"
    }
    leg_id = await db_wrapper.store_legislation(jur_id, bill)
    assert leg_id is not None
    assert len(fake_db.data_store["legislation"]) == 1
    
    # 4. Update Legislation (Existing)
    bill["status"] = "passed"
    leg_id_update = await db_wrapper.store_legislation(jur_id, bill)
    assert leg_id == leg_id_update
    
    # Verify DB state
    rows = fake_db.data_store["legislation"]
    assert len(rows) == 1
    assert rows[0]["status"] == "passed"
    assert rows[0]["updated_at"] is not None
