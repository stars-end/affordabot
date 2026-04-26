"""San Jose persisted pipeline POC.

This module is intentionally small, but it mirrors the proposed
Windmill-driven persisted pipeline boundary:

- Windmill/manual trigger owns scheduling and run initiation.
- Backend code owns business policy, freshness gating, idempotency, and
  durable evidence records.
- Search snapshots and content artifacts are persisted before downstream use.

The POC uses SQLite so it can run in any agent worktree without Railway
Postgres credentials. Table names and record shapes intentionally match the
MVP Postgres contract from bd-jxclm.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import textwrap
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4


CONTRACT_VERSION = "persisted-pipeline-poc.v1"
FAMILY = "san-jose-city-council-minutes"
QUERY = "San Jose City Council meeting minutes official Legistar"
PROVIDER = "fixed-official-legistar"
FRESHNESS_POLICY_NAME = "official_minutes_daily_36h"
FRESHNESS_TTL_HOURS = 36
DEFAULT_EVENT_ID = 7616
DEFAULT_EVENT_API_URL = (
    f"https://webapi.legistar.com/v1/sanjose/events/{DEFAULT_EVENT_ID}"
)
DEFAULT_EVENT_DETAIL_URL = (
    "https://sanjose.legistar.com/MeetingDetail.aspx?"
    "LEGID=7616&GID=317&G=920296E4-80BE-4CA2-A78F-32C5EFCF78AF"
)


FIXTURE_EVENT = {
    "EventId": DEFAULT_EVENT_ID,
    "EventBodyName": "City Council",
    "EventDate": "2026-04-07T00:00:00",
    "EventTime": "1:30 PM",
    "EventLocation": "Council Chambers",
    "EventMinutesStatusName": "Draft",
    "EventAgendaStatusName": "Final",
    "EventAgendaFile": (
        "https://legistar.granicus.com/sanjose/meetings/2026/4/"
        "7616_A_City_Council_26-04-07_Amended_Agenda.pdf"
    ),
    "EventMinutesFile": None,
    "EventInSiteURL": DEFAULT_EVENT_DETAIL_URL,
    "EventComment": "Closed Session at 9:30 a.m.",
}


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
class FetchResult:
    url: str
    body: bytes
    content_type: str
    source: str


class FixedSanJoseMinutesSearchProvider:
    """Fixed official-result provider for the capture-only vertical slice."""

    def search(self, query: str) -> list[SearchResult]:
        return [
            SearchResult(
                title="San Jose City Council minutes status - April 7, 2026",
                url=DEFAULT_EVENT_API_URL,
                snippet=(
                    "Official San Jose Legistar event record with City Council "
                    "minutes status and meeting detail link."
                ),
                domain="webapi.legistar.com",
                content=(
                    "City Council meeting minutes status, agenda pointer, and "
                    "official meeting detail URL."
                ),
                metadata={
                    "event_id": DEFAULT_EVENT_ID,
                    "jurisdiction": "San Jose, CA",
                    "asset_class": "minutes",
                    "official_detail_url": DEFAULT_EVENT_DETAIL_URL,
                },
            )
        ]


class FailingSearchProvider:
    """Provider used by the stale-backed failure drill."""

    def __init__(self, message: str = "simulated searxng outage"):
        self.message = message

    def search(self, query: str) -> list[SearchResult]:
        raise RuntimeError(self.message)


class HttpOrFixtureFetcher:
    """Fetch official content, with fixture fallback for offline verification."""

    def __init__(self, timeout_seconds: int = 20, network_enabled: bool = True):
        self.timeout_seconds = timeout_seconds
        self.network_enabled = network_enabled

    def fetch(self, url: str) -> FetchResult:
        if self.network_enabled:
            try:
                request = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": (
                            "AffordabotPersistedPipelinePOC/1.0 "
                            "(capture-only verification)"
                        )
                    },
                )
                with urllib.request.urlopen(
                    request, timeout=self.timeout_seconds
                ) as response:
                    body = response.read()
                    content_type = response.headers.get(
                        "content-type", "application/octet-stream"
                    )
                    return FetchResult(
                        url=url,
                        body=body,
                        content_type=content_type,
                        source="live_http",
                    )
            except Exception:
                pass

        return FetchResult(
            url=url,
            body=json.dumps(FIXTURE_EVENT, indent=2).encode("utf-8"),
            content_type="application/json",
            source="fixture_fallback",
        )


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
                started_at TEXT NOT NULL,
                completed_at TEXT,
                result_json TEXT,
                alerts_json TEXT NOT NULL DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS pipeline_steps (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES pipeline_runs(id),
                step_name TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                input_json TEXT NOT NULL DEFAULT '{}',
                output_json TEXT NOT NULL DEFAULT '{}',
                freshness_policy_name TEXT,
                freshness_family TEXT,
                freshness_observed_at TEXT,
                freshness_expires_at TEXT,
                stale_backed INTEGER NOT NULL DEFAULT 0,
                upstream_failure_json TEXT,
                idempotency_key TEXT,
                artifact_ref TEXT
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

    def create_run(
        self,
        run_label: str,
        triggered_by: str,
        now: datetime,
        jurisdiction: str = "San Jose, CA",
    ) -> str:
        run_id = f"run_{uuid4().hex}"
        self.conn.execute(
            """
            INSERT INTO pipeline_runs (
                id, run_label, jurisdiction, target_family, status, triggered_by,
                contract_version, started_at, alerts_json
            )
            VALUES (?, ?, ?, ?, 'running', ?, ?, ?, '[]')
            """,
            (
                run_id,
                run_label,
                jurisdiction,
                FAMILY,
                triggered_by,
                CONTRACT_VERSION,
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

    def start_step(
        self,
        run_id: str,
        step_name: str,
        now: datetime,
        input_payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> str:
        step_id = f"step_{uuid4().hex}"
        self.conn.execute(
            """
            INSERT INTO pipeline_steps (
                id, run_id, step_name, status, started_at, input_json,
                idempotency_key
            )
            VALUES (?, ?, ?, 'running', ?, ?, ?)
            """,
            (
                step_id,
                run_id,
                step_name,
                iso(now),
                json_dumps(input_payload or {}),
                idempotency_key,
            ),
        )
        self.conn.commit()
        return step_id

    def complete_step(
        self,
        step_id: str,
        status: str,
        now: datetime,
        output_payload: dict[str, Any],
        *,
        freshness_observed_at: datetime | None = None,
        freshness_expires_at: datetime | None = None,
        stale_backed: bool = False,
        upstream_failure: dict[str, Any] | None = None,
        artifact_ref: str | None = None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE pipeline_steps
            SET status = ?,
                completed_at = ?,
                output_json = ?,
                freshness_policy_name = ?,
                freshness_family = ?,
                freshness_observed_at = ?,
                freshness_expires_at = ?,
                stale_backed = ?,
                upstream_failure_json = ?,
                artifact_ref = ?
            WHERE id = ?
            """,
            (
                status,
                iso(now),
                json_dumps(output_payload),
                FRESHNESS_POLICY_NAME,
                FAMILY,
                iso(freshness_observed_at) if freshness_observed_at else None,
                iso(freshness_expires_at) if freshness_expires_at else None,
                1 if stale_backed else 0,
                json_dumps(upstream_failure) if upstream_failure else None,
                artifact_ref,
                step_id,
            ),
        )
        self.conn.commit()

    def insert_snapshot(
        self,
        *,
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
        rows = [result.to_dict() for result in results]
        self.conn.execute(
            """
            INSERT INTO search_result_snapshots (
                id, family, query, provider, query_hash, status, observed_at,
                expires_at, stale_backed, provider_failure_json, result_count,
                results_json, source_snapshot_id
            )
            VALUES (?, ?, ?, ?, ?, 'succeeded', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                FAMILY,
                query,
                provider,
                stable_hash(query),
                iso(observed_at),
                iso(expires_at),
                1 if stale_backed else 0,
                json_dumps(provider_failure) if provider_failure else None,
                len(rows),
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

    def latest_fresh_snapshot(self, now: datetime) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT *
            FROM search_result_snapshots
            WHERE family = ?
              AND status = 'succeeded'
              AND expires_at > ?
              AND result_count > 0
            ORDER BY observed_at DESC
            LIMIT 1
            """,
            (FAMILY, iso(now)),
        ).fetchone()
        return dict(row) if row else None

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

    def row_counts(self) -> dict[str, int]:
        counts = {}
        for table in (
            "pipeline_runs",
            "pipeline_steps",
            "search_result_snapshots",
            "content_artifacts",
        ):
            row = self.conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
            counts[table] = int(row["count"])
        return counts

    def rows(self, table: str) -> list[dict[str, Any]]:
        return [dict(row) for row in self.conn.execute(f"SELECT * FROM {table}")]


class SanJosePersistedPipelinePOC:
    def __init__(
        self,
        store: PersistedPipelineStore,
        search_provider: Any,
        fetcher: Any,
        *,
        now_fn: Any = utc_now,
    ):
        self.store = store
        self.search_provider = search_provider
        self.fetcher = fetcher
        self.now_fn = now_fn

    def run(
        self,
        *,
        run_label: str,
        triggered_by: str,
        prefer_cached_search: bool = False,
        allow_stale_fallback: bool = True,
    ) -> dict[str, Any]:
        alerts: list[dict[str, Any]] = []
        started_at = self.now_fn()
        run_id = self.store.create_run(run_label, triggered_by, started_at)
        try:
            snapshot, search_step = self._materialize_search(
                run_id=run_id,
                prefer_cached_search=prefer_cached_search,
                allow_stale_fallback=allow_stale_fallback,
                alerts=alerts,
            )
            artifacts, read_step = self._fetch_and_extract(
                run_id=run_id,
                snapshot=snapshot,
                alerts=alerts,
            )
            result = {
                "run_id": run_id,
                "run_label": run_label,
                "status": "completed",
                "contract_version": CONTRACT_VERSION,
                "snapshot_id": snapshot["id"],
                "stale_backed": bool(snapshot["stale_backed"]),
                "search_step": search_step,
                "read_step": read_step,
                "artifacts": artifacts,
            }
            self.store.complete_run(run_id, "completed", result, alerts, self.now_fn())
            return result
        except Exception as exc:
            failure = {
                "run_id": run_id,
                "run_label": run_label,
                "status": "failed",
                "error": str(exc),
                "contract_version": CONTRACT_VERSION,
            }
            alerts.append(
                {
                    "severity": "ERROR",
                    "code": "pipeline_failed",
                    "message": str(exc),
                }
            )
            self.store.complete_run(run_id, "failed", failure, alerts, self.now_fn())
            return failure

    def _materialize_search(
        self,
        *,
        run_id: str,
        prefer_cached_search: bool,
        allow_stale_fallback: bool,
        alerts: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        now = self.now_fn()
        step_id = self.store.start_step(
            run_id,
            "search-materialize",
            now,
            input_payload={
                "query": QUERY,
                "provider": PROVIDER,
                "prefer_cached_search": prefer_cached_search,
            },
            idempotency_key=f"search-materialize:{FAMILY}:{stable_hash(QUERY)}",
        )

        if prefer_cached_search:
            latest = self.store.latest_fresh_snapshot(now)
            if latest:
                step = {
                    "step_id": step_id,
                    "reused_snapshot_id": latest["id"],
                    "result_count": latest["result_count"],
                    "stale_backed": False,
                }
                self.store.complete_step(
                    step_id,
                    "succeeded",
                    self.now_fn(),
                    step,
                    freshness_observed_at=from_iso(latest["observed_at"]),
                    freshness_expires_at=from_iso(latest["expires_at"]),
                )
                return latest, step

        try:
            results = self.search_provider.search(QUERY)
        except Exception as exc:
            failure = {
                "type": type(exc).__name__,
                "message": str(exc),
                "provider": PROVIDER,
            }
            fallback = self.store.latest_fresh_snapshot(now)
            if not allow_stale_fallback or not fallback:
                self.store.complete_step(
                    step_id,
                    "failed",
                    self.now_fn(),
                    {"error": failure, "stale_fallback_available": bool(fallback)},
                    upstream_failure=failure,
                )
                raise RuntimeError(
                    "search provider failed and no fresh fallback snapshot is available"
                ) from exc

            copied = [
                SearchResult.from_dict(row)
                for row in json_loads(fallback["results_json"], [])
            ]
            snapshot = self.store.insert_snapshot(
                query=QUERY,
                provider=PROVIDER,
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
                    "message": (
                        "Search provider failed; using latest fresh snapshot "
                        f"{fallback['id']}."
                    ),
                }
            )
            step = {
                "step_id": step_id,
                "snapshot_id": snapshot["id"],
                "source_snapshot_id": fallback["id"],
                "result_count": snapshot["result_count"],
                "stale_backed": True,
            }
            self.store.complete_step(
                step_id,
                "succeeded",
                self.now_fn(),
                step,
                freshness_observed_at=from_iso(snapshot["observed_at"]),
                freshness_expires_at=from_iso(snapshot["expires_at"]),
                stale_backed=True,
                upstream_failure=failure,
            )
            return snapshot, step

        if not results:
            failure = {
                "type": "ZeroResults",
                "message": "provider returned zero results",
                "provider": PROVIDER,
            }
            self.store.complete_step(
                step_id,
                "failed",
                self.now_fn(),
                {"error": failure},
                upstream_failure=failure,
            )
            raise RuntimeError("search provider returned zero results")

        snapshot = self.store.insert_snapshot(
            query=QUERY,
            provider=PROVIDER,
            results=results,
            observed_at=now,
            expires_at=now + timedelta(hours=FRESHNESS_TTL_HOURS),
        )
        step = {
            "step_id": step_id,
            "snapshot_id": snapshot["id"],
            "result_count": snapshot["result_count"],
            "stale_backed": False,
        }
        self.store.complete_step(
            step_id,
            "succeeded",
            self.now_fn(),
            step,
            freshness_observed_at=from_iso(snapshot["observed_at"]),
            freshness_expires_at=from_iso(snapshot["expires_at"]),
        )
        return snapshot, step

    def _fetch_and_extract(
        self,
        *,
        run_id: str,
        snapshot: dict[str, Any],
        alerts: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        now = self.now_fn()
        results = [
            SearchResult.from_dict(row)
            for row in json_loads(snapshot["results_json"], [])
        ]
        if not results:
            raise RuntimeError(f"snapshot {snapshot['id']} has zero results")

        result = results[0]
        canonical_key = f"{FAMILY}:event-{result.metadata.get('event_id')}:v1"
        step_id = self.store.start_step(
            run_id,
            "read-fetch-extract",
            now,
            input_payload={
                "snapshot_id": snapshot["id"],
                "url": result.url,
                "canonical_key": canonical_key,
            },
            idempotency_key=f"read-fetch-extract:{canonical_key}",
        )

        raw = self.store.latest_artifact(canonical_key, "raw_event_json")
        markdown = self.store.latest_artifact(canonical_key, "minutes_markdown")
        if raw and markdown:
            step = {
                "step_id": step_id,
                "raw_artifact_id": raw["id"],
                "markdown_artifact_id": markdown["id"],
                "reused": True,
                "snapshot_id": snapshot["id"],
            }
            self.store.complete_step(
                step_id,
                "succeeded",
                self.now_fn(),
                step,
                freshness_observed_at=from_iso(snapshot["observed_at"]),
                freshness_expires_at=from_iso(snapshot["expires_at"]),
                stale_backed=bool(snapshot["stale_backed"]),
                artifact_ref=markdown["storage_uri"],
            )
            return {"raw": raw, "markdown": markdown}, step

        fetched = self.fetcher.fetch(result.url)
        if fetched.source == "fixture_fallback":
            alerts.append(
                {
                    "severity": "WARN",
                    "code": "fixture_fetch_fallback",
                    "message": "Live fetch failed or was disabled; fixture used.",
                }
            )

        event_payload = _parse_event_payload(fetched.body)
        markdown_bytes = _event_payload_to_markdown(
            event_payload=event_payload,
            source_url=result.url,
            search_result=result,
            fetch_source=fetched.source,
        ).encode("utf-8")
        raw_relative = f"content/{canonical_key}/raw_event.json"
        markdown_relative = f"content/{canonical_key}/minutes.md"
        raw_uri = self.store.write_artifact_file(raw_relative, fetched.body)
        markdown_uri = self.store.write_artifact_file(markdown_relative, markdown_bytes)

        raw_artifact = self.store.insert_artifact(
            family=FAMILY,
            url=result.url,
            canonical_key=canonical_key,
            artifact_kind="raw_event_json",
            storage_uri=raw_uri,
            sha256=bytes_hash(fetched.body),
            content_type=fetched.content_type,
            byte_count=len(fetched.body),
            created_at=self.now_fn(),
            metadata={
                "fetch_source": fetched.source,
                "official_detail_url": event_payload.get("EventInSiteURL"),
            },
            source_snapshot_id=snapshot["id"],
        )
        markdown_artifact = self.store.insert_artifact(
            family=FAMILY,
            url=event_payload.get("EventInSiteURL") or result.url,
            canonical_key=canonical_key,
            artifact_kind="minutes_markdown",
            storage_uri=markdown_uri,
            sha256=bytes_hash(markdown_bytes),
            content_type="text/markdown; charset=utf-8",
            byte_count=len(markdown_bytes),
            created_at=self.now_fn(),
            metadata={
                "fetch_source": fetched.source,
                "source_event_id": event_payload.get("EventId"),
                "minutes_status": event_payload.get("EventMinutesStatusName"),
            },
            source_snapshot_id=snapshot["id"],
        )
        step = {
            "step_id": step_id,
            "raw_artifact_id": raw_artifact["id"],
            "markdown_artifact_id": markdown_artifact["id"],
            "reused": False,
            "snapshot_id": snapshot["id"],
            "fetch_source": fetched.source,
        }
        self.store.complete_step(
            step_id,
            "succeeded",
            self.now_fn(),
            step,
            freshness_observed_at=from_iso(snapshot["observed_at"]),
            freshness_expires_at=from_iso(snapshot["expires_at"]),
            stale_backed=bool(snapshot["stale_backed"]),
            artifact_ref=markdown_artifact["storage_uri"],
        )
        return {"raw": raw_artifact, "markdown": markdown_artifact}, step


def _parse_event_payload(body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body.decode("utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return {
        **FIXTURE_EVENT,
        "RawBodyPreview": body[:2000].decode("utf-8", errors="replace"),
    }


def _event_payload_to_markdown(
    *,
    event_payload: dict[str, Any],
    source_url: str,
    search_result: SearchResult,
    fetch_source: str,
) -> str:
    minutes_file = event_payload.get("EventMinutesFile") or "not published"
    agenda_file = event_payload.get("EventAgendaFile") or "not published"
    body = f"""
    # San Jose City Council Meeting Minutes Capture

    - Jurisdiction: San Jose, CA
    - Event ID: {event_payload.get("EventId", "unknown")}
    - Body: {event_payload.get("EventBodyName", "unknown")}
    - Event date: {event_payload.get("EventDate", "unknown")}
    - Event time: {event_payload.get("EventTime", "unknown")}
    - Location: {event_payload.get("EventLocation", "unknown")}
    - Minutes status: {event_payload.get("EventMinutesStatusName", "unknown")}
    - Minutes file: {minutes_file}
    - Agenda status: {event_payload.get("EventAgendaStatusName", "unknown")}
    - Agenda file: {agenda_file}
    - Official detail URL: {event_payload.get("EventInSiteURL") or search_result.metadata.get("official_detail_url")}
    - Source API URL: {source_url}
    - Fetch source: {fetch_source}

    ## Extracted Notes

    {event_payload.get("EventComment") or "No event comment was published."}

    ## Search Evidence

    {search_result.title}

    {search_result.snippet}
    """
    return textwrap.dedent(body).strip() + "\n"


def run_three_pass_verification(
    *,
    store: PersistedPipelineStore,
    network_enabled: bool = True,
) -> dict[str, Any]:
    baseline = SanJosePersistedPipelinePOC(
        store,
        FixedSanJoseMinutesSearchProvider(),
        HttpOrFixtureFetcher(network_enabled=network_enabled),
    ).run(
        run_label="baseline-materialize",
        triggered_by="manual:poc_sanjose_persisted_pipeline",
    )
    replay = SanJosePersistedPipelinePOC(
        store,
        FixedSanJoseMinutesSearchProvider(),
        HttpOrFixtureFetcher(network_enabled=network_enabled),
    ).run(
        run_label="idempotent-replay",
        triggered_by="manual:poc_sanjose_persisted_pipeline",
        prefer_cached_search=True,
    )
    failure_drill = SanJosePersistedPipelinePOC(
        store,
        FailingSearchProvider(),
        HttpOrFixtureFetcher(network_enabled=network_enabled),
    ).run(
        run_label="stale-backed-search-failure-drill",
        triggered_by="manual:poc_sanjose_persisted_pipeline",
        allow_stale_fallback=True,
    )
    return {
        "contract_version": CONTRACT_VERSION,
        "runs": [baseline, replay, failure_drill],
        "row_counts": store.row_counts(),
        "checks": evaluate_checks(store, [baseline, replay, failure_drill]),
    }


def evaluate_checks(
    store: PersistedPipelineStore, runs: list[dict[str, Any]]
) -> dict[str, bool]:
    counts = store.row_counts()
    replay = runs[1]
    failure_drill = runs[2]
    return {
        "all_runs_completed": all(run.get("status") == "completed" for run in runs),
        "four_contract_tables_populated": all(
            counts[name] > 0
            for name in (
                "pipeline_runs",
                "pipeline_steps",
                "search_result_snapshots",
                "content_artifacts",
            )
        ),
        "second_run_reused_search_snapshot": bool(
            replay.get("search_step", {}).get("reused_snapshot_id")
        ),
        "second_run_reused_content_artifacts": bool(
            replay.get("read_step", {}).get("reused")
        ),
        "failure_drill_stale_backed": bool(failure_drill.get("stale_backed")),
        "failure_drill_completed": failure_drill.get("status") == "completed",
        "content_artifact_pair_written_once": counts["content_artifacts"] == 2,
    }


def render_markdown_report(
    *,
    summary: dict[str, Any],
    store: PersistedPipelineStore,
    db_path: Path,
    report_path: Path,
) -> str:
    checks = summary["checks"]
    verdict = "PASS" if all(checks.values()) else "FAIL"
    rows = []
    for run in summary["runs"]:
        rows.append(
            "| {label} | {status} | {snapshot} | {stale} | {search_reuse} | {read_reuse} |".format(
                label=run.get("run_label"),
                status=run.get("status"),
                snapshot=run.get("snapshot_id"),
                stale=run.get("stale_backed"),
                search_reuse=run.get("search_step", {}).get("reused_snapshot_id")
                or "no",
                read_reuse=run.get("read_step", {}).get("reused"),
            )
        )

    artifact_rows = []
    for artifact in store.rows("content_artifacts"):
        artifact_rows.append(
            "| {kind} | {id} | {bytes} | `{uri}` |".format(
                kind=artifact["artifact_kind"],
                id=artifact["id"],
                bytes=artifact["bytes"],
                uri=artifact["storage_uri"],
            )
        )

    check_rows = [
        f"- [{'x' if passed else ' '}] {name}: {passed}"
        for name, passed in checks.items()
    ]
    counts = summary["row_counts"]
    return "\n".join(
        [
            "# San Jose Persisted Pipeline POC Evidence",
            "",
            f"VERDICT: {verdict}",
            "BEADS_SUBTASK: bd-jxclm.12",
            f"CONTRACT_VERSION: {summary['contract_version']}",
            "",
            "## Scope",
            "",
            "Capture-only vertical slice for San Jose City Council meeting minutes status:",
            "fixed official search materialization, freshness gating, read/fetch/extract,",
            "persisted artifacts, idempotent replay, and stale-backed search failure drill.",
            "",
            "## Commands",
            "",
            "```bash",
            "python3 backend/scripts/verification/poc_sanjose_persisted_pipeline.py \\",
            "  --reset \\",
            "  --out-dir backend/artifacts/poc_sanjose_persisted_pipeline",
            "```",
            "",
            "## Persistence Evidence",
            "",
            f"- SQLite proof DB: `{db_path}`",
            f"- Evidence report: `{report_path}`",
            f"- pipeline_runs: {counts['pipeline_runs']}",
            f"- pipeline_steps: {counts['pipeline_steps']}",
            f"- search_result_snapshots: {counts['search_result_snapshots']}",
            f"- content_artifacts: {counts['content_artifacts']}",
            "",
            "## Run Results",
            "",
            "| Run | Status | Snapshot | Stale backed | Search reuse | Read reuse |",
            "| --- | --- | --- | --- | --- | --- |",
            *rows,
            "",
            "## Content Artifacts",
            "",
            "| Kind | Artifact ID | Bytes | Storage URI |",
            "| --- | --- | --- | --- |",
            *artifact_rows,
            "",
            "## Checks",
            "",
            *check_rows,
            "",
            "## Boundary Notes",
            "",
            "- Backend code owns freshness policy, stale fallback, idempotency keys, and",
            "  alert content.",
            "- Windmill/manual trigger is represented by the `triggered_by` field; it",
            "  does not own business decisions.",
            "- A zero-result search is treated as failure, not as a valid empty state.",
            "- The stale-backed drill records provider failure on both the snapshot and",
            "  the step while still completing from the latest fresh snapshot.",
            "",
        ]
    )
