# Document Ingestion and Chunking Service

Implement the ingestion service that takes raw scraped documents and converts them into overlapping text chunks ready for embedding and vector storage.

## Capabilities

### Text chunking with overlap

- Given a document with text longer than `chunk_size`, the service splits it into multiple chunks where each chunk is at most `chunk_size` characters [@test](./tests/test_chunk_size.py)
- Adjacent chunks overlap by `chunk_overlap` characters so no context is lost at boundaries [@test](./tests/test_chunk_overlap.py)
- A document with text shorter than `chunk_size` produces exactly one chunk containing the full text [@test](./tests/test_single_chunk.py)
- `process_raw_scrape(scrape_id)` returns an integer count of the chunks created [@test](./tests/test_chunk_count.py)

## Implementation

[@generates](./src/ingestion_service.py)

## API

```python { #api }
from typing import List

class IngestionService:
    chunk_size: int
    chunk_overlap: int

    def __init__(
        self,
        postgres_client,
        vector_backend=None,
        embedding_service=None,
        storage_backend=None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> None: ...

    async def process_raw_scrape(self, scrape_id: str) -> int:
        """Process a single raw scrape into embedded chunks. Returns chunk count."""
        ...

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks of chunk_size with chunk_overlap overlap."""
        ...
```

## Dependencies { .dependencies }

### affordabot { .dependency }

Provides the `IngestionService` interface, `RetrievalBackend`, and `EmbeddingService` abstractions used to store and embed document chunks.

[@satisfied-by](affordabot)
