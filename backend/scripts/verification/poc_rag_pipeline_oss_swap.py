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
import time
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


def _render_markdown(summary: dict[str, Any], out_path: str | None) -> None:
    if not out_path:
        return
    lines = [
        "# OSS Swap RAG Verification Report",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        "",
        f"- Jurisdiction: `{summary['jurisdiction']}`",
        f"- Bill ID: `{summary['bill_id']}`",
        f"- Endpoint mode: `{summary['endpoint_mode']}`",
        f"- Endpoint: `{summary['endpoint']}`",
        "",
        "## Pipeline contract checks",
        f"- rag_chunks: `{summary['rag_chunks']}`",
        f"- web_sources: `{summary['web_sources']}`",
        f"- evidence_envelopes: `{summary['evidence_envelopes']}`",
        f"- is_sufficient: `{summary['is_sufficient']}`",
        f"- insufficiency_reason: `{summary['insufficiency_reason']}`",
        "",
        "## Top web results",
        "",
    ]
    for idx, item in enumerate(summary.get("top_web_sources", []), 1):
        lines.append(f"{idx}. [{item.get('title','')}]({item.get('url','')})")
    lines.append("")
    lines.append("## Saratoga relevance signals")
    lines.append(f"- official_domain_hits: `{summary.get('official_domain_hits', 0)}`")
    lines.append(f"- saratoga_mention_hits: `{summary.get('saratoga_mention_hits', 0)}`")
    lines.append("")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run_poc(endpoint: str, endpoint_mode: str, bill_id: str, jurisdiction: str, bill_text: str) -> dict[str, Any]:
    search = OssSearxngWebSearchClient(
        endpoint=endpoint,
        timeout_s=5.0,
        max_retries=3,
        backoff_base_s=0.1,
        backoff_max_s=0.5,
    )
    service = LegislationResearchService(
        llm_client=object(),
        search_client=search,  # type: ignore[arg-type]
        retrieval_backend=FakeRetrievalBackend(),
    )

    result = await service.research(
        bill_id=bill_id,
        bill_text=bill_text,
        jurisdiction=jurisdiction,
        top_k=3,
        min_score=0.4,
    )
    await search.close()

    top_web_sources = [
        {
            "title": item.get("title", ""),
            "url": item.get("url") or item.get("link") or "",
        }
        for item in result.web_sources[:5]
    ]
    official_domains = ("ci.saratoga.ca.us", ".gov", "sccgov.org", "santaclaracounty.gov")
    official_domain_hits = sum(
        1
        for item in result.web_sources
        if any(token in ((item.get("url") or item.get("link") or "").lower()) for token in official_domains)
    )
    saratoga_mention_hits = sum(
        1
        for item in result.web_sources
        if "saratoga" in (item.get("title", "") + " " + item.get("snippet", "")).lower()
    )

    return {
        "bill_id": bill_id,
        "jurisdiction": jurisdiction,
        "endpoint_mode": endpoint_mode,
        "endpoint": endpoint,
        "rag_chunks": len(result.rag_chunks),
        "web_sources": len(result.web_sources),
        "evidence_envelopes": len(result.evidence_envelopes),
        "is_sufficient": result.is_sufficient,
        "insufficiency_reason": result.insufficiency_reason,
        "first_web_source": (result.web_sources[0]["url"] if result.web_sources else None),
        "top_web_titles": [item.get("title", "") for item in result.web_sources[:3]],
        "top_web_sources": top_web_sources,
        "official_domain_hits": official_domain_hits,
        "saratoga_mention_hits": saratoga_mention_hits,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8877)
    parser.add_argument("--bill-id", default="AB-123")
    parser.add_argument("--jurisdiction", default="California")
    parser.add_argument(
        "--live-endpoint",
        default="",
        help="Use a real OSS endpoint (e.g. http://127.0.0.1:8080/search). If omitted, local mock server is used.",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional markdown output path for result report.",
    )
    parser.add_argument(
        "--bill-text",
        default=(
            "A bill to establish reporting and compliance requirements with "
            "potential fiscal impacts for implementing agencies. " * 4
        ),
    )
    args = parser.parse_args()

    summary: dict[str, Any]
    if args.live_endpoint.strip():
        endpoint = args.live_endpoint.strip()
        summary = asyncio.run(
            run_poc(
                endpoint=endpoint,
                endpoint_mode="live",
                bill_id=args.bill_id,
                jurisdiction=args.jurisdiction,
                bill_text=args.bill_text,
            )
        )
    else:
        server = ThreadingHTTPServer((args.host, args.port), MockSearxHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            summary = asyncio.run(
                run_poc(
                    endpoint=f"http://{args.host}:{args.port}/search",
                    endpoint_mode="mock",
                    bill_id=args.bill_id,
                    jurisdiction=args.jurisdiction,
                    bill_text=args.bill_text,
                )
            )
        finally:
            server.shutdown()
            server.server_close()

    print(json.dumps(summary, indent=2))
    _render_markdown(summary, args.out or None)


if __name__ == "__main__":
    main()
