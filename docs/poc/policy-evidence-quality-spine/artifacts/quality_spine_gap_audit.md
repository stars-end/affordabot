# Policy Evidence Quality Spine Gap Audit (`bd-3wefe.13`)

## Verdict

`retry_4_attempted_runtime_blocked`

The local deterministic quality loop should stop after retry-3. Retry-4 attempted the next meaningful live runtime proof and hit a concrete Railway-dev storage blocker. The P1 false-pass risks identified before retry-3 are fixed in the generated artifacts:

- `scraped/search` no longer passes on source presence alone.
- `storage/read-back` no longer claims real Postgres/MinIO proof from an in-memory harness.
- scorecard/report/ledger now share retry-3 attempt metadata.

The remaining gaps are live current-run proof gaps, not local data-quality scoring bugs:

- `storage/read-back`: needs real Postgres + MinIO proof for the current vertical package.
- `Windmill/orchestration`: needs current Windmill run/job ids linked to the current vertical package.
- `LLM narrative`: needs canonical analysis/LLM run ids linked to the current vertical package.

Retry-4 storage proof artifact:

- path: `artifacts/quality_spine_live_storage_probe.json`
- status: `blocked`
- blocker: `minio_write_or_readback_failed`
- error_class: `S3Error`
- summarized cause: `AccessDenied` for the configured `affordabot-artifacts` bucket

## Current Artifact State

- attempt: `bd-3wefe.13-retry-3`
- targeted_tweak: `strict_data_runtime_proof_fields`
- overall_verdict: `partial`
- failed_categories: `[]`
- not_proven_categories: `storage/read-back`, `Windmill/orchestration`, `LLM narrative`
- horizontal breadth: 6 artifacts, 3 jurisdictions, 3 mechanism families
- vertical package: `pkg-sj-parking-minimum-amendment`

## Findings

### [P1 Resolved] Artifact set is internally consistent

`data_runtime_evidence.json`, `quality_spine_scorecard.json`, `quality_spine_report.md`, and `retry_ledger.json` now reflect retry-3. The retry ledger records baseline, retry-1, retry-2, and retry-3 rather than presenting retry-2 as unexecuted.

### [P1 Resolved] `storage/read-back` no longer false-passes

The scorecard now marks storage as `not_proven` when the only proof is deterministic in-memory readback. This preserves the useful local invariant test while making clear that architecture lock still needs a real Postgres/MinIO proof.

Current status:

```text
storage/read-back = not_proven
details = Deterministic in-memory readback is proven, but non-memory Postgres/MinIO storage proof is not provided.
```

### [P1 Resolved] `scraped/search` is quality-gated

The scorecard now requires selected-artifact provider-quality evidence. The vertical San Jose package passes because the selected path is explicitly artifact-grade, official-domain, non-portal, and top-2.

Current status:

```text
scraped/search = pass
details = Selected artifact has provider-quality support (provider=private_searxng, status=strong, reason=artifact_top2).
```

### [P1 Remaining] Live current-run proof is still missing

The deterministic lane has reached the boundary of what it can prove locally. The existing storage verifier already documents that live Postgres/MinIO proof is blocked from the macOS runtime because Railway private DNS such as `pgvector.railway.internal` is not resolvable locally. The next meaningful proof needs to run inside the Railway dev network or through a deployed backend job/endpoint.

Required current-run proof:

- storage: real `policy_evidence_packages` row, real MinIO object write/readback, and pgvector marked derived-only for the current package.
- Windmill: current flow/job ids for the current package.
- LLM narrative: canonical analysis/LLM run ids for the current package.

## Retry Recommendation

Do not run another local fixture tweak. Retry-4 already confirmed that the next proof must fix or route around live runtime storage access. The next retry should be a live runtime proof after the MinIO dev runtime configuration is corrected:

`retry_5 = railway_dev_current_run_storage_windmill_llm_proof`

Acceptance should require real current-run ids/rows/objects. If live runtime cannot execute non-interactively, keep the categories as `not_proven` and treat the missing runtime path as the blocker for architecture lock.

## Architecture-Lock Implication

The evidence now supports this narrower claim:

> The proposed evidence-package shape can unify scraped and structured data into a source-bound economic handoff package for a direct-cost vertical case, and strict scoring can avoid false passes.

It does not yet support this stronger claim:

> The full Windmill + backend + Postgres/pgvector + MinIO + canonical LLM analysis pipeline is proven end-to-end for a current package.

That stronger claim requires retry-4 in Railway dev or equivalent live runtime.
