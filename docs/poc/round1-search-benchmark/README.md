# Round 1 Search Benchmark (bd-vho5t.1)

Scope in this folder is benchmark-only:
- current baseline discovery lane
- SearXNG lane
- deterministic local-government matrix (`4 jurisdictions x 3 intents`)

Out of scope:
- production migration
- Round 2 (YaCy / Scrapy+Meilisearch)

## Matrix

Deterministic matrix file:

- `docs/poc/round1-search-benchmark/matrix.local_government_round1.json`

The matrix includes:
- intents: `agenda`, `minutes`, `ordinance`
- jurisdictions:
  - `San Jose, CA` (known hard case)
  - `Oakland, CA`
  - `Santa Clara County, CA`
  - `Long Beach, CA`

## Run Commands

Live benchmark:

```bash
cd backend
poetry run python scripts/verification/run_round1_search_benchmark.py --mode live
```

Live mode dependency:
- `SEARXNG_BASE_URL` must be set for the SearXNG lane.

If `SEARXNG_BASE_URL` is missing, the harness fails closed with:
- benchmark state `benchmark_harness_ready_live_run_blocked`
- blocker `SEARXNG_BASE_URL`

Fixture-backed run:

```bash
cd backend
poetry run python scripts/verification/run_round1_search_benchmark.py \
  --mode fixture \
  --fixture-file scripts/verification/fixtures/round1_search_benchmark_fixture.json
```

## Artifacts

Each run writes both machine-readable and human-readable outputs under:

- `docs/poc/round1-search-benchmark/artifacts/`

Files:
- `round1_search_benchmark_<timestamp>.json`
- `round1_search_benchmark_<timestamp>.md`

Metrics reported per lane:
- `empty_result_rate`
- `non_empty_result_rate`
- `official_source_top5_rate`
- `useful_url_yield`
- `unique_useful_url_yield`
- `artifact_vs_portal_rate`
- `duplicate_url_rate`
- `median_latency_ms`
- `hard_failure_rate`

The JSON report also includes representative samples and failure-mode buckets.
