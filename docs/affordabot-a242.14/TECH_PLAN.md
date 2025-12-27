# affordabot-a242.14 — WebReaderTool (deep reading)

## Goal
Provide a robust “deep read” tool for agents that can extract readable text + metadata from URLs (beyond shallow search snippets).

## Approach
- Prefer a two-tier strategy:
  - Fast path: `trafilatura` (or similar) HTML → text extraction
  - Fallback: Playwright render + extraction for JS-heavy pages

## Acceptance Criteria
- Tool returns `{text, title, url, retrieved_at, content_hash}` plus optional `evidence` metadata.
- Has unit tests with fixture HTML.

