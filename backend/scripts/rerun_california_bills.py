#!/usr/bin/env python3
"""
Re-run SB 277 and ACR 117 through the full truth pipeline.

Steps:
1. Chunk the scraped text into document_chunks with embeddings
2. Run the AnalysisPipeline (research → generate → review → persist)
3. Verify truth fields are persisted

Usage:
  PYTHONPATH=backend python backend/scripts/rerun_california_bills.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(BACKEND_ROOT))


def chunk_text(
    text: str, chunk_size: int = 1000, chunk_overlap: int = 200
) -> list[str]:
    """Simple text chunking."""
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # Find natural break
        if end < len(text):
            last_space = chunk.rfind(" ")
            if last_space > chunk_size * 0.5:
                end = start + last_space

        chunks.append(text[start:end].strip())
        start = end - chunk_overlap

        if start >= end:
            break

    return [c for c in chunks if c]


async def generate_embeddings(texts: list[str], api_key: str) -> list[list[float]]:
    """Generate embeddings using OpenRouter's OpenAI-compatible API."""
    import httpx

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/embeddings",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "qwen/qwen3-embedding-8b",
                "input": texts,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return [item["embedding"] for item in data["data"]]


async def ingest_bill(db, bill_number: str, bill_text: str, metadata: dict) -> int:
    """Chunk text, generate embeddings, store in document_chunks."""
    chunks = chunk_text(bill_text)
    if not chunks:
        print(f"  No chunks for {bill_number}")
        return 0

    print(f"  Chunked {bill_number} into {len(chunks)} chunks")

    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_key:
        print("  ERROR: OPENROUTER_API_KEY not set, cannot generate embeddings")
        return 0

    embeddings = await generate_embeddings(chunks, openrouter_key)
    print(f"  Generated {len(embeddings)} embeddings")

    document_id = str(uuid4())
    stored = 0

    for i, (chunk_text_val, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_id = str(uuid4())
        chunk_meta = {
            **metadata,
            "document_id": document_id,
            "chunk_index": i,
        }

        embedding_str = str(embedding)

        await db._execute(
            """INSERT INTO document_chunks (id, content, embedding, metadata, document_id)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT (id) DO UPDATE SET
                   content = EXCLUDED.content,
                   embedding = EXCLUDED.embedding,
                   metadata = EXCLUDED.metadata""",
            chunk_id,
            chunk_text_val,
            embedding_str,
            json.dumps(chunk_meta),
            document_id,
        )
        stored += 1

    # Note: raw_scrapes.document_id is not updated here to avoid UUID cast issues
    # with sources that have non-UUID jurisdiction_id (e.g. "web"). Chunks are
    # linked via metadata.bill_number instead.

    print(f"  Stored {stored} chunks, document_id={document_id[:20]}...")
    return stored


async def run_pipeline(db, bill_number: str, bill_text: str, jurisdiction: str):
    """Run the full analysis pipeline for a bill."""
    from llm_common.core import LLMConfig
    from llm_common.providers import ZaiClient, OpenRouterClient
    from llm_common.web_search import WebSearchClient
    from services.llm.orchestrator import AnalysisPipeline
    from services.retrieval.local_pgvector import LocalPgVectorBackend
    from llm_common.embeddings.openai import OpenAIEmbeddingService

    # Initialize LLM client
    llm_config = LLMConfig(
        api_key=os.getenv("ZAI_API_KEY"),
        provider="zai",
        default_model=os.getenv("LLM_MODEL_RESEARCH", "glm-4.7"),
    )
    llm_client = ZaiClient(llm_config)

    fallback_client = None
    if os.getenv("OPENROUTER_API_KEY"):
        or_config = LLMConfig(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            provider="openrouter",
            default_model="google/gemini-2.0-flash-exp",
        )
        fallback_client = OpenRouterClient(or_config)

    search_client = WebSearchClient(api_key=os.getenv("ZAI_API_KEY"))

    # Initialize retrieval backend
    retrieval_backend = None
    embedding_fn = None
    if os.getenv("OPENROUTER_API_KEY"):
        embed_svc = OpenAIEmbeddingService(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
            model="qwen/qwen3-embedding-8b",
            dimensions=4096,
        )
        retrieval_backend = LocalPgVectorBackend(
            table_name="document_chunks",
            postgres_client=db,
            embedding_fn=embed_svc.embed_query,
        )
        embedding_fn = embed_svc.embed_query

    pipeline = AnalysisPipeline(
        llm_client,
        search_client,
        db,
        fallback_client=fallback_client,
        retrieval_backend=retrieval_backend,
        embedding_fn=embedding_fn,
    )

    models = {
        "research": os.getenv("LLM_MODEL_RESEARCH", "glm-4.7"),
        "generate": os.getenv("LLM_MODEL_GENERATE", "glm-4.7"),
        "review": os.getenv("LLM_MODEL_REVIEW", "glm-4.7"),
    }

    print(f"  Running pipeline for {bill_number}...")
    result = await pipeline.run(
        bill_id=bill_number,
        bill_text=bill_text,
        jurisdiction=jurisdiction,
        models=models,
        trigger_source="manual",
    )

    print(f"  Pipeline complete for {bill_number}:")
    print(f"    sufficiency_state: {result.sufficiency_state}")
    print(f"    quantification_eligible: {result.quantification_eligible}")
    print(f"    total_impact_p50: {result.total_impact_p50}")
    print(f"    impacts: {len(result.impacts)}")
    print(f"    insufficiency_reason: {result.insufficiency_reason}")

    return result


async def verify_state(db, bill_number: str):
    """Verify the persisted state for a bill."""
    leg = await db._fetchrow(
        "SELECT bill_number, LENGTH(text_content) as text_len, analysis_status, "
        "sufficiency_state, insufficiency_reason, quantification_eligible, total_impact_p50 "
        "FROM legislation WHERE bill_number = $1",
        bill_number,
    )

    chunks = await db._fetchrow(
        "SELECT COUNT(*) as c FROM document_chunks WHERE metadata::json->>'bill_number' = $1",
        bill_number,
    )

    pipe = await db._fetchrow(
        "SELECT id, status, result FROM pipeline_runs WHERE bill_id = $1 ORDER BY started_at DESC LIMIT 1",
        bill_number,
    )

    pipe_result = {}
    if pipe:
        pipe_result = (
            json.loads(pipe["result"])
            if isinstance(pipe["result"], str)
            else (pipe["result"] or {})
        )

    print(f"\n  === {bill_number} Final State ===")
    print(f"  text_len: {leg['text_len'] if leg else 'N/A'}")
    print(f"  chunks: {chunks['c'] if chunks else 0}")
    print(f"  analysis_status: {leg['analysis_status'] if leg else 'N/A'}")
    print(f"  sufficiency_state: {leg['sufficiency_state'] if leg else 'N/A'}")
    print(
        f"  quantification_eligible: {leg['quantification_eligible'] if leg else 'N/A'}"
    )
    print(f"  total_impact_p50: {leg['total_impact_p50'] if leg else 'N/A'}")
    print(f"  insufficiency_reason: {leg['insufficiency_reason'] if leg else 'N/A'}")
    print(f"  pipeline source_text_present: {pipe_result.get('source_text_present')}")
    print(f"  pipeline retriever_invoked: {pipe_result.get('retriever_invoked')}")
    print(f"  pipeline rag_chunks_retrieved: {pipe_result.get('rag_chunks_retrieved')}")
    print(
        f"  pipeline quantification_eligible: {pipe_result.get('quantification_eligible')}"
    )


async def main():
    from db.postgres_client import PostgresDB

    db = PostgresDB()
    await db.connect()

    bills = [
        {
            "bill_number": "SB 277",
            "jurisdiction": "State of California",
        },
        {
            "bill_number": "ACR 117",
            "jurisdiction": "State of California",
        },
    ]

    try:
        # Step 0: Ensure trigger_source column exists
        print("=== Step 0: Schema Pre-flight ===")
        try:
            await db._execute("""
                ALTER TABLE pipeline_runs
                  ADD COLUMN IF NOT EXISTS trigger_source TEXT DEFAULT 'manual'
            """)
            print("  trigger_source column ensured")
            await db._execute("""
                CREATE INDEX IF NOT EXISTS idx_pipeline_runs_trigger_source
                  ON pipeline_runs(trigger_source)
            """)
            print("  idx_pipeline_runs_trigger_source ensured")
        except Exception as e:
            print(f"  WARNING: schema pre-flight failed (non-blocking): {e}")

        # Step 1: Ingest/chunk
        print("=== Step 1: Ingestion/Chunking ===")
        for bill in bills:
            leg = await db._fetchrow(
                "SELECT text_content FROM legislation WHERE bill_number = $1",
                bill["bill_number"],
            )
            if not leg or not leg["text_content"]:
                print(f"  SKIP {bill['bill_number']}: no text")
                continue

            text = leg["text_content"]
            if len(text) < 100:
                print(
                    f"  SKIP {bill['bill_number']}: text too short ({len(text)} chars)"
                )
                continue

            # Remove old chunks for this bill
            await db._execute(
                "DELETE FROM document_chunks WHERE metadata::json->>'bill_number' = $1",
                bill["bill_number"],
            )

            metadata = {
                "bill_number": bill["bill_number"],
                "jurisdiction": bill["jurisdiction"].lower(),
                "source_type": "leginfo",
            }

            await ingest_bill(db, bill["bill_number"], text, metadata)

        # Step 2: Run pipeline
        print("\n=== Step 2: Analysis Pipeline ===")
        for bill in bills:
            leg = await db._fetchrow(
                "SELECT text_content FROM legislation WHERE bill_number = $1",
                bill["bill_number"],
            )
            if not leg or not leg["text_content"] or len(leg["text_content"]) < 100:
                print(f"  SKIP {bill['bill_number']}: no valid text")
                continue

            try:
                await run_pipeline(
                    db,
                    bill["bill_number"],
                    leg["text_content"],
                    bill["jurisdiction"],
                )
            except Exception as e:
                print(f"  ERROR running pipeline for {bill['bill_number']}: {e}")
                import traceback

                traceback.print_exc()

        # Step 3: Verify
        print("\n=== Step 3: Verification ===")
        for bill in bills:
            await verify_state(db, bill["bill_number"])

    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
