# Research Fixtures Contract

This directory contains replayable research fixtures for the golden bill corpus (bd-bkco.2).

## Purpose

Snapshot and persist replayable fixtures for:
1. **Raw scrape text** - Bill text scraped from official sources
2. **Retrieved chunks** - RAG retrieval results from the vector store
3. **Web search results** - External web search responses

This enables the test suite to separate pipeline logic regressions from search volatility.

## Fixture Schema

Each fixture file (`{bill_id}.json`) follows this contract:

```json
{
  "fixture_version": "1.0",
  "feature_key": "bd-bkco.2",
  "bill_id": "us-hr-1319-2021",
  "captured_at": "2026-03-28T12:00:00Z",
  "capture_mode": "live|synthetic",
  "scraped_bill_text": {
    "bill_number": "H.R. 1319",
    "title": "American Rescue Plan Act of 2021",
    "text": "...",
    "introduced_date": "2021-02-24",
    "status": "Enacted",
    "source_url": "https://..."
  },
  "rag_chunks": [
    {
      "chunk_id": "...",
      "content": "...",
      "score": 0.85,
      "metadata": {
        "source_url": "...",
        "jurisdiction": "federal-us",
        "content_type": "bill_text"
      }
    }
  ],
  "web_sources": [
    {
      "url": "https://...",
      "title": "...",
      "snippet": "...",
      "content": null
    }
  ],
  "sufficiency_breakdown": {
    "source_text_present": true,
    "rag_chunks_retrieved": 5,
    "web_research_sources_found": 12,
    "fiscal_notes_detected": true,
    "bill_text_chunks": 3
  }
}
```

## Field Requirements

| Field | Required | Description |
|-------|----------|-------------|
| `fixture_version` | Yes | Schema version (current: "1.0") |
| `feature_key` | Yes | Must be "bd-bkco.2" |
| `bill_id` | Yes | Canonical bill identifier matching manifest |
| `captured_at` | Yes | ISO 8601 timestamp of fixture capture |
| `capture_mode` | Yes | "live" (from real API) or "synthetic" (curated) |
| `scraped_bill_text` | Yes* | Bill text data (can be empty object for control bills) |
| `rag_chunks` | Yes | Array of retrieved chunks (can be empty) |
| `web_sources` | Yes | Array of web search results (can be empty) |
| `sufficiency_breakdown` | Yes | Evidence sufficiency metrics |

* `scraped_bill_text` requires: `bill_number`, `title`, `text`

## Replay Mechanism

The `ReplayableResearchFixture` class in `replay_fixtures.py` provides:

```python
from backend.scripts.verification.fixtures.research_fixtures import (
    ReplayableResearchFixture,
    FixtureStore,
)

# Load a single fixture
fixture = ReplayableResearchFixture.load("us-hr-1319-2021")

# Get scraped bill text
bill_text = fixture.get_bill_text()

# Get RAG chunks as RetrievedChunk objects
chunks = fixture.get_rag_chunks()

# Get web sources as dict list
web_sources = fixture.get_web_sources()

# Get full research result
result = fixture.to_research_result()

# Load all fixtures for corpus
store = FixtureStore.load_corpus()
for bill_id, fixture in store.fixtures.items():
    ...
```

## Validation

Run the validator:

```bash
python backend/scripts/verification/validate_research_fixtures.py
```

The validator checks:
- Required fields present
- Fixture version compatibility
- Bill ID matches manifest entries
- `scraped_bill_text` has required subfields
- Capture mode is valid ("live" or "synthetic")
- Arrays are properly typed

## Capture Modes

- **live**: Captured from real API calls during pipeline execution
- **synthetic**: Curated minimal fixtures for control/fail-closed bills

## Prefix vs Full-Run Evaluation

### Prefix Evaluation (Fast)
Uses only `scraped_bill_text` and first 3 `rag_chunks` for quick validation.

### Full-Run Evaluation
Uses all fixture data including all `rag_chunks` and `web_sources` for comprehensive testing.
