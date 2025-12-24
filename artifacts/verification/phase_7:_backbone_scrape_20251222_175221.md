# ✅ Phase 7: Backbone Scrape

**Captured**: 2025-12-22T17:52:21.966469
**Status**: SUCCESS

## Output

```
   Running Scrapy spiders...
   Exit code: 0
fordabot-artifacts?location='): Retry(total=0, connect=None, read=None, redirect=None, status=None)
2025-12-22 17:52:21,750 - WARNING - Retrying (Retry(total=0, connect=None, read=None, redirect=None, status=None)) after connection broken by 'NameResolutionError("HTTPConnection(host='bucket.railway.internal', port=9000): Failed to resolve 'bucket.railway.internal' ([Errno -2] Name or service not known)")': /affordabot-artifacts?location=
2025-12-22 17:52:21 [urllib3.connectionpool] WARNING: Retrying (Retry(total=0, connect=None, read=None, redirect=None, status=None)) after connection broken by 'NameResolutionError("HTTPConnection(host='bucket.railway.internal', port=9000): Failed to resolve 'bucket.railway.internal' ([Errno -2] Name or service not known)")': /affordabot-artifacts?location=
2025-12-22 17:52:21,751 - DEBUG - Starting new HTTP connection (6): bucket.railway.internal:9000
2025-12-22 17:52:21,777 - ERROR - Failed to ensure bucket exists (DNS or Connection issue): HTTPConnectionPool(host='bucket.railway.internal', port=9000): Max retries exceeded with url: /affordabot-artifacts?location= (Caused by NameResolutionError("HTTPConnection(host='bucket.railway.internal', port=9000): Failed to resolve 'bucket.railway.internal' ([Errno -2] Name or service not known)"))
2025-12-22 17:52:21 [services.storage.s3_storage] ERROR: Failed to ensure bucket exists (DNS or Connection issue): HTTPConnectionPool(host='bucket.railway.internal', port=9000): Max retries exceeded with url: /affordabot-artifacts?location= (Caused by NameResolutionError("HTTPConnection(host='bucket.railway.internal', port=9000): Failed to resolve 'bucket.railway.internal' ([Errno -2] Name or service not known)"))
2025-12-22 17:52:21,777 - INFO - 🍽️  Ingestion Complete. Created 0 chunks.
2025-12-22 17:52:21 [rag_cron] INFO: 🍽️  Ingestion Complete. Created 0 chunks.
2025-12-22 17:52:21,777 - INFO - 🏁 Complete. Scraped 0 items: {}
2025-12-22 17:52:21 [rag_cron] INFO: 🏁 Complete. Scraped 0 items: {}

```
