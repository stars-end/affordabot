# Manual Audit: Cycle 37 Data Moat

Feature-Key: `bd-3wefe.13`

Artifacts:
- `artifacts/live_cycle_37_windmill_domain_run.json`
- `live_cycle_37_windmill_domain_run.md`

Runtime identity:
- Windmill run: `bd-3wefe.13-live-cycle-37-20260417045750`
- Windmill job: `019d99cd-9d57-0018-67b9-0ef407fa3d3b`

## Verdict

`FAIL_DATA_MOAT__CLF_QUERY_FOUND_RELEVANT_CANDIDATES_BUT_MALFORMED_ATTACHMENT_CRASHED_BACKEND`

Cycle 37 changed the evaluation target from generic San Jose housing meeting minutes to the actual data-moat vertical: San Jose Commercial Linkage Fee rate/adoption evidence.

The query change worked directionally. The diagnostic bakeoff found relevant Legistar CLF legislation:

- Exa top URL: `https://sanjose.legistar.com/LegislationDetail.aspx?GUID=2F1C4308-5A4D-4A7B-8C4D-B4EECA92C889&ID=5463296&Options=&Search=`
- Tavily top URL: `https://sanjose.legistar.com/LegislationDetail.aspx?ID=5463296&GUID=2F1C4308-5A4D-4A7B-8C4D-B4EECA92C889&Options=&Search=`

The live product path still failed because the backend let a malformed/unreadable Legistar attachment PDF crash the run.

## What Passed

- The live gate now uses a CLF-specific source family:
  - `commercial_linkage_fee`
- The live gate now uses a CLF-specific query:
  - `San Jose Commercial Linkage Fee per square foot ordinance resolution fee schedule site:sanjose.legistar.com OR site:sanjoseca.gov`
- Diagnostic provider results found relevant official Legistar CLF candidates.
- Windmill orchestration invoked the backend endpoint with the expected scope:
  - `San Jose CA|commercial_linkage_fee|0`

## What Failed

- Backend endpoint returned HTTP 500.
- Failure class: `backend_endpoint_http_error`.
- Root exception:
  - `pypdf.errors.PdfReadError: Cannot find Root object in pdf`
- Stack location:
  - `StructuredSourceEnricher._probe_legistar_attachment_contents`
  - `StructuredSourceEnricher._extract_pdf_text`
  - `for page in reader.pages`
- No package was produced for row-level data audit.

This is a robustness failure, not an evidence-quality pass or fail. The data moat cannot depend on every official attachment being parseable. Government portals commonly include malformed PDFs, HTML error payloads with `.pdf` URLs, scans, or restricted files. The pipeline must preserve the attachment as a failed probe and continue with other candidates or fail closed with a structured blocker.

## Manual Data Assessment

Cycle 37 is a strong regression test for production robustness. It showed that the source-discovery query can reach the right class of official artifacts, but the attachment reader is not yet robust enough for a moat-grade ingestion system.

The correct behavior is:

- record the attachment as `pdf_parse_failed` / `attachment_pdf_parse_failed`;
- emit no economic rows from the malformed attachment;
- continue probing other high-value attachments when available; and
- if no readable authoritative rate rows remain, fail closed with a discovery/reader-quality blocker.

The implementation wave following this cycle added stable PDF parse error classification and explicit tests for page-iteration and page-extraction failures.

## Required Next Wave

1. Deploy the PDF fail-closed patch.
2. Rerun the CLF-specific live gate.
3. Confirm malformed PDFs no longer crash the backend.
4. Manually inspect whether the resulting package contains:
   - authoritative official San Jose CLF evidence;
   - accurate per-square-foot fee rows, or a clear no-row fail-closed state;
   - no annual-report/revenue dollars mislabeled as rates;
   - source provenance adequate for economic analysis.

## Stop Condition For This Vertical

The next cycle must produce a package or a structured product-quality blocker. A backend 500 from an unreadable government attachment is not acceptable moat infrastructure.
