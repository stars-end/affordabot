# Substrate Defaults POC (bd-sc6o.1)

## Scope

This task hardens manual municipal capture for raw substrate durability:

- explicit `content_class` classification
- binary-safe raw persistence (for example, agenda PDFs)
- text-only ingestion attempt policy

Out of scope in this task:

- staged ingestion truth model (`bd-sc6o.2`)
- promotion-gate policy (`bd-sc6o.3`)

## Active Contract

Manual capture writes substrate metadata into existing schema (`sources.metadata`
and `raw_scrapes.metadata`) with:

- `canonical_url`
- `document_type`
- `source_type`
- `content_class`
- `trust_tier`
- `capture_method`
- `promotion_state`
- `substrate_version`

## Content Class Rules

- `html_text`: `text/html`, `application/xhtml+xml`
- `plain_text`: `text/plain`
- `json_text`: `application/json`, `application/ld+json`
- `pdf_binary`: `application/pdf`
- `binary_blob`: everything else

## Binary Safety Rule

For non-text content classes, raw payload is stored as:

- `data.content_base64`
- `data.content_encoding = "base64"`
- `data.byte_length`

Text payloads continue to use:

- `data.content` (UTF-8 text)

## Ingestion Rule

`--ingest` is attempted only for text-like classes (`html_text`, `plain_text`,
`json_text`). Binary classes are still durably captured but ingestion is
skipped with an explicit reason in script output.
