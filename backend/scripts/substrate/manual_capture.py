#!/usr/bin/env python3
"""Manual substrate capture with binary-safe persistence and content classes.

This script captures official municipal documents into `raw_scrapes` while
making content handling explicit:
- text-like responses are stored as UTF-8 text in `data.content`
- binary responses are uploaded to durable blob storage and referenced from
  `raw_scrapes.storage_uri` and `data.content_storage_uri`

The goal is durable raw capture first; ingestion/chunking is optional and is
only attempted for text-like content classes.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import html
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from db.postgres_client import PostgresDB
from services.ingestion_service import IngestionService
from services.pdf_markdown import PDFMarkdownError
from services.pdf_markdown import extract_pdf_markdown
from services.storage.s3_storage import S3Storage
from services.substrate_promotion import apply_promotion_decision
from services.substrate_promotion import evaluate_rules
from services.substrate_promotion import seed_capture_promotion_metadata
from services.vector_backend_factory import create_vector_backend


DEFAULT_SUBSTRATE_VERSION = "poc-v1"
DEFAULT_PROMOTION_STATE = "captured_candidate"
EMBEDDING_DIMENSIONS = 4096


@dataclass(frozen=True)
class SubstrateDefaults:
    document_type: str
    trust_tier: str
    capture_method: str
    canonical_url: str
    content_class: str
    promotion_state: str = DEFAULT_PROMOTION_STATE
    substrate_version: str = DEFAULT_SUBSTRATE_VERSION


TEXT_CONTENT_CLASSES = {"html_text", "plain_text", "json_text"}


def normalize_canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    cleaned = parts._replace(fragment="")
    return urlunsplit(cleaned)


def parse_metadata_blob(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def detect_content_class(content_type: str) -> str:
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype in {"text/html", "application/xhtml+xml"}:
        return "html_text"
    if ctype in {"text/plain"}:
        return "plain_text"
    if ctype in {"application/json", "application/ld+json"}:
        return "json_text"
    if ctype == "application/pdf":
        return "pdf_binary"
    return "binary_blob"


def extract_title_from_html(raw_html: str, fallback_url: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
    if match:
        title = re.sub(r"\s+", " ", html.unescape(match.group(1))).strip()
        if title:
            return title
    return fallback_url


def extract_preview_text(raw_html: str, limit: int = 500) -> str:
    text = re.sub(r"<script.*?</script>", " ", raw_html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return text[:limit]


def build_source_metadata(
    *,
    defaults: SubstrateDefaults,
    source_name: str,
    source_type: str,
) -> dict[str, Any]:
    seeded = {
        "substrate_version": defaults.substrate_version,
        "canonical_url": defaults.canonical_url,
        "document_type": defaults.document_type,
        "source_type": source_type,
        "content_class": defaults.content_class,
        "trust_tier": defaults.trust_tier,
        "capture_method": defaults.capture_method,
        "promotion_state": defaults.promotion_state,
        "active": True,
        "poc": True,
        "poc_source_name": source_name,
    }
    return seed_capture_promotion_metadata(
        metadata=seeded,
        canonical_url=defaults.canonical_url,
        trust_tier=defaults.trust_tier,
    )


def build_raw_metadata(
    *,
    defaults: SubstrateDefaults,
    source_name: str,
    source_type: str,
    title: str,
    response_content_type: str,
) -> dict[str, Any]:
    seeded = {
        "substrate_version": defaults.substrate_version,
        "canonical_url": defaults.canonical_url,
        "document_type": defaults.document_type,
        "source_type": source_type,
        "content_class": defaults.content_class,
        "trust_tier": defaults.trust_tier,
        "capture_method": defaults.capture_method,
        "promotion_state": defaults.promotion_state,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "raw_capture_mode": "manual_poc",
        "source_name": source_name,
        "title": title,
        "response_content_type": response_content_type,
        "ingestion_truth": {
            "stage": "raw_captured",
            "raw_captured": True,
            "blob_stored": False,
            "storage_uri_present": False,
            "parsed": False,
            "chunked": False,
            "embedded": False,
            "vector_upserted": False,
            "retrievable": False,
            "ingest_attempted": False,
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    seeded = seed_capture_promotion_metadata(
        metadata=seeded,
        canonical_url=defaults.canonical_url,
        trust_tier=defaults.trust_tier,
    )
    return apply_promotion_decision(
        metadata=seeded,
        decision=evaluate_rules(seeded),
        canonical_url=defaults.canonical_url,
    )


def build_data_payload(
    *,
    content_class: str,
    content_bytes: bytes,
    title: str,
    canonical_url: str,
) -> tuple[dict[str, Any], str]:
    if content_class in TEXT_CONTENT_CLASSES:
        text_content = content_bytes.decode("utf-8", errors="replace")
        preview = extract_preview_text(text_content)
        payload = {
            "content": text_content,
            "title": title,
            "canonical_url": canonical_url,
            "preview_text": preview,
        }
        return payload, preview

    preview = f"[binary:{content_class}] {title}"
    payload = {
        "content_storage": "external_blob",
        "byte_length": len(content_bytes),
        "title": title,
        "canonical_url": canonical_url,
        "preview_text": preview,
    }
    return payload, preview


def extension_for_content_type(content_type: str) -> str:
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype == "application/pdf":
        return "pdf"
    if ctype in {"text/html", "application/xhtml+xml"}:
        return "html"
    if ctype in {"application/json", "application/ld+json"}:
        return "json"
    if ctype == "text/plain":
        return "txt"
    return "bin"


def _build_ingestion_truth_update(
    *,
    stage: str,
    ingest_attempted: bool,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "stage": stage,
        "ingest_attempted": ingest_attempted,
        "last_updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        payload.update(extra)
    return payload


def extract_pdf_markdown_payload(content_bytes: bytes) -> tuple[str | None, str | None, str | None]:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp_file:
        tmp_file.write(content_bytes)
        tmp_file.flush()
        try:
            result = extract_pdf_markdown(tmp_file.name)
        except PDFMarkdownError as exc:
            return None, None, str(exc)
    return result.markdown, result.extractor, None


async def upload_binary_artifact(
    *,
    source_id: str,
    content_hash: str,
    content_type: str,
    content_bytes: bytes,
) -> str:
    now = datetime.now(timezone.utc)
    ext = extension_for_content_type(content_type)
    path = f"{source_id}/{now.year}/{now.month}/{content_hash}.{ext}"
    storage = S3Storage()
    return await storage.upload(path, content_bytes)


async def build_embedding_service() -> Any:
    if os.environ.get("OPENROUTER_API_KEY"):
        from llm_common.embeddings.openai import OpenAIEmbeddingService

        return OpenAIEmbeddingService(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            model="qwen/qwen3-embedding-8b",
            dimensions=EMBEDDING_DIMENSIONS,
        )

    class MockEmbeddingService:
        async def embed_query(self, text: str) -> list[float]:
            return [0.1] * EMBEDDING_DIMENSIONS

        async def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[0.1] * EMBEDDING_DIMENSIONS for _ in texts]

    return MockEmbeddingService()


async def ensure_source(
    db: PostgresDB,
    *,
    jurisdiction_name: str,
    jurisdiction_type: str,
    source_name: str,
    source_type: str,
    canonical_url: str,
    source_metadata: dict[str, Any],
) -> tuple[str, str]:
    jurisdiction_id = await db.get_or_create_jurisdiction(jurisdiction_name, jurisdiction_type)
    if not jurisdiction_id:
        raise RuntimeError("Failed to resolve jurisdiction")

    source_id = await db.get_or_create_source(
        jurisdiction_id,
        source_name,
        source_type,
        url=canonical_url,
    )
    if not source_id:
        raise RuntimeError("Failed to resolve source")

    existing = await db.get_source(source_id) or {}
    merged = {**parse_metadata_blob(existing.get("metadata")), **source_metadata}
    await db.update_source(
        source_id,
        {
            "metadata": json.dumps(merged),
            "source_method": "manual",
            "handler": "substrate_manual_capture",
            "scrape_url": canonical_url,
            "status": "active",
        },
    )
    return jurisdiction_id, source_id


async def capture_document(args: argparse.Namespace) -> dict[str, Any]:
    canonical_url = normalize_canonical_url(args.url)

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        response = await client.get(canonical_url)
        response.raise_for_status()
        content_bytes = response.content
        content_type = response.headers.get("content-type", "application/octet-stream").split(";")[
            0
        ].strip()

    content_class = detect_content_class(content_type)
    defaults = SubstrateDefaults(
        document_type=args.document_type,
        trust_tier=args.trust_tier,
        capture_method=args.capture_method,
        canonical_url=canonical_url,
        content_class=content_class,
    )

    title = args.title
    if not title:
        if content_class == "html_text":
            html_text = content_bytes.decode("utf-8", errors="replace")
            title = extract_title_from_html(html_text, canonical_url)
        else:
            title = canonical_url

    data_payload, preview = build_data_payload(
        content_class=content_class,
        content_bytes=content_bytes,
        title=title,
        canonical_url=canonical_url,
    )

    db = PostgresDB()
    try:
        source_metadata = build_source_metadata(
            defaults=defaults,
            source_name=args.source_name,
            source_type=args.source_type,
        )
        jurisdiction_id, source_id = await ensure_source(
            db,
            jurisdiction_name=args.jurisdiction_name,
            jurisdiction_type=args.jurisdiction_type,
            source_name=args.source_name,
            source_type=args.source_type,
            canonical_url=canonical_url,
            source_metadata=source_metadata,
        )

        raw_metadata = build_raw_metadata(
            defaults=defaults,
            source_name=args.source_name,
            source_type=args.source_type,
            title=title,
            response_content_type=content_type,
        )
        storage_uri = None
        content_hash = hashlib.sha256(content_bytes).hexdigest()
        if content_class not in TEXT_CONTENT_CLASSES:
            storage_uri = await upload_binary_artifact(
                source_id=source_id,
                content_hash=content_hash,
                content_type=content_type,
                content_bytes=content_bytes,
            )
            data_payload["content_storage_uri"] = storage_uri
            if isinstance(raw_metadata.get("ingestion_truth"), dict):
                raw_metadata["ingestion_truth"]["blob_stored"] = True
                raw_metadata["ingestion_truth"]["storage_uri_present"] = True
                raw_metadata["ingestion_truth"]["last_updated_at"] = datetime.now(
                    timezone.utc
                ).isoformat()

        scrape_record = {
            "source_id": source_id,
            "url": canonical_url,
            "content_hash": content_hash,
            "content_type": content_type,
            "data": data_payload,
            "metadata": raw_metadata,
            "storage_uri": storage_uri,
        }
        scrape_id = await db.create_raw_scrape(scrape_record)
        if not scrape_id:
            raise RuntimeError("Failed to create raw scrape")

        chunk_count = 0
        ingest_attempted = False
        ingest_skipped_reason = None
        scrape_row = await db._fetchrow("SELECT * FROM raw_scrapes WHERE id = $1", scrape_id)
        document_id = None
        storage_uri = None
        error_message = None

        if args.ingest:
            prepared_text_like = content_class in TEXT_CONTENT_CLASSES
            if content_class == "pdf_binary":
                extracted_markdown, extractor_name, extractor_error = extract_pdf_markdown_payload(
                    content_bytes
                )
                existing_meta = parse_metadata_blob(scrape_row.get("metadata")) if scrape_row else {}
                truth = parse_metadata_blob(existing_meta.get("ingestion_truth"))
                if extracted_markdown:
                    data_payload["parsed_markdown"] = extracted_markdown
                    data_payload["pdf_markdown_extractor"] = extractor_name
                    truth.update(
                        {
                            "parsed": True,
                            "parse_method": extractor_name,
                            "parse_error": None,
                            "stage": "parsed_pdf_markdown",
                            "last_updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    existing_meta["ingestion_truth"] = truth
                    await db._execute(
                        "UPDATE raw_scrapes SET data = $1, metadata = $2 WHERE id = $3",
                        json.dumps(data_payload),
                        json.dumps(existing_meta),
                        scrape_id,
                    )
                    scrape_row = await db._fetchrow("SELECT * FROM raw_scrapes WHERE id = $1", scrape_id)
                    prepared_text_like = True
                else:
                    truth.update(
                        {
                            "parsed": False,
                            "parse_method": "pdf_markdown",
                            "parse_error": extractor_error,
                            "stage": "parse_failed_pdf",
                            "last_updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    existing_meta["ingestion_truth"] = truth
                    await db._execute(
                        "UPDATE raw_scrapes SET metadata = $1, error_message = $2 WHERE id = $3",
                        json.dumps(existing_meta),
                        extractor_error,
                        scrape_id,
                    )
                    scrape_row = await db._fetchrow("SELECT * FROM raw_scrapes WHERE id = $1", scrape_id)

            if prepared_text_like:
                ingest_attempted = True
                existing_meta = parse_metadata_blob(scrape_row.get("metadata")) if scrape_row else {}
                truth = parse_metadata_blob(existing_meta.get("ingestion_truth"))
                truth.update(_build_ingestion_truth_update(stage="ingest_started", ingest_attempted=True))
                existing_meta["ingestion_truth"] = truth
                await db._execute(
                    "UPDATE raw_scrapes SET metadata = $1 WHERE id = $2",
                    json.dumps(existing_meta),
                    scrape_id,
                )
                embedding_service = await build_embedding_service()

                async def embed_fn(text: str) -> list[float]:
                    return await embedding_service.embed_query(text)

                vector_backend = create_vector_backend(
                    postgres_client=db,
                    embedding_fn=embed_fn,
                )
                ingestion_service = IngestionService(
                    postgres_client=db,
                    vector_backend=vector_backend,
                    embedding_service=embedding_service,
                    storage_backend=S3Storage(),
                )
                chunk_count = await ingestion_service.process_raw_scrape(scrape_id)
                scrape_row = await db._fetchrow("SELECT * FROM raw_scrapes WHERE id = $1", scrape_id)
            else:
                ingest_skipped_reason = f"content_class={content_class} is not text-like"
                existing_meta = parse_metadata_blob(scrape_row.get("metadata")) if scrape_row else {}
                truth = parse_metadata_blob(existing_meta.get("ingestion_truth"))
                truth.update(
                    _build_ingestion_truth_update(
                        stage="ingest_skipped_non_text",
                        ingest_attempted=False,
                        extra={"ingest_skipped_reason": ingest_skipped_reason},
                    )
                )
                existing_meta["ingestion_truth"] = truth
                await db._execute(
                    "UPDATE raw_scrapes SET metadata = $1 WHERE id = $2",
                    json.dumps(existing_meta),
                    scrape_id,
                )
                scrape_row = await db._fetchrow("SELECT * FROM raw_scrapes WHERE id = $1", scrape_id)

        # Re-evaluate rules after ingest state updates so promotion fields remain
        # machine-checkable on the final stored row.
        if scrape_row:
            existing_meta = parse_metadata_blob(scrape_row.get("metadata"))
            promoted = apply_promotion_decision(
                metadata=existing_meta,
                decision=evaluate_rules(existing_meta),
                canonical_url=canonical_url,
            )
            await db._execute(
                "UPDATE raw_scrapes SET metadata = $1 WHERE id = $2",
                json.dumps(promoted),
                scrape_id,
            )
            scrape_row = await db._fetchrow("SELECT * FROM raw_scrapes WHERE id = $1", scrape_id)

        if scrape_row:
            document_id = str(scrape_row.get("document_id")) if scrape_row.get("document_id") else None
            storage_uri = scrape_row.get("storage_uri")
            error_message = scrape_row.get("error_message")
        final_metadata = parse_metadata_blob(scrape_row.get("metadata")) if scrape_row else {}
        processed = bool(scrape_row.get("processed")) if scrape_row and scrape_row.get("processed") is not None else scrape_row.get("processed") if scrape_row else None
    finally:
        await db.close()

    return {
        "jurisdiction_id": jurisdiction_id,
        "source_id": source_id,
        "scrape_id": scrape_id,
        "document_id": document_id,
        "storage_uri": storage_uri,
        "chunk_count": chunk_count,
        "error_message": error_message,
        "content_type": content_type,
        "content_class": content_class,
        "ingest_attempted": ingest_attempted,
        "ingest_skipped_reason": ingest_skipped_reason,
        "defaults": asdict(defaults),
        "title": title,
        "preview_text": preview,
        "processed": processed,
        "raw_metadata": final_metadata,
        "source_metadata": source_metadata,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--jurisdiction-name", required=True)
    parser.add_argument("--jurisdiction-type", required=True, choices=("city", "county", "state"))
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--source-type", required=True)
    parser.add_argument("--document-type", required=True)
    parser.add_argument("--trust-tier", required=True)
    parser.add_argument("--capture-method", default="manual_http")
    parser.add_argument("--title")
    parser.add_argument("--ingest", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = asyncio.run(capture_document(args))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
