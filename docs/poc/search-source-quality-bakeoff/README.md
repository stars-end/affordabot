# Search Source Quality Bakeoff

Feature key: `bd-9qjof.8`
Purpose: Select MVP municipal discovery provider (`private_searxng` vs `tavily` vs `exa`) using evidence that predicts full pipeline usefulness, not just search API uptime.

## Why this exists

PR #433 proved Windmill/backend/storage mechanics. It also exposed discovery-quality failure: a source was selected that resolved to navigation/menu content, and Z.ai analysis correctly rejected insufficient evidence.

This bakeoff closes that gap.

## Inputs

- Query corpus: `docs/poc/search-source-quality-bakeoff/query-corpus.json`
- Scoring rubric: `docs/poc/search-source-quality-bakeoff/scoring-rubric.md`

## Required environment

- `SEARXNG_SEARCH_ENDPOINT` (example used in session: `https://searxng-railway-production-79aa.up.railway.app/search`)
- `TAVILY_API_KEY`
- `EXA_API_KEY`
- Exa requests must use User-Agent `affordabot-dev-bakeoff/1.0` to avoid Cloudflare 1010 observed with default Python UA.

SearXNG-only mode does not require `TAVILY_API_KEY` or `EXA_API_KEY`.

## SearXNG-only run

```bash
cd backend
poetry run python scripts/verification/verify_search_source_quality_bakeoff.py \
  --searxng-only \
  --query-file ../docs/poc/search-source-quality-bakeoff/query-corpus.json \
  --searx-endpoint "https://searxng-railway-production-79aa.up.railway.app/search"
```

This mode emits the same report files and adds a `searxng_fanout_health` section with:

- per-query result count and top result URL/title rows,
- per-query `unresponsive_engines` metadata (when returned by SearXNG),
- `health_verdict` (`healthy` / `degraded` / `unhealthy`),
- `raw_candidate_count`, `deduped_candidate_count`,
- deterministic class counts:
  - `final_artifact`
  - `portal_seed`
  - `likely_navigation`
  - `third_party_or_junk`,
- deterministic shortlist guidance (`recommended_shortlist_size`, `selected_shortlist`).

## Expected harness behavior

Implementation does:

1. Load `query-corpus.json`.
2. For each provider and query:
   - execute provider search (top-5 results),
   - compute per-query search-source score and disqualifier flags from rubric.
3. Aggregate provider-level metrics and `provider_score`.
4. Emit machine-readable and human-readable artifacts.
5. Report a best candidate separately from MVP readiness. A provider is not selected for rollout unless `mvp_ready` is true.

## Output artifact contract

Commit these under:

`docs/poc/search-source-quality-bakeoff/artifacts/`

Required files:

- `search_source_quality_bakeoff_report.json`
- `search_source_quality_bakeoff_report.md`

`search_source_quality_bakeoff_report.json` minimum shape:

```json
{
  "generated_at": "ISO8601",
  "feature_key": "bd-9qjof.8",
  "providers": ["searxng", "tavily", "exa"],
  "provider_summary": [
    {
      "provider": "searxng",
      "provider_score": 0,
      "eligible_for_mvp": false,
      "query_success_rate_percent": 0,
      "median_query_score": 0,
      "reader_ready_rate_percent": 0,
      "official_domain_hit_rate_percent": 0,
      "error_rate": 0,
      "rate_limit_rate": 0,
      "p90_latency_ms": 0,
      "failures": []
    }
  ],
  "recommendation": {
    "provider": "tavily",
    "mvp_ready": false,
    "reason": "no_provider_meets_mvp_threshold_best_candidate_only",
    "action": "do_not_lock_provider_run_full_reader_gate_or_tune_corpus"
  }
}
```

## Recommendation logic

Use thresholds from `docs/poc/search-source-quality-bakeoff/scoring-rubric.md`.

Decision outputs:

- `SELECT_PROVIDER_FOR_MVP`
- `NO_PROVIDER_PASSES_RETRY_WITH_CORPUS_TUNING`

Selection is valid only if:

- all MVP thresholds pass, and
- no repeated disqualifier pattern on San Jose queries (`sj-001` to `sj-006`).

The April 13, 2026 live bakeoff produced a best-candidate result, not an MVP selection:

- Private SearXNG, Tavily, and Exa all returned successful HTTP responses across the corpus.
- Tavily had the highest weighted provider score in the final run.
- No provider met the MVP threshold because reader-readiness remained below the required rate.
- Exa required the explicit `affordabot-dev-bakeoff/1.0` User-Agent; default Python user-agent requests were blocked during smoke testing.

## Mandatory next gate after winner selection

Run full Windmill live gate using the selected provider and commit:

- updated San Jose live gate report artifacts,
- explicit evidence that Z.ai analysis is based on official municipal source content (not nav-shell content),
- persisted provenance chain verification across search -> reader -> analysis.

Only after this gate passes should we lock provider architecture for rollout. The current artifact supports a narrow next step: run the full San Jose reader/analysis gate with Tavily as the first candidate and Exa/private SearXNG as fallback comparison lanes.

## Non-goals for this doc set

- No production backend provider SDK changes here.
- No provider SDK design here.
- No production rollout policy here.
