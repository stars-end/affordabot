# Path A Storage Snapshots

## First Run Snapshot

```json
{
  "object_store": {
    "keys": [
      "documents/sanjoseca-gov-your-government-departments-offices-city-clerk-city-council-meetings/reader/52e6d8a43914d77c.md",
      "idempotency/san-jose-ca:meeting_minutes:2026-04-12/analysis/69e1e31c34f41ea6.json",
      "idempotency/san-jose-ca:meeting_minutes:2026-04-12/search/ad52464ef535c48b.json"
    ],
    "object_count": 3
  },
  "relational_store": {
    "analysis_count": 1,
    "document_count": 1,
    "search_snapshot_count": 1
  },
  "vector_store": {
    "chunk_count": 1,
    "chunk_ids": [
      "sanjoseca.gov/your-government/departments-offices/city-clerk/city-council-meetings::chunk-0::712bf03ddc3f"
    ]
  }
}
```

## Rerun Snapshot

```json
{
  "object_store": {
    "keys": [
      "documents/sanjoseca-gov-your-government-departments-offices-city-clerk-city-council-meetings/reader/52e6d8a43914d77c.md",
      "idempotency/san-jose-ca:meeting_minutes:2026-04-12/analysis/69e1e31c34f41ea6.json",
      "idempotency/san-jose-ca:meeting_minutes:2026-04-12/search/ad52464ef535c48b.json"
    ],
    "object_count": 3
  },
  "relational_store": {
    "analysis_count": 1,
    "document_count": 1,
    "search_snapshot_count": 1
  },
  "vector_store": {
    "chunk_count": 1,
    "chunk_ids": [
      "sanjoseca.gov/your-government/departments-offices/city-clerk/city-council-meetings::chunk-0::712bf03ddc3f"
    ]
  }
}
```
