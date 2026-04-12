#!/usr/bin/env python3
"""Path B POC: Windmill-style orchestration with an affordabot domain boundary.

This script is intentionally deterministic and local-first. It models Windmill step
boundaries while keeping product-data writes inside coarse domain commands.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse


CONTRACT_VERSION = "2026-04-12.windmill-storage-bakeoff.v1"
DEFAULT_QUERY = "San Jose CA city council meeting minutes housing"
DEFAULT_JURISDICTION = "San Jose CA"
DEFAULT_SOURCE_FAMILY = "meeting_minutes"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_for_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")


def canonical_document_key(jurisdiction: str, url: str) -> str:
    """Domain invariant: stable document identity from jurisdiction + canonical URL."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    normalized = f"{host}{path}"
    return f"{normalize_for_key(jurisdiction)}::{stable_hash(normalized)[:16]}"


@dataclass
class Envelope:
    architecture_path: str
    windmill_run_id: str
    windmill_job_id: str
    idempotency_key: str
    jurisdiction: str
    source_family: str
    windmill_workspace: str = "affordabot"
    windmill_flow_path: str = "f/affordabot/pipeline_daily_refresh_domain_boundary__flow"
    orchestrator: str = "windmill"
    contract_version: str = CONTRACT_VERSION

    def as_dict(self) -> Dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "architecture_path": self.architecture_path,
            "orchestrator": self.orchestrator,
            "windmill_workspace": self.windmill_workspace,
            "windmill_flow_path": self.windmill_flow_path,
            "windmill_run_id": self.windmill_run_id,
            "windmill_job_id": self.windmill_job_id,
            "idempotency_key": self.idempotency_key,
            "jurisdiction": self.jurisdiction,
            "source_family": self.source_family,
        }


class SearxLikeClient:
    """SearXNG-compatible abstraction preserving SearX JSON response shape."""

    def __init__(self, fail_mode: bool = False):
        self.fail_mode = fail_mode

    def search(self, query: str) -> Dict[str, Any]:
        if self.fail_mode:
            raise RuntimeError("simulated_source_error")
        return {
            "query": query,
            "number_of_results": 2,
            "results": [
                {
                    "url": "https://www.sanjoseca.gov/your-government/departments-offices/city-clerk/city-council-meeting-minutes",
                    "title": "City Council Meeting Minutes",
                    "content": "Official San Jose City Council meeting minutes archive.",
                    "engines": ["mock-searxng"],
                },
                {
                    "url": "https://www.sanjoseca.gov/news-stories/minutes-and-agendas",
                    "title": "Minutes and Agendas",
                    "content": "Minutes and agendas for council meetings.",
                    "engines": ["mock-searxng"],
                },
            ],
            "answers": [],
            "infoboxes": [],
        }


class ReaderContractClient:
    """Z.ai reader contract shape; deterministic local body unless fail_mode is set."""

    def __init__(self, fail_mode: bool = False):
        self.fail_mode = fail_mode

    def fetch(self, url: str) -> Dict[str, Any]:
        if self.fail_mode:
            raise RuntimeError("simulated_reader_error")
        markdown = (
            "# San Jose City Council Meeting Minutes\n\n"
            "2026-04-10 meeting highlights:\n"
            "- Housing permit processing timelines discussed.\n"
            "- Fee schedule update hearing moved to next session.\n"
            "- Public comments on affordable housing expansion."
        )
        return {
            "reader_result": {
                "url": url,
                "title": "San Jose Meeting Minutes",
                "markdown": markdown,
                "fetched_at": iso_now(),
            }
        }


class VectorAdapter:
    """pgvector-compatible adapter with deterministic embeddings."""

    dimension = 8

    def embed(self, text: str) -> List[float]:
        digest = stable_hash(text)
        vals = []
        for i in range(self.dimension):
            chunk = digest[i * 8 : (i + 1) * 8]
            vals.append((int(chunk, 16) % 1000) / 1000.0)
        return vals


class AnalysisAdapter:
    """Deterministic stand-in for Z.ai analysis with explicit evidence references."""

    def analyze(self, question: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not chunks:
            raise RuntimeError("analysis_requires_evidence")
        evidence_refs = [
            {
                "chunk_id": c["chunk_id"],
                "canonical_document_key": c["canonical_document_key"],
                "artifact_ref": c["artifact_ref"],
            }
            for c in chunks
        ]
        return {
            "status": "succeeded",
            "question": question,
            "summary": (
                "San Jose meeting minutes indicate active housing policy discussions and "
                "scheduled follow-up hearings affecting near-term planning timelines."
            ),
            "sufficiency_state": "qualitative_only",
            "claims": [
                {
                    "claim": "Housing-related agenda items were actively discussed.",
                    "evidence_refs": evidence_refs[:2],
                }
            ],
        }


@dataclass
class InMemoryDomainStore:
    """Product storage surrogate for Postgres + pgvector + MinIO interfaces."""

    search_snapshots: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    documents: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    artifacts: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    chunks: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    analyses: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    run_summaries: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def snapshot_counts(self) -> Dict[str, int]:
        return {
            "search_snapshots": len(self.search_snapshots),
            "documents": len(self.documents),
            "artifacts": len(self.artifacts),
            "chunks": len(self.chunks),
            "analyses": len(self.analyses),
            "run_summaries": len(self.run_summaries),
        }


class DomainBoundaryService:
    """Affordabot domain commands.

    These are intentionally coarse commands. Each command enforces at least one
    product invariant so this layer is not a thin SQL wrapper.
    """

    def __init__(
        self,
        store: InMemoryDomainStore,
        search_client: SearxLikeClient,
        reader_client: ReaderContractClient,
        vector_adapter: VectorAdapter,
        analysis_adapter: AnalysisAdapter,
        fail_storage_step: Optional[str] = None,
    ):
        self.store = store
        self.search_client = search_client
        self.reader_client = reader_client
        self.vector_adapter = vector_adapter
        self.analysis_adapter = analysis_adapter
        self.fail_storage_step = fail_storage_step

    def _assert_storage_available(self, step_name: str) -> None:
        if self.fail_storage_step == step_name:
            raise RuntimeError(f"simulated_storage_error:{step_name}")

    def search_materialize(self, env: Envelope, query: str) -> Dict[str, Any]:
        """Invariant: idempotent search snapshot materialization keyed by query+scope."""
        try:
            raw = self.search_client.search(query)
        except Exception as exc:
            return {"status": "source_error", "error": str(exc)}

        results = raw.get("results", [])
        snapshot_key = stable_hash(
            f"{env.jurisdiction}|{env.source_family}|{query}|{json.dumps(results, sort_keys=True)}"
        )[:16]
        snapshot_id = f"snapshot-{snapshot_key}"
        if snapshot_id not in self.store.search_snapshots:
            self._assert_storage_available("search_materialize")
            self.store.search_snapshots[snapshot_id] = {
                "snapshot_id": snapshot_id,
                "query": query,
                "result_count": len(results),
                "results": results,
                "captured_at": iso_now(),
                "jurisdiction": env.jurisdiction,
                "source_family": env.source_family,
            }
        status = "empty_result" if len(results) == 0 else "fresh"
        return {"status": status, "snapshot_id": snapshot_id, "result_count": len(results)}

    def freshness_gate(self, env: Envelope, snapshot_id: str, max_stale_hours: int) -> Dict[str, Any]:
        """Invariant: explicit stale policy; zero results are not transport failures."""
        snap = self.store.search_snapshots.get(snapshot_id)
        if not snap:
            return {"status": "source_error", "error": "missing_snapshot"}
        captured_at = datetime.fromisoformat(snap["captured_at"])
        age = utc_now() - captured_at
        if snap["result_count"] == 0:
            return {"status": "empty_result", "age_seconds": int(age.total_seconds())}
        if age <= timedelta(hours=max_stale_hours):
            return {"status": "fresh", "age_seconds": int(age.total_seconds())}
        return {"status": "stale_blocked", "age_seconds": int(age.total_seconds())}

    def read_fetch(self, env: Envelope, snapshot_id: str) -> Dict[str, Any]:
        """Invariant: canonical document identity + artifact reference dedup."""
        snap = self.store.search_snapshots.get(snapshot_id)
        if not snap:
            return {"status": "reader_error", "error": "missing_snapshot"}
        if not snap["results"]:
            return {"status": "reader_error", "error": "no_results_to_read"}
        target = snap["results"][0]
        url = target["url"]
        doc_key = canonical_document_key(env.jurisdiction, url)
        try:
            payload = self.reader_client.fetch(url)
        except Exception as exc:
            return {"status": "reader_error", "error": str(exc)}
        reader_result = payload.get("reader_result", payload)
        markdown = reader_result.get("markdown", "")
        artifact_hash = stable_hash(markdown)[:16]
        artifact_ref = f"minio://affordabot-artifacts/{env.jurisdiction.replace(' ', '_')}/{artifact_hash}.md"

        self._assert_storage_available("read_fetch")
        if artifact_ref not in self.store.artifacts:
            self.store.artifacts[artifact_ref] = {
                "artifact_ref": artifact_ref,
                "content_hash": artifact_hash,
                "content_type": "text/markdown",
                "body": markdown,
                "source_url": url,
                "created_at": iso_now(),
            }
        if doc_key not in self.store.documents:
            self.store.documents[doc_key] = {
                "canonical_document_key": doc_key,
                "source_url": url,
                "artifact_ref": artifact_ref,
                "jurisdiction": env.jurisdiction,
                "source_family": env.source_family,
                "created_at": iso_now(),
            }
        return {
            "status": "fresh",
            "canonical_document_key": doc_key,
            "artifact_ref": artifact_ref,
            "source_url": url,
        }

    def index(self, env: Envelope, canonical_key: str) -> Dict[str, Any]:
        """Invariant: chunk provenance includes canonical key + artifact ref, with upsert idempotency."""
        doc = self.store.documents.get(canonical_key)
        if not doc:
            return {"status": "storage_error", "error": "missing_document"}
        artifact = self.store.artifacts.get(doc["artifact_ref"])
        if not artifact:
            return {"status": "storage_error", "error": "missing_artifact"}
        text = artifact["body"]
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        chunks_created = 0
        self._assert_storage_available("index")
        for idx, line in enumerate(lines):
            chunk_id = f"chunk-{stable_hash(f'{canonical_key}|{line}')[:20]}"
            if chunk_id in self.store.chunks:
                continue
            self.store.chunks[chunk_id] = {
                "chunk_id": chunk_id,
                "canonical_document_key": canonical_key,
                "artifact_ref": doc["artifact_ref"],
                "chunk_index": idx,
                "content": line,
                "embedding": self.vector_adapter.embed(line),
                "created_at": iso_now(),
            }
            chunks_created += 1
        return {"status": "fresh", "chunks_total": len(lines), "chunks_created": chunks_created}

    def analyze(self, env: Envelope, question: str) -> Dict[str, Any]:
        """Invariant: no analysis without evidence chunks and traceable provenance."""
        usable_chunks = [
            c
            for c in self.store.chunks.values()
            if self.store.documents.get(c["canonical_document_key"], {}).get("jurisdiction")
            == env.jurisdiction
        ]
        if not usable_chunks:
            return {"status": "analysis_error", "error": "insufficient_evidence"}
        analysis_id = f"analysis-{stable_hash(env.idempotency_key)[:16]}"
        if analysis_id in self.store.analyses:
            return {"status": "fresh", "analysis_id": analysis_id, "reused": True}
        self._assert_storage_available("analyze")
        analysis_payload = self.analysis_adapter.analyze(question, usable_chunks)
        self.store.analyses[analysis_id] = {
            "analysis_id": analysis_id,
            "question": question,
            "payload": analysis_payload,
            "created_at": iso_now(),
            "evidence_chunk_ids": [c["chunk_id"] for c in usable_chunks],
        }
        return {"status": "fresh", "analysis_id": analysis_id, "reused": False}

    def summarize_run(self, env: Envelope, step_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Invariant: run summary links orchestration IDs to domain storage state."""
        summary_id = f"summary-{env.windmill_run_id}"
        status = "succeeded"
        alerts: List[str] = []
        for step_name in ("search_materialize", "freshness_gate", "read_fetch", "index", "analyze"):
            step_status = step_results.get(step_name, {}).get("status", "unknown")
            if step_status not in {"fresh", "succeeded"}:
                status = "failed"
                alerts.append(f"{step_name}:{step_status}")
        summary = {
            "summary_id": summary_id,
            "status": status,
            "alerts": alerts,
            "step_results": step_results,
            "storage_counts": self.store.snapshot_counts(),
            "envelope": env.as_dict(),
            "created_at": iso_now(),
        }
        self.store.run_summaries[summary_id] = summary
        return summary


class WindmillShapedRunner:
    """Local flow runner with Windmill-like step graph."""

    def __init__(self, domain: DomainBoundaryService):
        self.domain = domain

    @staticmethod
    def _safe_step(name: str, fn: Any, *args: Any) -> Dict[str, Any]:
        try:
            return fn(*args)
        except Exception as exc:
            error_text = str(exc)
            status = "storage_error" if "storage_error" in error_text else "source_error"
            if "reader_error" in error_text:
                status = "reader_error"
            return {"status": status, "error": error_text, "step": name}

    def run_once(
        self,
        run_id: str,
        job_id: str,
        idempotency_key: str,
        query: str,
        question: str,
        jurisdiction: str = DEFAULT_JURISDICTION,
        source_family: str = DEFAULT_SOURCE_FAMILY,
    ) -> Dict[str, Any]:
        env = Envelope(
            architecture_path="affordabot_domain_boundary",
            windmill_run_id=run_id,
            windmill_job_id=job_id,
            idempotency_key=idempotency_key,
            jurisdiction=jurisdiction,
            source_family=source_family,
        )

        steps: Dict[str, Dict[str, Any]] = {}
        steps["search_materialize"] = self._safe_step(
            "search_materialize", self.domain.search_materialize, env, query
        )
        if steps["search_materialize"].get("status") not in {"fresh", "empty_result"}:
            return self.domain.summarize_run(env, steps)

        snapshot_id = steps["search_materialize"].get("snapshot_id", "")
        steps["freshness_gate"] = self._safe_step(
            "freshness_gate", self.domain.freshness_gate, env, snapshot_id, 24
        )
        if steps["freshness_gate"].get("status") != "fresh":
            return self.domain.summarize_run(env, steps)

        steps["read_fetch"] = self._safe_step("read_fetch", self.domain.read_fetch, env, snapshot_id)
        if steps["read_fetch"].get("status") != "fresh":
            return self.domain.summarize_run(env, steps)

        canonical_key = steps["read_fetch"]["canonical_document_key"]
        steps["index"] = self._safe_step("index", self.domain.index, env, canonical_key)
        if steps["index"].get("status") != "fresh":
            return self.domain.summarize_run(env, steps)

        steps["analyze"] = self._safe_step("analyze", self.domain.analyze, env, question)
        return self.domain.summarize_run(env, steps)


def run_scenario(scenario: str) -> Dict[str, Any]:
    store = InMemoryDomainStore()
    query = DEFAULT_QUERY
    question = "Summarize housing-related signals from recent San Jose meeting minutes."
    idempotency = "san-jose-ca:meeting_minutes:2026-04-12"

    if scenario == "source_failure":
        domain = DomainBoundaryService(
            store=store,
            search_client=SearxLikeClient(fail_mode=True),
            reader_client=ReaderContractClient(fail_mode=False),
            vector_adapter=VectorAdapter(),
            analysis_adapter=AnalysisAdapter(),
        )
        runner = WindmillShapedRunner(domain)
        return runner.run_once("run-source-failure", "job-search", idempotency, query, question)

    if scenario == "reader_failure":
        domain = DomainBoundaryService(
            store=store,
            search_client=SearxLikeClient(fail_mode=False),
            reader_client=ReaderContractClient(fail_mode=True),
            vector_adapter=VectorAdapter(),
            analysis_adapter=AnalysisAdapter(),
        )
        runner = WindmillShapedRunner(domain)
        return runner.run_once("run-reader-failure", "job-reader", idempotency, query, question)

    if scenario == "storage_failure":
        domain = DomainBoundaryService(
            store=store,
            search_client=SearxLikeClient(fail_mode=False),
            reader_client=ReaderContractClient(fail_mode=False),
            vector_adapter=VectorAdapter(),
            analysis_adapter=AnalysisAdapter(),
            fail_storage_step="index",
        )
        runner = WindmillShapedRunner(domain)
        return runner.run_once("run-storage-failure", "job-index", idempotency, query, question)

    domain = DomainBoundaryService(
        store=store,
        search_client=SearxLikeClient(fail_mode=False),
        reader_client=ReaderContractClient(fail_mode=False),
        vector_adapter=VectorAdapter(),
        analysis_adapter=AnalysisAdapter(),
    )
    runner = WindmillShapedRunner(domain)
    first = runner.run_once("run-first", "job-main", idempotency, query, question)
    second = runner.run_once("run-second", "job-main", idempotency, query, question)
    return {"first_run": first, "rerun": second}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Path B Windmill storage-boundary bakeoff (domain boundary model)."
    )
    parser.add_argument(
        "--scenario",
        choices=["happy_rerun", "source_failure", "reader_failure", "storage_failure"],
        default="happy_rerun",
        help="Scenario to execute.",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional JSON output file path.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_scenario(args.scenario)
    if args.pretty:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps(result, sort_keys=True))
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
