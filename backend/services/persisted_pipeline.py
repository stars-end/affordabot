"""Persisted pipeline with SearXNG search, Z.ai Web Reader, and Z.ai LLM analysis.

This module implements the architecture-locking POC for bd-jxclm.14.1:
- SearXNG/OSS search is the primary search provider.
- Z.ai direct Web Reader is the canonical reader provider.
- Z.ai LLM analysis/synthesis is mockable locally and live-capable.
- Z.ai direct Web Search is deprecated and excluded from the product flow.

Backend step responses are branchable by Windmill and contain NO backend-owned
retry/DAG fields (no next_recommended_step, max_retries, retry_after_seconds).

Uses SQLite proof-store so the POC runs in any worktree without Postgres.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import textwrap
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote_plus, urlparse
from uuid import uuid4


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONTRACT_VERSION = "persisted-pipeline.v1"
ZAI_DIRECT_SEARCH_DEPRECATED = True

FRESHNESS_TTL_HOURS = 36
DEFAULT_SEARXNG_URL = "http://localhost:8888"
ZAI_READER_ENDPOINT_PAAS = "https://api.z.ai/api/paas/v4/reader"
ZAI_READER_ENDPOINT_CODING = "https://api.z.ai/api/coding/paas/v4/reader"
ZAI_LLM_BASE_URL_DEFAULT = "https://api.z.ai/api/paas/v4"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def bytes_hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def json_loads(value: str | None, fallback: Any = None) -> Any:
    if value is None:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    domain: str
    content: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "domain": self.domain,
            "content": self.content,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SearchResult":
        return cls(
            title=value["title"],
            url=value["url"],
            snippet=value.get("snippet", ""),
            domain=value.get("domain") or urlparse(value["url"]).netloc,
            content=value.get("content", ""),
            metadata=value.get("metadata", {}),
        )


@dataclass(frozen=True)
class ReaderResult:
    url: str
    raw_response: bytes
    markdown: str
    text: str
    content_type: str
    provider: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnalysisResult:
    summary: str
    key_facts: list[str]
    provider: str
    raw_response: bytes
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Provider protocols
# ---------------------------------------------------------------------------


class SearchProvider(Protocol):
    def search(self, query: str) -> list[SearchResult]: ...


class ReaderProvider(Protocol):
    def read(self, url: str) -> ReaderResult: ...


class AnalysisProvider(Protocol):
    def analyze(self, content: str, context: dict[str, Any]) -> AnalysisResult: ...


# ---------------------------------------------------------------------------
# SearXNG search provider
# ---------------------------------------------------------------------------


class SearXNGSearchProvider:
    """SearXNG-compatible search provider.

    Calls a SearXNG instance via its JSON API. Returns normalized
    SearchResult objects. Falls back to urllib so no extra deps needed.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: int = 20,
        categories: str = "general",
    ):
        self.base_url = (
            base_url or os.getenv("SEARXNG_URL", DEFAULT_SEARXNG_URL)
        ).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.categories = categories

    def search(self, query: str) -> list[SearchResult]:
        url = (
            f"{self.base_url}/search"
            f"?q={quote_plus(query)}"
            f"&format=json"
            f"&categories={self.categories}"
        )
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "AffordabotPersistedPipeline/1.0",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as resp:
            body = resp.read()
        data = json.loads(body.decode("utf-8"))
        results = data.get("results", [])
        normalized: list[SearchResult] = []
        for r in results:
            normalized.append(
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    snippet=r.get("content", ""),
                    domain=urlparse(r.get("url", "")).netloc,
                    content=r.get("content", ""),
                    metadata={
                        "engine": r.get("engine", ""),
                        "score": r.get("score"),
                        "category": r.get("category", ""),
                    },
                )
            )
        return normalized


# ---------------------------------------------------------------------------
# Fixed / mock providers
# ---------------------------------------------------------------------------


class FixedSearchProvider:
    """Deterministic provider for testing / POC fixtures."""

    def __init__(self, results: list[SearchResult] | None = None):
        self._results = results or [
            SearchResult(
                title="San Jose City Council - Official Agenda Portal",
                url="https://sanjose.legistar.com/Calendar.aspx",
                snippet="Official San Jose Legistar calendar with agendas and minutes.",
                domain="sanjose.legistar.com",
                content="City Council meeting calendar, agendas, and minutes.",
                metadata={
                    "event_id": 7616,
                    "jurisdiction": "San Jose, CA",
                    "asset_class": "minutes",
                },
            )
        ]

    def search(self, query: str) -> list[SearchResult]:
        return list(self._results)


class FailingSearchProvider:
    """Provider that always raises, used for failure drills."""

    def __init__(self, message: str = "simulated searxng outage"):
        self.message = message

    def search(self, query: str) -> list[SearchResult]:
        raise RuntimeError(self.message)


class ZeroResultSearchProvider:
    """Provider that returns empty results (distinct from failure)."""

    def search(self, query: str) -> list[SearchResult]:
        return []


class MockReaderProvider:
    """Reader that returns fixture content without network calls."""

    def __init__(self, content: str | None = None):
        self.content = content or textwrap.dedent(
            """\
            # San Jose City Council Meeting Minutes

            - Jurisdiction: San Jose, CA
            - Event ID: 7616
            - Body: City Council
            - Event date: 2026-04-07
            - Minutes status: Draft

            ## Summary

            The City Council met in regular session to discuss budget items.
        """
        )

    def read(self, url: str) -> ReaderResult:
        raw = json.dumps(
            {
                "url": url,
                "content": self.content,
                "provider": "mock",
            }
        ).encode("utf-8")
        return ReaderResult(
            url=url,
            raw_response=raw,
            markdown=self.content,
            text=self.content,
            content_type="text/markdown; charset=utf-8",
            provider="mock_reader",
            metadata={"mock": True},
        )


class ZaiWebReaderProvider:
    """Z.ai direct Web Reader client.

    Calls POST /api/paas/v4/reader or POST /api/coding/paas/v4/reader
    by configuration. This is the canonical reader — NOT chat completions.
    """

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str | None = None,
        timeout_seconds: int = 30,
    ):
        self.api_key = api_key or os.getenv("ZAI_API_KEY", "")
        self.endpoint = endpoint or os.getenv(
            "ZAI_READER_ENDPOINT", ZAI_READER_ENDPOINT_PAAS
        )
        self.timeout_seconds = timeout_seconds

    def read(self, url: str) -> ReaderResult:
        if not self.api_key:
            raise RuntimeError("ZAI_API_KEY not configured for reader")
        payload = json.dumps({"url": url}).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "AffordabotPersistedPipeline/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as resp:
            body = resp.read()
            content_type = resp.headers.get("content-type", "application/json")

        data = json.loads(body.decode("utf-8"))
        reader_result = data.get("reader_result", {})
        if not isinstance(reader_result, dict):
            reader_result = {}

        md = (
            reader_result.get("content")
            or reader_result.get("markdown")
            or data.get("markdown")
            or data.get("content")
            or ""
        )
        text = (
            reader_result.get("text")
            or reader_result.get("content")
            or data.get("text")
            or md
        )
        if not md.strip():
            raise RuntimeError("reader response did not contain non-empty content")

        return ReaderResult(
            url=url,
            raw_response=body,
            markdown=md,
            text=text,
            content_type=content_type,
            provider="zai_web_reader",
            metadata={
                "endpoint": self.endpoint,
                "reader_title": reader_result.get("title"),
                "reader_description": reader_result.get("description"),
                "reader_url": reader_result.get("url"),
                "reader_metadata": reader_result.get("metadata"),
                "ZAI_DIRECT_SEARCH_DEPRECATED": True,
            },
        )


class MockAnalysisProvider:
    """Mockable Z.ai LLM analysis provider for local testing."""

    def analyze(self, content: str, context: dict[str, Any]) -> AnalysisResult:
        return AnalysisResult(
            summary="Mock analysis: content received and processed.",
            key_facts=["mock_fact_1", "mock_fact_2"],
            provider="mock_analysis",
            raw_response=json.dumps(
                {
                    "mock": True,
                    "content_length": len(content),
                }
            ).encode("utf-8"),
            metadata={"mock": True},
        )


class ZaiLLMAnalysisProvider:
    """Minimal Z.ai LLM analysis/synthesis provider.

    Calls the Z.ai chat completions endpoint. Mockable locally;
    live-capable when ZAI_API_KEY exists. Does NOT use chat-web-search.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        endpoint_path: str = "/chat/completions",
        timeout_seconds: int = 60,
    ):
        self.api_key = api_key or os.getenv("ZAI_API_KEY", "")
        self.model = model or os.getenv("ZAI_LLM_MODEL", "glm-4.7")
        env_base_url = os.getenv("ZAI_LLM_BASE_URL")
        env_endpoint = os.getenv("ZAI_LLM_ENDPOINT")
        self.base_url = (base_url or env_base_url or ZAI_LLM_BASE_URL_DEFAULT).rstrip(
            "/"
        )
        self.endpoint_path = endpoint_path
        self.endpoint = env_endpoint or f"{self.base_url}{self.endpoint_path}"
        self.timeout_seconds = timeout_seconds

    def analyze(self, content: str, context: dict[str, Any]) -> AnalysisResult:
        if not self.api_key:
            raise RuntimeError("ZAI_API_KEY not configured for analysis")
        system_prompt = (
            "You are a municipal legislation analyst. "
            "Summarize the provided content and extract key facts. "
            "Do NOT use web search. Base your analysis strictly on the provided text."
        )
        user_prompt = f"Analyze the following content:\n\n{content[:8000]}"
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": 1024,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as resp:
            body = resp.read()
        data = json.loads(body.decode("utf-8"))
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return AnalysisResult(
            summary=text[:500],
            key_facts=_extract_facts(text),
            provider="zai_llm",
            raw_response=body,
            metadata={
                "model": self.model,
                "endpoint": self.endpoint,
                "ZAI_DIRECT_SEARCH_DEPRECATED": True,
            },
        )


def _extract_facts(text: str) -> list[str]:
    lines = text.strip().split("\n")
    facts: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            facts.append(stripped[2:])
        elif len(facts) < 5 and stripped and not stripped.startswith("#"):
            facts.append(stripped)
    return facts[:10]


# ---------------------------------------------------------------------------
# SQLite proof-store (adapted from PR #417)
# ---------------------------------------------------------------------------


class PersistedPipelineStore:
    """SQLite-backed persistence adapter with production-shaped table names."""

    def __init__(self, db_path: Path, artifact_dir: Path):
        self.db_path = db_path
        self.artifact_dir = artifact_dir
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    @classmethod
    def fresh(cls, db_path: Path, artifact_dir: Path) -> "PersistedPipelineStore":
        if db_path.exists():
            db_path.unlink()
        if artifact_dir.exists():
            shutil.rmtree(artifact_dir)
        return cls(db_path=db_path, artifact_dir=artifact_dir)

    def close(self) -> None:
        self.conn.close()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id TEXT PRIMARY KEY,
                run_label TEXT NOT NULL,
                jurisdiction TEXT NOT NULL,
                target_family TEXT NOT NULL,
                status TEXT NOT NULL,
                triggered_by TEXT NOT NULL,
                contract_version TEXT NOT NULL,
                windmill_flow_run_id TEXT,
                windmill_job_id TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                result_json TEXT,
                alerts_json TEXT NOT NULL DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS search_result_snapshots (
                id TEXT PRIMARY KEY,
                family TEXT NOT NULL,
                query TEXT NOT NULL,
                provider TEXT NOT NULL,
                query_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                stale_backed INTEGER NOT NULL DEFAULT 0,
                provider_failure_json TEXT,
                result_count INTEGER NOT NULL,
                results_json TEXT NOT NULL,
                source_snapshot_id TEXT
            );

            CREATE TABLE IF NOT EXISTS content_artifacts (
                id TEXT PRIMARY KEY,
                family TEXT NOT NULL,
                url TEXT NOT NULL,
                canonical_key TEXT NOT NULL,
                artifact_kind TEXT NOT NULL,
                storage_uri TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                content_type TEXT NOT NULL,
                bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                source_snapshot_id TEXT NOT NULL,
                reused_from_artifact_id TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_snapshots_fresh
                ON search_result_snapshots(family, status, expires_at);
            CREATE INDEX IF NOT EXISTS idx_artifacts_key_kind
                ON content_artifacts(canonical_key, artifact_kind, created_at);
            """
        )
        self.conn.commit()

    # -- run operations -----------------------------------------------------

    def create_run(
        self,
        run_label: str,
        triggered_by: str,
        now: datetime,
        *,
        jurisdiction: str = "San Jose, CA",
        target_family: str = "san-jose-city-council-minutes",
        windmill_flow_run_id: str | None = None,
        windmill_job_id: str | None = None,
    ) -> str:
        run_id = f"run_{uuid4().hex}"
        self.conn.execute(
            """
            INSERT INTO pipeline_runs (
                id, run_label, jurisdiction, target_family, status, triggered_by,
                contract_version, windmill_flow_run_id, windmill_job_id,
                started_at, alerts_json
            )
            VALUES (?, ?, ?, ?, 'running', ?, ?, ?, ?, ?, '[]')
            """,
            (
                run_id,
                run_label,
                jurisdiction,
                target_family,
                triggered_by,
                CONTRACT_VERSION,
                windmill_flow_run_id,
                windmill_job_id,
                iso(now),
            ),
        )
        self.conn.commit()
        return run_id

    def complete_run(
        self,
        run_id: str,
        status: str,
        result: dict[str, Any],
        alerts: list[dict[str, Any]],
        now: datetime,
    ) -> None:
        self.conn.execute(
            """
            UPDATE pipeline_runs
            SET status = ?, completed_at = ?, result_json = ?, alerts_json = ?
            WHERE id = ?
            """,
            (status, iso(now), json_dumps(result), json_dumps(alerts), run_id),
        )
        self.conn.commit()

    # -- snapshot operations ------------------------------------------------

    def insert_snapshot(
        self,
        *,
        family: str,
        query: str,
        provider: str,
        results: list[SearchResult],
        observed_at: datetime,
        expires_at: datetime,
        stale_backed: bool = False,
        provider_failure: dict[str, Any] | None = None,
        source_snapshot_id: str | None = None,
    ) -> dict[str, Any]:
        snapshot_id = f"snap_{uuid4().hex}"
        rows = [r.to_dict() for r in results]
        result_count = len(rows)
        status = "succeeded" if result_count > 0 else "zero_results"
        self.conn.execute(
            """
            INSERT INTO search_result_snapshots (
                id, family, query, provider, query_hash, status, observed_at,
                expires_at, stale_backed, provider_failure_json, result_count,
                results_json, source_snapshot_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                family,
                query,
                provider,
                stable_hash(query),
                status,
                iso(observed_at),
                iso(expires_at),
                1 if stale_backed else 0,
                json_dumps(provider_failure) if provider_failure else None,
                result_count,
                json_dumps(rows),
                source_snapshot_id,
            ),
        )
        self.conn.commit()
        return self.get_snapshot(snapshot_id)

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT * FROM search_result_snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()
        if not row:
            raise KeyError(snapshot_id)
        return dict(row)

    def latest_fresh_snapshot(
        self, family: str, query: str, now: datetime
    ) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT *
            FROM search_result_snapshots
            WHERE family = ?
              AND query_hash = ?
              AND status = 'succeeded'
              AND expires_at > ?
              AND result_count > 0
            ORDER BY observed_at DESC
            LIMIT 1
            """,
            (family, stable_hash(query), iso(now)),
        ).fetchone()
        return dict(row) if row else None

    # -- artifact operations ------------------------------------------------

    def latest_artifact(
        self, canonical_key: str, artifact_kind: str
    ) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT *
            FROM content_artifacts
            WHERE canonical_key = ? AND artifact_kind = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (canonical_key, artifact_kind),
        ).fetchone()
        return dict(row) if row else None

    def insert_artifact(
        self,
        *,
        family: str,
        url: str,
        canonical_key: str,
        artifact_kind: str,
        storage_uri: str,
        sha256: str,
        content_type: str,
        byte_count: int,
        created_at: datetime,
        metadata: dict[str, Any],
        source_snapshot_id: str,
        reused_from_artifact_id: str | None = None,
    ) -> dict[str, Any]:
        artifact_id = f"artifact_{uuid4().hex}"
        self.conn.execute(
            """
            INSERT INTO content_artifacts (
                id, family, url, canonical_key, artifact_kind, storage_uri,
                sha256, content_type, bytes, created_at, metadata_json,
                source_snapshot_id, reused_from_artifact_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                family,
                url,
                canonical_key,
                artifact_kind,
                storage_uri,
                sha256,
                content_type,
                byte_count,
                iso(created_at),
                json_dumps(metadata),
                source_snapshot_id,
                reused_from_artifact_id,
            ),
        )
        self.conn.commit()
        return dict(
            self.conn.execute(
                "SELECT * FROM content_artifacts WHERE id = ?", (artifact_id,)
            ).fetchone()
        )

    def write_artifact_file(self, relative_path: str, content: bytes) -> str:
        path = self.artifact_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return str(path)

    # -- reporting ----------------------------------------------------------

    def row_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for table in ("pipeline_runs", "search_result_snapshots", "content_artifacts"):
            row = self.conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
            counts[table] = int(row["count"])
        return counts

    def rows(self, table: str) -> list[dict[str, Any]]:
        return [dict(row) for row in self.conn.execute(f"SELECT * FROM {table}")]


# ---------------------------------------------------------------------------
# Step response contract
# ---------------------------------------------------------------------------


def make_step_response(
    *,
    run_id: str,
    step: str,
    status: str,
    decision: str,
    decision_reason: str,
    evidence: dict[str, Any] | None = None,
    alerts: list[dict[str, Any]] | None = None,
    windmill_flow_run_id: str | None = None,
    windmill_job_id: str | None = None,
) -> dict[str, Any]:
    """Build a Windmill-branchable step response.

    Deliberately excludes next_recommended_step, max_retries,
    retry_after_seconds.  Windmill owns retry/DAG decisions.
    """
    return {
        "contract_version": CONTRACT_VERSION,
        "run_id": run_id,
        "windmill_flow_run_id": windmill_flow_run_id,
        "windmill_job_id": windmill_job_id,
        "step": step,
        "status": status,
        "decision": decision,
        "decision_reason": decision_reason,
        "evidence": evidence or {},
        "alerts": alerts or [],
    }


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------


class PersistedPipeline:
    """Multi-step persisted pipeline with provider abstractions.

    Steps: search_materialize -> read_extract -> analyze -> finalize
    Each step produces a branchable response for Windmill.
    """

    def __init__(
        self,
        store: PersistedPipelineStore,
        search_provider: SearchProvider,
        reader_provider: ReaderProvider,
        analysis_provider: AnalysisProvider,
        *,
        now_fn: Any = utc_now,
    ):
        self.store = store
        self.search_provider = search_provider
        self.reader_provider = reader_provider
        self.analysis_provider = analysis_provider
        self.now_fn = now_fn

    def run_full(
        self,
        *,
        run_label: str,
        triggered_by: str,
        query: str,
        family: str,
        jurisdiction: str = "San Jose, CA",
        prefer_cached_search: bool = False,
        allow_stale_fallback: bool = True,
        skip_analysis: bool = False,
        windmill_flow_run_id: str | None = None,
        windmill_job_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute the full pipeline and return the final step response."""
        alerts: list[dict[str, Any]] = []
        started_at = self.now_fn()
        run_id = self.store.create_run(
            run_label,
            triggered_by,
            started_at,
            jurisdiction=jurisdiction,
            target_family=family,
            windmill_flow_run_id=windmill_flow_run_id,
            windmill_job_id=windmill_job_id,
        )

        # Step 1: search_materialize
        search_resp = self._step_search_materialize(
            run_id=run_id,
            query=query,
            family=family,
            prefer_cached_search=prefer_cached_search,
            allow_stale_fallback=allow_stale_fallback,
            alerts=alerts,
            windmill_flow_run_id=windmill_flow_run_id,
            windmill_job_id=windmill_job_id,
        )
        if search_resp["status"] == "failed":
            self.store.complete_run(
                run_id, "failed", search_resp, alerts, self.now_fn()
            )
            return search_resp

        # Zero results is a terminal decision — no downstream steps possible
        if search_resp["decision"] == "zero_results":
            finalize_resp = make_step_response(
                run_id=run_id,
                step="finalize",
                status="succeeded",
                decision="zero_results",
                decision_reason="search returned zero results; pipeline terminates",
                evidence={
                    "snapshot_id": None,
                    "result_count": 0,
                    "stale_backed": False,
                    "search_decision": "zero_results",
                },
                alerts=alerts,
                windmill_flow_run_id=windmill_flow_run_id,
                windmill_job_id=windmill_job_id,
            )
            self.store.complete_run(
                run_id, "completed", finalize_resp, alerts, self.now_fn()
            )
            return finalize_resp

        snapshot_id = search_resp["evidence"]["snapshot_id"]
        snapshot = self.store.get_snapshot(snapshot_id)

        # Step 2: read_extract
        read_resp = self._step_read_extract(
            run_id=run_id,
            snapshot=snapshot,
            family=family,
            alerts=alerts,
            windmill_flow_run_id=windmill_flow_run_id,
            windmill_job_id=windmill_job_id,
        )
        if read_resp["status"] == "failed":
            self.store.complete_run(run_id, "failed", read_resp, alerts, self.now_fn())
            return read_resp

        # Step 3: analyze (optional)
        if not skip_analysis:
            analyze_resp = self._step_analyze(
                run_id=run_id,
                read_response=read_resp,
                family=family,
                snapshot_id=snapshot_id,
                alerts=alerts,
                windmill_flow_run_id=windmill_flow_run_id,
                windmill_job_id=windmill_job_id,
            )
            if analyze_resp["status"] == "failed":
                self.store.complete_run(
                    run_id, "failed", analyze_resp, alerts, self.now_fn()
                )
                return analyze_resp
        else:
            analyze_resp = make_step_response(
                run_id=run_id,
                step="analyze",
                status="succeeded",
                decision="analysis_succeeded",
                decision_reason="skipped by request",
                evidence={"skipped": True},
                windmill_flow_run_id=windmill_flow_run_id,
                windmill_job_id=windmill_job_id,
            )

        # Step 4: finalize
        finalize_resp = make_step_response(
            run_id=run_id,
            step="finalize",
            status="succeeded",
            decision=(
                "fresh_snapshot" if not snapshot.get("stale_backed") else "stale_backed"
            ),
            decision_reason="pipeline completed successfully",
            evidence={
                "snapshot_id": snapshot_id,
                "result_count": search_resp["evidence"].get("result_count", 0),
                "stale_backed": bool(snapshot.get("stale_backed")),
                "search_decision": search_resp["decision"],
                "read_decision": read_resp["decision"],
                "analyze_decision": analyze_resp["decision"],
            },
            alerts=alerts,
            windmill_flow_run_id=windmill_flow_run_id,
            windmill_job_id=windmill_job_id,
        )

        self.store.complete_run(
            run_id, "completed", finalize_resp, alerts, self.now_fn()
        )
        return finalize_resp

    # -- step implementations -----------------------------------------------

    def _step_search_materialize(
        self,
        *,
        run_id: str,
        query: str,
        family: str,
        prefer_cached_search: bool,
        allow_stale_fallback: bool,
        alerts: list[dict[str, Any]],
        windmill_flow_run_id: str | None,
        windmill_job_id: str | None,
    ) -> dict[str, Any]:
        now = self.now_fn()
        provider_name = type(self.search_provider).__name__

        # Idempotent: check for fresh snapshot
        if prefer_cached_search:
            latest = self.store.latest_fresh_snapshot(family, query, now)
            if latest:
                return make_step_response(
                    run_id=run_id,
                    step="search_materialize",
                    status="succeeded",
                    decision="fresh_snapshot",
                    decision_reason="reused existing fresh snapshot",
                    evidence={
                        "snapshot_id": latest["id"],
                        "result_count": latest["result_count"],
                        "provider": latest["provider"],
                        "reused": True,
                    },
                    windmill_flow_run_id=windmill_flow_run_id,
                    windmill_job_id=windmill_job_id,
                )

        # Try live search
        try:
            results = self.search_provider.search(query)
        except Exception as exc:
            failure = {
                "type": type(exc).__name__,
                "message": str(exc),
                "provider": provider_name,
            }
            fallback = self.store.latest_fresh_snapshot(family, query, now)
            if not allow_stale_fallback or not fallback:
                return make_step_response(
                    run_id=run_id,
                    step="search_materialize",
                    status="failed",
                    decision="provider_failed_no_fallback",
                    decision_reason=(
                        "search provider failed and no fresh fallback snapshot exists"
                    ),
                    evidence={"provider_failure": failure},
                    alerts=[
                        {
                            "severity": "ERROR",
                            "code": "search_failed_no_fallback",
                            "message": str(exc),
                        }
                    ],
                    windmill_flow_run_id=windmill_flow_run_id,
                    windmill_job_id=windmill_job_id,
                )

            # Stale fallback
            copied = [
                SearchResult.from_dict(r)
                for r in json_loads(fallback["results_json"], [])
            ]
            snapshot = self.store.insert_snapshot(
                family=family,
                query=query,
                provider=provider_name,
                results=copied,
                observed_at=now,
                expires_at=from_iso(fallback["expires_at"]),
                stale_backed=True,
                provider_failure=failure,
                source_snapshot_id=fallback["id"],
            )
            alerts.append(
                {
                    "severity": "WARN",
                    "code": "stale_backed_search",
                    "message": f"Search provider failed; stale fallback from {fallback['id']}",
                }
            )
            return make_step_response(
                run_id=run_id,
                step="search_materialize",
                status="succeeded",
                decision="stale_backed",
                decision_reason="provider failed, stale fallback used",
                evidence={
                    "snapshot_id": snapshot["id"],
                    "source_snapshot_id": fallback["id"],
                    "result_count": snapshot["result_count"],
                    "stale_backed": True,
                    "provider_failure": failure,
                },
                alerts=alerts,
                windmill_flow_run_id=windmill_flow_run_id,
                windmill_job_id=windmill_job_id,
            )

        # Zero results — distinct from provider failure
        if not results:
            return make_step_response(
                run_id=run_id,
                step="search_materialize",
                status="succeeded",
                decision="zero_results",
                decision_reason="provider returned zero results (not a failure)",
                evidence={
                    "snapshot_id": None,
                    "result_count": 0,
                    "provider": provider_name,
                },
                alerts=[
                    {
                        "severity": "WARN",
                        "code": "zero_results",
                        "message": "Search returned zero results for query",
                    }
                ],
                windmill_flow_run_id=windmill_flow_run_id,
                windmill_job_id=windmill_job_id,
            )

        # Fresh results
        snapshot = self.store.insert_snapshot(
            family=family,
            query=query,
            provider=provider_name,
            results=results,
            observed_at=now,
            expires_at=now + timedelta(hours=FRESHNESS_TTL_HOURS),
        )
        return make_step_response(
            run_id=run_id,
            step="search_materialize",
            status="succeeded",
            decision="fresh_snapshot",
            decision_reason="new search results materialized",
            evidence={
                "snapshot_id": snapshot["id"],
                "result_count": snapshot["result_count"],
                "provider": provider_name,
                "stale_backed": False,
            },
            windmill_flow_run_id=windmill_flow_run_id,
            windmill_job_id=windmill_job_id,
        )

    def _step_read_extract(
        self,
        *,
        run_id: str,
        snapshot: dict[str, Any],
        family: str,
        alerts: list[dict[str, Any]],
        windmill_flow_run_id: str | None,
        windmill_job_id: str | None,
    ) -> dict[str, Any]:
        results = [
            SearchResult.from_dict(r) for r in json_loads(snapshot["results_json"], [])
        ]
        if not results:
            return make_step_response(
                run_id=run_id,
                step="read_extract",
                status="failed",
                decision="reader_failed",
                decision_reason="no search results to read",
                windmill_flow_run_id=windmill_flow_run_id,
                windmill_job_id=windmill_job_id,
            )

        target = results[0]
        canonical_key = f"{family}:{stable_hash(target.url)}:v1"

        # Idempotent: check existing artifacts
        raw_art = self.store.latest_artifact(canonical_key, "raw_provider_response")
        md_art = self.store.latest_artifact(canonical_key, "reader_markdown")
        if raw_art and md_art:
            return make_step_response(
                run_id=run_id,
                step="read_extract",
                status="succeeded",
                decision="reader_succeeded",
                decision_reason="reused existing reader artifacts",
                evidence={
                    "raw_artifact_id": raw_art["id"],
                    "markdown_artifact_id": md_art["id"],
                    "canonical_key": canonical_key,
                    "reused": True,
                    "url": target.url,
                },
                windmill_flow_run_id=windmill_flow_run_id,
                windmill_job_id=windmill_job_id,
            )

        # Read from provider
        try:
            reader_result = self.reader_provider.read(target.url)
        except Exception as exc:
            return make_step_response(
                run_id=run_id,
                step="read_extract",
                status="failed",
                decision="reader_failed",
                decision_reason=f"reader provider error: {exc}",
                evidence={"url": target.url, "error": str(exc)},
                alerts=[
                    {
                        "severity": "ERROR",
                        "code": "reader_failed",
                        "message": str(exc),
                    }
                ],
                windmill_flow_run_id=windmill_flow_run_id,
                windmill_job_id=windmill_job_id,
            )

        # Persist raw provider response
        raw_relative = f"content/{canonical_key}/raw_response.json"
        raw_uri = self.store.write_artifact_file(
            raw_relative, reader_result.raw_response
        )
        raw_art = self.store.insert_artifact(
            family=family,
            url=target.url,
            canonical_key=canonical_key,
            artifact_kind="raw_provider_response",
            storage_uri=raw_uri,
            sha256=bytes_hash(reader_result.raw_response),
            content_type="application/json",
            byte_count=len(reader_result.raw_response),
            created_at=self.now_fn(),
            metadata={"provider": reader_result.provider, **reader_result.metadata},
            source_snapshot_id=snapshot["id"],
        )

        # Persist normalized markdown/text artifact
        md_bytes = reader_result.markdown.encode("utf-8")
        md_relative = f"content/{canonical_key}/reader_output.md"
        md_uri = self.store.write_artifact_file(md_relative, md_bytes)
        md_art = self.store.insert_artifact(
            family=family,
            url=target.url,
            canonical_key=canonical_key,
            artifact_kind="reader_markdown",
            storage_uri=md_uri,
            sha256=bytes_hash(md_bytes),
            content_type="text/markdown; charset=utf-8",
            byte_count=len(md_bytes),
            created_at=self.now_fn(),
            metadata={"provider": reader_result.provider},
            source_snapshot_id=snapshot["id"],
        )

        return make_step_response(
            run_id=run_id,
            step="read_extract",
            status="succeeded",
            decision="reader_succeeded",
            decision_reason="content read and persisted",
            evidence={
                "raw_artifact_id": raw_art["id"],
                "markdown_artifact_id": md_art["id"],
                "canonical_key": canonical_key,
                "reused": False,
                "url": target.url,
                "provider": reader_result.provider,
            },
            windmill_flow_run_id=windmill_flow_run_id,
            windmill_job_id=windmill_job_id,
        )

    def _step_analyze(
        self,
        *,
        run_id: str,
        read_response: dict[str, Any],
        family: str,
        snapshot_id: str,
        alerts: list[dict[str, Any]],
        windmill_flow_run_id: str | None,
        windmill_job_id: str | None,
    ) -> dict[str, Any]:
        evidence = read_response.get("evidence", {})
        canonical_key = evidence.get("canonical_key", "")
        if not canonical_key:
            return make_step_response(
                run_id=run_id,
                step="analyze",
                status="failed",
                decision="analysis_failed",
                decision_reason="no canonical key from read step",
                windmill_flow_run_id=windmill_flow_run_id,
                windmill_job_id=windmill_job_id,
            )

        # Load content from artifact
        md_art = self.store.latest_artifact(canonical_key, "reader_markdown")
        if not md_art:
            return make_step_response(
                run_id=run_id,
                step="analyze",
                status="failed",
                decision="analysis_failed",
                decision_reason="reader markdown artifact not found",
                windmill_flow_run_id=windmill_flow_run_id,
                windmill_job_id=windmill_job_id,
            )
        md_path = Path(md_art["storage_uri"])
        content = md_path.read_text("utf-8") if md_path.exists() else ""

        # Idempotent: check existing analysis artifact
        analysis_art = self.store.latest_artifact(canonical_key, "analysis_result")
        if analysis_art:
            return make_step_response(
                run_id=run_id,
                step="analyze",
                status="succeeded",
                decision="analysis_succeeded",
                decision_reason="reused existing analysis artifact",
                evidence={
                    "analysis_artifact_id": analysis_art["id"],
                    "canonical_key": canonical_key,
                    "reused": True,
                },
                windmill_flow_run_id=windmill_flow_run_id,
                windmill_job_id=windmill_job_id,
            )

        try:
            result = self.analysis_provider.analyze(content, {"family": family})
        except Exception as exc:
            return make_step_response(
                run_id=run_id,
                step="analyze",
                status="failed",
                decision="analysis_failed",
                decision_reason=f"analysis provider error: {exc}",
                evidence={"error": str(exc)},
                alerts=[
                    {
                        "severity": "ERROR",
                        "code": "analysis_failed",
                        "message": str(exc),
                    }
                ],
                windmill_flow_run_id=windmill_flow_run_id,
                windmill_job_id=windmill_job_id,
            )

        # Persist analysis
        analysis_payload = json.dumps(
            {
                "summary": result.summary,
                "key_facts": result.key_facts,
                "provider": result.provider,
            },
            indent=2,
        ).encode("utf-8")
        analysis_relative = f"content/{canonical_key}/analysis.json"
        analysis_uri = self.store.write_artifact_file(
            analysis_relative, analysis_payload
        )
        analysis_art = self.store.insert_artifact(
            family=family,
            url=evidence.get("url", ""),
            canonical_key=canonical_key,
            artifact_kind="analysis_result",
            storage_uri=analysis_uri,
            sha256=bytes_hash(analysis_payload),
            content_type="application/json",
            byte_count=len(analysis_payload),
            created_at=self.now_fn(),
            metadata={
                "provider": result.provider,
                "summary_preview": result.summary[:200],
            },
            source_snapshot_id=snapshot_id,
        )

        return make_step_response(
            run_id=run_id,
            step="analyze",
            status="succeeded",
            decision="analysis_succeeded",
            decision_reason="analysis completed and persisted",
            evidence={
                "analysis_artifact_id": analysis_art["id"],
                "canonical_key": canonical_key,
                "reused": False,
                "provider": result.provider,
                "summary_preview": result.summary[:200],
            },
            windmill_flow_run_id=windmill_flow_run_id,
            windmill_job_id=windmill_job_id,
        )
