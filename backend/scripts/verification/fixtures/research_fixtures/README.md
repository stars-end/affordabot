# Research Fixtures Contract

This directory contains the checked-in replayable research fixture subset for the golden bill corpus (bd-bkco.2).

## Purpose

Snapshot and persist replayable fixtures for:
1. **Raw scrape text** - Bill text used by replay tests
2. **Retrieved chunks** - RAG payloads fed to downstream stages
3. **Web search results** - External search payloads used by replay tests

Current checked-in fixtures are intentionally narrow:
- they are synthetic control/adversarial fixtures only
- they support deterministic replay of control paths and fixture-loading contracts
- they do **not** prove that the pipeline is insulated from live search volatility

Only fixtures captured from live pipeline outputs may claim search-volatility separation.
The collection-level scope for this directory is fixed in `../research_fixture_set_metadata.json`.

## Fixture Schema

Each fixture file (`{bill_id}.json`) follows this contract:

```json
{
  "fixture_version": "1.0",
  "feature_key": "bd-bkco.2",
  "bill_id": "ca-acr-117-2024",
  "captured_at": "2026-03-28T12:00:00Z",
  "capture_mode": "live|synthetic",
  "fixture_provenance": {
    "provenance_type": "live_capture|synthetic_control",
    "search_volatility_separated": false,
    "valid_for": [
      "control_path_replay"
    ],
    "limitations": [
      "not_live_capture",
      "not_search_volatility_proof",
      "not_quantitative_ground_truth"
    ]
  },
  "scraped_bill_text": {
    "bill_number": "ACR 117",
    "title": "Ceremonial California Assembly Concurrent Resolution",
    "text": "...",
    "introduced_date": "2024-03-15",
    "status": "Adopted",
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
| `capture_mode` | Yes | "live" (from real API) or "synthetic" (curated control fixture) |
| `fixture_provenance` | Yes | Machine-checkable provenance and allowed guarantees |
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
fixture = ReplayableResearchFixture.load("ca-acr-117-2024")

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
- Provenance is explicit and machine-checkable
- Synthetic fixtures are limited to explicit fail-closed/adversarial controls
- Synthetic fixtures carry explicit non-live / non-volatility-proof limitations
- Arrays are properly typed

## Capture Modes

- **live**: Captured from real API calls during pipeline execution. Only these fixtures may set `fixture_provenance.search_volatility_separated=true`.
- **synthetic**: Curated control/adversarial fixtures only. They are valid for deterministic replay of control paths and schema checks, not for quantitative regression claims.

## Current Corpus Status

At the moment, the checked-in fixture set is a control-only bootstrap:
- fail-closed controls
- adversarial controls

Positive quantitative bills remain in the corpus manifest, but they are intentionally **not** represented as checked-in synthetic research fixtures. They must be added later as live captures if we want truthful search-volatility or live-retrieval regression claims.

This means `bd-bkco.2` currently bootstraps the fixture contract and deterministic control-path replay. It does **not** claim that the repo already contains a frozen research fixture corpus for every golden bill.

## Prefix vs Full-Run Evaluation

### Prefix Evaluation (Fast)
Uses only `scraped_bill_text` and first 3 `rag_chunks` for quick control-path validation.

### Full-Run Evaluation
Uses all fixture data including all `rag_chunks` and `web_sources` for deterministic replay of the fixture payload itself. For synthetic fixtures, this is still not evidence of live search behavior.
