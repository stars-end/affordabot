#!/usr/bin/env python3
"""Evaluate OSS web-search integration quality for a single jurisdiction using two robust methods.

Method 1: Query-level retrieval quality scorecard.
Method 2: End-to-end RAG contract stability sweep.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import threading
import time
import types
import sys
from dataclasses import dataclass
from dataclasses import dataclass as _dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

backend_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, backend_root)

if "llm_common" not in sys.modules:
    llm_common = types.ModuleType("llm_common")
    core_mod = types.ModuleType("llm_common.core")
    web_mod = types.ModuleType("llm_common.web_search")
    prov_mod = types.ModuleType("llm_common.agents.provenance")
    retrieval_mod = types.ModuleType("llm_common.retrieval")

    class _LLMClient:  # pragma: no cover
        pass

    class _WebSearchClient:  # pragma: no cover
        pass

    @_dataclass
    class _Evidence:  # pragma: no cover
        id: str
        kind: str
        label: str
        url: str
        content: str
        excerpt: str
        confidence: float
        metadata: dict[str, Any]

    @_dataclass
    class _EvidenceEnvelope:  # pragma: no cover
        id: str
        source_tool: str
        source_query: str
        evidence: list[_Evidence]

    @_dataclass
    class _RetrievedChunk:  # pragma: no cover
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
    async def retrieve(self, query: str, top_k: int, min_score: float, filters: dict[str, Any]) -> list[FakeChunk]:
        del query, min_score
        bill = filters.get("bill_number", "UNKNOWN")
        jurisdiction = filters.get("jurisdiction", "unknown")
        return [
            FakeChunk(
                chunk_id=f"{bill}-ctx",
                content=f"{bill}: municipal implementation costs and compliance details for {jurisdiction}.",
                metadata={
                    "source_url": f"https://{jurisdiction}.example.gov/{bill}",
                    "source_type": "bill_text",
                    "content_type": "bill_text",
                    "jurisdiction": jurisdiction,
                },
                score=0.8,
            )
        ][:top_k]


class MockSearxHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/search":
            self.send_response(404)
            self.end_headers()
            return

        q = parse_qs(parsed.query).get("q", [""])[0].lower()
        results = [
            {
                "title": f"Saratoga fiscal memo: {q[:60]}",
                "url": "https://www.ci.saratoga.ca.us/government/city-council",
                "content": "City of Saratoga council records and meeting materials.",
            },
            {
                "title": f"Santa Clara County public policy: {q[:60]}",
                "url": "https://www.sccgov.org/sites/bos/Pages/home.aspx",
                "content": "County policy and budget materials relevant to municipal changes.",
            },
            {
                "title": f"Local news coverage: {q[:60]}",
                "url": "https://www.mercurynews.com/local-government",
                "content": "News coverage with Saratoga context.",
            },
        ]
        body = json.dumps({"results": results}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        del format, args
        return


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


async def method_1_query_scorecard(client: OssSearxngWebSearchClient, jurisdiction: str) -> dict[str, Any]:
    queries = [
        f"{jurisdiction} city council housing ordinance fiscal impact",
        f"{jurisdiction} planning commission zoning amendment cost estimate",
        f"{jurisdiction} municipal budget implementation analysis",
    ]
    rows = []
    official_hits = 0
    unique_domains: set[str] = set()
    for query in queries:
        results = await client.search(query, count=5)
        top = results[:3]
        top_domains = [_domain(r.get("url", "")) for r in top]
        unique_domains.update(d for d in top_domains if d)
        hit = sum(1 for d in top_domains if d.endswith(".gov") or "ci.saratoga.ca.us" in d or "sccgov.org" in d)
        official_hits += hit
        rows.append(
            {
                "query": query,
                "top3_count": len(top),
                "official_domain_hits_top3": hit,
                "top3_domains": top_domains,
            }
        )

    return {
        "name": "method_1_query_scorecard",
        "query_count": len(queries),
        "rows": rows,
        "official_domain_hits_total": official_hits,
        "unique_domains_total": len(unique_domains),
    }


async def method_2_pipeline_stability(client: OssSearxngWebSearchClient, jurisdiction: str) -> dict[str, Any]:
    service = LegislationResearchService(
        llm_client=object(),
        search_client=client,  # type: ignore[arg-type]
        retrieval_backend=FakeRetrievalBackend(),
    )

    bill_ids = ["SR-2026-001", "SR-2026-002", "SR-2026-003"]
    runs = []
    sufficient_count = 0
    total_web_sources = 0
    for bill_id in bill_ids:
        result = await service.research(
            bill_id=bill_id,
            bill_text=(
                f"{bill_id} introduces municipal compliance steps, reporting obligations, "
                "and potential administrative costs. " * 3
            ),
            jurisdiction=jurisdiction,
            top_k=3,
            min_score=0.4,
        )
        sufficient_count += 1 if result.is_sufficient else 0
        total_web_sources += len(result.web_sources)
        runs.append(
            {
                "bill_id": bill_id,
                "web_sources": len(result.web_sources),
                "evidence_envelopes": len(result.evidence_envelopes),
                "is_sufficient": result.is_sufficient,
            }
        )

    return {
        "name": "method_2_pipeline_stability",
        "bill_count": len(bill_ids),
        "runs": runs,
        "sufficiency_rate": round(sufficient_count / len(bill_ids), 3),
        "avg_web_sources": round(total_web_sources / len(bill_ids), 2),
    }


def render_markdown(report: dict[str, Any], out_path: str) -> None:
    lines = [
        "# Single-Jurisdiction OSS Evaluation",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        f"Jurisdiction: `{report['jurisdiction']}`",
        f"Endpoint mode: `{report['endpoint_mode']}`",
        f"Endpoint: `{report['endpoint']}`",
        "",
        "## Method 1 — Query scorecard",
    ]
    m1 = report["method_1"]
    lines.append(f"- query_count: `{m1['query_count']}`")
    lines.append(f"- official_domain_hits_total: `{m1['official_domain_hits_total']}`")
    lines.append(f"- unique_domains_total: `{m1['unique_domains_total']}`")
    lines.append("")
    lines.append("| Query | Top3 | Official hits | Domains |")
    lines.append("|---|---:|---:|---|")
    for row in m1["rows"]:
        lines.append(
            f"| {row['query']} | {row['top3_count']} | {row['official_domain_hits_top3']} | {', '.join(row['top3_domains'])} |"
        )

    m2 = report["method_2"]
    lines.extend([
        "",
        "## Method 2 — Pipeline stability sweep",
        f"- bill_count: `{m2['bill_count']}`",
        f"- sufficiency_rate: `{m2['sufficiency_rate']}`",
        f"- avg_web_sources: `{m2['avg_web_sources']}`",
        "",
        "| Bill | Web sources | Envelopes | Sufficient |",
        "|---|---:|---:|---:|",
    ])
    for row in m2["runs"]:
        lines.append(
            f"| {row['bill_id']} | {row['web_sources']} | {row['evidence_envelopes']} | {row['is_sufficient']} |"
        )

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run_eval(jurisdiction: str, endpoint: str, endpoint_mode: str) -> dict[str, Any]:
    client = OssSearxngWebSearchClient(endpoint=endpoint, timeout_s=5.0, max_retries=3, backoff_base_s=0.1)
    try:
        method_1 = await method_1_query_scorecard(client, jurisdiction)
        method_2 = await method_2_pipeline_stability(client, jurisdiction)
    finally:
        await client.close()

    return {
        "jurisdiction": jurisdiction,
        "endpoint_mode": endpoint_mode,
        "endpoint": endpoint,
        "method_1": method_1,
        "method_2": method_2,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jurisdiction", default="Saratoga CA")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8899)
    parser.add_argument("--live-endpoint", default="")
    parser.add_argument("--out", default="backend/artifacts/single_jurisdiction_oss_eval_report.md")
    parser.add_argument("--out-json", default="backend/artifacts/single_jurisdiction_oss_eval_report.json")
    args = parser.parse_args()

    report: dict[str, Any]
    if args.live_endpoint.strip():
        report = asyncio.run(run_eval(args.jurisdiction, args.live_endpoint.strip(), "live"))
    else:
        server = ThreadingHTTPServer((args.host, args.port), MockSearxHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            report = asyncio.run(run_eval(args.jurisdiction, f"http://{args.host}:{args.port}/search", "mock"))
        finally:
            server.shutdown()
            server.server_close()

    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_json).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    render_markdown(report, args.out)
    print(json.dumps(report, indent=2))
    print(f"Markdown report written: {args.out}")
    print(f"JSON report written: {args.out_json}")


if __name__ == "__main__":
    main()
