#!/usr/bin/env python3
"""POC #2: run current RAG research pipeline with OSS-hosted web search swapped in.

This script keeps `LegislationResearchService` logic unchanged and only swaps the web search
client from Z.ai to an OSS-style SearXNG-compatible endpoint. By default it launches a local
mock SearXNG JSON server so the full flow can be tested in isolation.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import sys
import types
from dataclasses import dataclass as _dataclass

backend_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, backend_root)

# Minimal llm_common shims for local verification contexts where llm_common is not installed.
if "llm_common" not in sys.modules:
    llm_common = types.ModuleType("llm_common")
    core_mod = types.ModuleType("llm_common.core")
    web_mod = types.ModuleType("llm_common.web_search")
    prov_mod = types.ModuleType("llm_common.agents.provenance")
    retrieval_mod = types.ModuleType("llm_common.retrieval")

    class _LLMClient:  # pragma: no cover - runtime shim
        pass

    class _WebSearchClient:  # pragma: no cover - runtime shim
        pass

    @_dataclass
    class _Evidence:  # pragma: no cover - runtime shim
        id: str
        kind: str
        label: str
        url: str
        content: str
        excerpt: str
        confidence: float
        metadata: dict[str, Any]

    @_dataclass
    class _EvidenceEnvelope:  # pragma: no cover - runtime shim
        id: str
        source_tool: str
        source_query: str
        evidence: list[_Evidence]

    @_dataclass
    class _RetrievedChunk:  # pragma: no cover - runtime shim
        chunk_id: str
        content: str
        metadata: dict[str, Any]
        score: float

    core_mod.LLMClient = _LLMClient
    web_mod.WebSearchClient = _WebSearchClient
    prov_mod.Evidence = _Evidence
    prov_mod.EvidenceEnvelope = _EvidenceEnvelope
    retrieval_mod.RetrievedChunk = _RetrievedChunk
    llm_common.core = core_mod
    llm_common.web_search = web_mod
    llm_common.agents = types.ModuleType("llm_common.agents")
    llm_common.agents.provenance = prov_mod
    llm_common.retrieval = retrieval_mod

    sys.modules["llm_common"] = llm_common
    sys.modules["llm_common.core"] = core_mod
    sys.modules["llm_common.web_search"] = web_mod
    sys.modules["llm_common.agents"] = llm_common.agents
    sys.modules["llm_common.agents.provenance"] = prov_mod
    sys.modules["llm_common.retrieval"] = retrieval_mod

from services.legislation_research import LegislationResearchService  # noqa: E402
from services.llm.web_search_factory import OssSearxngWebSearchClient  # noqa: E402


@dataclass
class FakeChunk:
    chunk_id: str
    content: str
    metadata: dict[str, Any]
    score: float


class FakeRetrievalBackend:
    async def retrieve(
        self,
        query: str,
        top_k: int,
        min_score: float,
        filters: dict[str, Any],
    ) -> list[FakeChunk]:
        del query, min_score
        bill = filters.get("bill_number", "UNKNOWN")
        jurisdiction = filters.get("jurisdiction", "unknown")
        return [
            FakeChunk(
                chunk_id=f"{bill}-chunk-1",
                content=(
                    f"{bill} requires annual implementation reporting and may involve "
                    "new appropriations subject to committee fiscal review."
                ),
                metadata={
                    "source_url": f"https://{jurisdiction}.example.gov/{bill}",
                    "source_type": "bill_text",
                    "content_type": "bill_text",
                    "jurisdiction": jurisdiction,
                },
                score=0.82,
            )
        ][:top_k]


class MockSearxHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/search":
            self.send_response(404)
            self.end_headers()
            return

        query = parse_qs(parsed.query).get("q", [""])[0]
        results = {
            "results": [
                {
                    "title": f"Fiscal analysis for {query}",
                    "url": "https://lao.ca.gov/mock-fiscal-analysis",
                    "content": "Legislative Analyst review references implementation cost estimates.",
                },
                {
                    "title": f"Committee analysis for {query}",
                    "url": "https://leginfo.legislature.ca.gov/mock-committee-analysis",
                    "content": "Committee summary references appropriations and compliance obligations.",
                },
            ]
        }

        payload = json.dumps(results).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        del format, args
        return


async def run_poc(base_url: str) -> dict[str, Any]:
    search = OssSearxngWebSearchClient(endpoint=f"{base_url}/search", timeout_s=5.0)
    service = LegislationResearchService(
        llm_client=object(),
        search_client=search,  # type: ignore[arg-type]
        retrieval_backend=FakeRetrievalBackend(),
    )

    result = await service.research(
        bill_id="AB-123",
        bill_text=(
            "A bill to establish reporting and compliance requirements with "
            "potential fiscal impacts for implementing agencies. " * 4
        ),
        jurisdiction="California",
        top_k=3,
        min_score=0.4,
    )
    await search.close()

    return {
        "rag_chunks": len(result.rag_chunks),
        "web_sources": len(result.web_sources),
        "evidence_envelopes": len(result.evidence_envelopes),
        "is_sufficient": result.is_sufficient,
        "insufficiency_reason": result.insufficiency_reason,
        "first_web_source": (result.web_sources[0]["url"] if result.web_sources else None),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8877)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), MockSearxHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    summary: dict[str, Any]
    try:
        summary = asyncio.run(run_poc(base_url=f"http://{args.host}:{args.port}"))
    finally:
        server.shutdown()
        server.server_close()

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
