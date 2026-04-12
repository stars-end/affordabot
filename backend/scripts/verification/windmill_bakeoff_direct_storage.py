#!/usr/bin/env python3
"""Windmill-shaped Path A bakeoff runner: direct storage writes without backend endpoints."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import textwrap
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


CONTRACT_VERSION = "2026-04-12.windmill-storage-bakeoff.v1"
ARCH_PATH = "windmill_direct_storage"
DEFAULT_STATE_DIR = (
    Path("docs/poc/windmill-storage-bakeoff/path-a-direct-storage/runtime_state")
)
DEFAULT_EVIDENCE_DIR = Path("docs/poc/windmill-storage-bakeoff/path-a-direct-storage")
DEFAULT_SEARX_QUERY = "San Jose CA city council meeting minutes"
DEFAULT_SOURCE_FAMILY = "meeting_minutes"
DEFAULT_JURISDICTION = "San Jose CA"

STATUS_FRESH = "fresh"
STATUS_STALE_USABLE = "stale_but_usable"
STATUS_STALE_BLOCKED = "stale_blocked"
STATUS_EMPTY = "empty_result"
STATUS_SOURCE_ERROR = "source_error"
STATUS_READER_ERROR = "reader_error"
STATUS_STORAGE_ERROR = "storage_error"
STATUS_ANALYSIS_ERROR = "analysis_error"
STATUS_SUCCEEDED = "succeeded"

TERMINAL_FAILURE_STATUSES = {
    STATUS_SOURCE_ERROR,
    STATUS_READER_ERROR,
    STATUS_STORAGE_ERROR,
    STATUS_ANALYSIS_ERROR,
    STATUS_STALE_BLOCKED,
}

DEFAULT_SEARX_FIXTURE: dict[str, Any] = {
    "query": DEFAULT_SEARX_QUERY,
    "number_of_results": 3,
    "results": [
        {
            "title": "City Council Meetings - City of San Jose",
            "url": "https://www.sanjoseca.gov/your-government/departments-offices/city-clerk/city-council-meetings",
            "content": "Public agendas and minutes for San Jose City Council meetings.",
        },
        {
            "title": "Meeting Agenda and Minutes | City of San Jose",
            "url": "https://sanjose.legistar.com/Calendar.aspx",
            "content": "Calendar portal with agendas, minutes, and archived packets.",
        },
        {
            "title": "San Jose Open Data - Council Minutes",
            "url": "https://data.sanjoseca.gov/",
            "content": "Open data portal with civic documents including meeting records.",
        },
    ],
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso(value: datetime | None = None) -> str:
    ts = value or now_utc()
    return ts.astimezone(timezone.utc).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def canonical_document_key(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")
    path = parsed.path.rstrip("/") or "/"
    key = f"{host}{path}"
    return key.lower()


def chunk_text(text: str, chunk_size: int = 450, overlap: int = 80) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [cleaned]
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(cleaned):
            break
        start = max(0, end - overlap)
    return chunks


def deterministic_embedding(text: str, dims: int = 12) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    vec: list[float] = []
    for i in range(dims):
        raw = digest[i] / 255.0
        vec.append((raw * 2.0) - 1.0)
    return vec


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(y * y for y in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


@dataclass
class ArtifactRef:
    ref: str
    key: str
    sha256: str
    bytes: int
    content_type: str


class DirectObjectStore:
    """Deterministic MinIO-compatible local adapter with stable refs."""

    def __init__(self, root: Path):
        self.root = root
        self.bucket = "affordabot-artifacts"
        self.index_path = self.root / "object_store_index.json"
        self.objects_dir = self.root / "objects"
        self.index: dict[str, Any] = load_json(self.index_path, {"objects": {}})
        self.objects_dir.mkdir(parents=True, exist_ok=True)

    def put(
        self,
        key: str,
        payload: bytes,
        content_type: str = "application/octet-stream",
        fail: bool = False,
    ) -> ArtifactRef:
        if fail:
            raise RuntimeError("simulated_storage_error")
        sha = hashlib.sha256(payload).hexdigest()
        ext = ".json" if content_type == "application/json" else ".txt"
        object_name = f"{sha}{ext}"
        object_path = self.objects_dir / object_name
        if not object_path.exists():
            object_path.write_bytes(payload)
        ref = f"minio://{self.bucket}/{key}#{sha}"
        self.index["objects"][key] = {
            "ref": ref,
            "sha256": sha,
            "bytes": len(payload),
            "content_type": content_type,
            "object_path": str(object_path),
            "updated_at": utc_iso(),
        }
        write_json(self.index_path, self.index)
        return ArtifactRef(
            ref=ref,
            key=key,
            sha256=sha,
            bytes=len(payload),
            content_type=content_type,
        )

    def get(self, key: str) -> bytes:
        record = self.index["objects"][key]
        return Path(record["object_path"]).read_bytes()

    def count(self) -> int:
        return len(self.index.get("objects", {}))

    def snapshot(self) -> dict[str, Any]:
        return {
            "object_count": self.count(),
            "keys": sorted(self.index.get("objects", {}).keys()),
        }


class DirectVectorStore:
    """Deterministic pgvector-compatible adapter with idempotent upsert."""

    def __init__(self, root: Path):
        self.path = root / "vector_store.json"
        self.data: dict[str, Any] = load_json(self.path, {"chunks": {}})

    def upsert_document_chunks(
        self,
        canonical_key: str,
        artifact_ref: str,
        text: str,
        metadata: dict[str, Any],
    ) -> dict[str, int]:
        chunks = chunk_text(text)
        created = 0
        reused = 0
        for idx, chunk in enumerate(chunks):
            chunk_hash = sha256_text(chunk)
            chunk_id = f"{canonical_key}::chunk-{idx}::{chunk_hash[:12]}"
            if chunk_id in self.data["chunks"]:
                reused += 1
                continue
            self.data["chunks"][chunk_id] = {
                "chunk_id": chunk_id,
                "canonical_document_key": canonical_key,
                "content": chunk,
                "embedding": deterministic_embedding(chunk),
                "artifact_ref": artifact_ref,
                "metadata": metadata,
                "created_at": utc_iso(),
            }
            created += 1
        write_json(self.path, self.data)
        return {"created": created, "reused": reused, "total": len(chunks)}

    def query(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        query_vec = deterministic_embedding(query)
        scored: list[tuple[float, dict[str, Any]]] = []
        for chunk in self.data["chunks"].values():
            score = cosine_similarity(query_vec, chunk["embedding"])
            scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        results: list[dict[str, Any]] = []
        for score, chunk in scored[:top_k]:
            payload = dict(chunk)
            payload["score"] = score
            results.append(payload)
        return results

    def count(self) -> int:
        return len(self.data.get("chunks", {}))

    def snapshot(self) -> dict[str, Any]:
        return {
            "chunk_count": self.count(),
            "chunk_ids": sorted(self.data.get("chunks", {}).keys()),
        }


class DirectRelationalStore:
    """Deterministic Postgres-like adapter for snapshots/documents/analysis rows."""

    def __init__(self, root: Path):
        self.path = root / "relational_store.json"
        self.data: dict[str, Any] = load_json(
            self.path,
            {
                "search_snapshots": {},
                "documents": {},
                "analyses": {},
                "runs": {},
            },
        )

    def upsert_search_snapshot(
        self,
        idempotency_key: str,
        query: str,
        payload: dict[str, Any],
        artifact_ref: str,
        status: str,
    ) -> dict[str, Any]:
        normalized_results = [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
            }
            for item in payload.get("results", [])
        ]
        snapshot_hash = sha256_text(json.dumps(normalized_results, sort_keys=True))
        snapshot_id = f"{idempotency_key}::{snapshot_hash[:16]}"
        exists = snapshot_id in self.data["search_snapshots"]
        row = self.data["search_snapshots"].setdefault(
            snapshot_id,
            {
                "snapshot_id": snapshot_id,
                "idempotency_key": idempotency_key,
                "query": query,
                "status": status,
                "snapshot_hash": snapshot_hash,
                "result_count": len(normalized_results),
                "artifact_ref": artifact_ref,
                "created_at": utc_iso(),
                "updated_at": utc_iso(),
            },
        )
        row["updated_at"] = utc_iso()
        row["artifact_ref"] = artifact_ref
        row["status"] = status
        write_json(self.path, self.data)
        return {"snapshot_id": snapshot_id, "created": not exists, "row": row}

    def upsert_document(
        self,
        canonical_key: str,
        title: str,
        source_url: str,
        reader_artifact_ref: str,
        content_hash: str,
    ) -> dict[str, Any]:
        exists = canonical_key in self.data["documents"]
        row = self.data["documents"].setdefault(
            canonical_key,
            {
                "canonical_document_key": canonical_key,
                "title": title,
                "source_url": source_url,
                "reader_artifact_ref": reader_artifact_ref,
                "content_hash": content_hash,
                "first_seen_at": utc_iso(),
            },
        )
        row["reader_artifact_ref"] = reader_artifact_ref
        row["content_hash"] = content_hash
        row["updated_at"] = utc_iso()
        write_json(self.path, self.data)
        return {"created": not exists, "row": row}

    def upsert_analysis(
        self, idempotency_key: str, analysis_payload: dict[str, Any], artifact_ref: str
    ) -> dict[str, Any]:
        exists = idempotency_key in self.data["analyses"]
        row = self.data["analyses"].setdefault(
            idempotency_key,
            {
                "idempotency_key": idempotency_key,
                "analysis": analysis_payload,
                "artifact_ref": artifact_ref,
                "first_written_at": utc_iso(),
            },
        )
        row["analysis"] = analysis_payload
        row["artifact_ref"] = artifact_ref
        row["updated_at"] = utc_iso()
        write_json(self.path, self.data)
        return {"created": not exists, "row": row}

    def write_run(self, run_id: str, payload: dict[str, Any]) -> None:
        self.data["runs"][run_id] = payload
        write_json(self.path, self.data)

    def previous_snapshot_time(self, idempotency_key: str) -> datetime | None:
        rows = [
            row
            for row in self.data["search_snapshots"].values()
            if row["idempotency_key"] == idempotency_key
        ]
        if not rows:
            return None
        latest = max(rows, key=lambda row: row.get("updated_at", row["created_at"]))
        return datetime.fromisoformat(latest.get("updated_at", latest["created_at"]))

    def count_snapshots(self) -> int:
        return len(self.data["search_snapshots"])

    def count_documents(self) -> int:
        return len(self.data["documents"])

    def count_analyses(self) -> int:
        return len(self.data["analyses"])

    def snapshot(self) -> dict[str, Any]:
        return {
            "search_snapshot_count": self.count_snapshots(),
            "document_count": self.count_documents(),
            "analysis_count": self.count_analyses(),
        }


class SearxClient:
    """SearXNG-compatible search adapter with deterministic fallback fixture."""

    def __init__(self, endpoint: str | None = None):
        self.endpoint = endpoint

    def search(
        self,
        query: str,
        limit: int = 5,
        force_failure: bool = False,
    ) -> dict[str, Any]:
        if force_failure:
            raise RuntimeError("simulated_searx_failure")

        if self.endpoint:
            params = urlencode({"q": query, "format": "json"})
            url = f"{self.endpoint.rstrip('/')}" + f"?{params}"
            request = Request(url, method="GET")
            try:
                with urlopen(request, timeout=20) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except (HTTPError, URLError, TimeoutError) as exc:
                raise RuntimeError(f"live_searx_unreachable: {exc}") from exc
        else:
            payload = DEFAULT_SEARX_FIXTURE
        payload["results"] = payload.get("results", [])[:limit]
        return payload


class ReaderClient:
    """Z.ai direct reader contract shape with deterministic fallback."""

    def __init__(self, allow_live: bool = False):
        self.allow_live = allow_live
        self.api_key = os.getenv("ZAI_API_KEY")
        self.endpoint = "https://api.z.ai/api/coding/paas/v4/reader"

    def read(self, url: str, force_failure: bool = False) -> dict[str, Any]:
        if force_failure:
            raise RuntimeError("simulated_reader_failure")
        if self.allow_live and self.api_key:
            request = Request(
                self.endpoint,
                data=json.dumps({"url": url, "extract_main": True}).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urlopen(request, timeout=45) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    data = payload.get("reader_result", payload)
                    return {
                        "mode": "live",
                        "title": data.get("title") or "Untitled",
                        "content": data.get("content") or "",
                        "url": url,
                    }
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"live_reader_failed: {exc}") from exc
        text = textwrap.dedent(
            f"""
            # San Jose City Council Minutes (Deterministic Reader)

            Source URL: {url}

            Agenda highlights:
            - Approved transit corridor grant allocation updates.
            - Discussed affordable housing permit acceleration.
            - Published meeting minutes and attachments for public review.
            """
        ).strip()
        return {"mode": "deterministic", "title": "San Jose Minutes", "content": text, "url": url}


class AnalysisClient:
    """Z.ai LLM contract shape with deterministic analysis fallback."""

    def __init__(self, allow_live: bool = False):
        self.allow_live = allow_live
        self.api_key = os.getenv("ZAI_API_KEY")
        self.endpoint = "https://api.z.ai/api/coding/paas/v4/chat/completions"
        self.model = os.getenv("LLM_MODEL_RESEARCH", "glm-4.7")

    def analyze(
        self,
        prompt: str,
        chunks: list[dict[str, Any]],
        artifact_ref: str,
        force_failure: bool = False,
    ) -> dict[str, Any]:
        if force_failure:
            raise RuntimeError("simulated_analysis_failure")
        if self.allow_live and self.api_key:
            messages = [
                {"role": "system", "content": "Return concise JSON with findings and citations."},
                {"role": "user", "content": prompt},
            ]
            request = Request(
                self.endpoint,
                data=json.dumps({"model": self.model, "messages": messages, "stream": False}).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urlopen(request, timeout=45) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                content = payload["choices"][0]["message"]["content"]
                return {
                    "mode": "live",
                    "summary": content[:1200],
                    "citations": [chunk["chunk_id"] for chunk in chunks[:2]],
                    "artifact_ref": artifact_ref,
                }
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"live_analysis_failed: {exc}") from exc
        top = chunks[:2]
        citations = [
            {
                "chunk_id": chunk["chunk_id"],
                "artifact_ref": chunk["artifact_ref"],
                "source_url": chunk["metadata"]["source_url"],
            }
            for chunk in top
        ]
        summary = (
            "San Jose meeting minutes indicate transit funding decisions and housing permit "
            "acceleration updates were discussed in recent sessions."
        )
        return {
            "mode": "deterministic",
            "summary": summary,
            "citations": citations,
            "artifact_ref": artifact_ref,
        }


def freshness_status(
    previous_snapshot: datetime | None,
    now: datetime,
    stale_usable_hours: int,
    stale_blocked_hours: int,
    force_stale_hours: int | None = None,
) -> tuple[str, str]:
    if force_stale_hours is not None:
        age = timedelta(hours=force_stale_hours)
    elif previous_snapshot is None:
        age = timedelta(0)
    else:
        age = now - previous_snapshot
    if age <= timedelta(hours=stale_usable_hours):
        return STATUS_FRESH, f"age_hours={age.total_seconds() / 3600:.2f}"
    if age <= timedelta(hours=stale_blocked_hours):
        return STATUS_STALE_USABLE, f"age_hours={age.total_seconds() / 3600:.2f}"
    return STATUS_STALE_BLOCKED, f"age_hours={age.total_seconds() / 3600:.2f}"


class DirectStoragePipelineRunner:
    def __init__(
        self,
        state_dir: Path,
        searx_endpoint: str | None = None,
        allow_live_zai: bool = False,
    ):
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.object_store = DirectObjectStore(self.state_dir)
        self.vector_store = DirectVectorStore(self.state_dir)
        self.relational = DirectRelationalStore(self.state_dir)
        self.searx = SearxClient(searx_endpoint)
        self.reader = ReaderClient(allow_live=allow_live_zai)
        self.analysis = AnalysisClient(allow_live=allow_live_zai)

    def _envelope(self, run_id: str, run_date: str) -> dict[str, Any]:
        return {
            "contract_version": CONTRACT_VERSION,
            "architecture_path": ARCH_PATH,
            "orchestrator": "windmill",
            "windmill_workspace": "affordabot",
            "windmill_flow_path": "f/affordabot/pipeline_daily_refresh_direct_storage",
            "windmill_run_id": run_id,
            "windmill_job_id": f"job-{run_id}",
            "idempotency_key": f"san-jose-ca:meeting_minutes:{run_date}",
            "jurisdiction": DEFAULT_JURISDICTION,
            "source_family": DEFAULT_SOURCE_FAMILY,
        }

    def run(
        self,
        *,
        run_date: str,
        scenario: str = "normal",
        stale_usable_hours: int = 24,
        stale_blocked_hours: int = 72,
        force_stale_hours: int | None = None,
    ) -> dict[str, Any]:
        run_id = f"local-{uuid.uuid4()}"
        envelope = self._envelope(run_id, run_date)
        now = now_utc()
        steps: list[dict[str, Any]] = []
        alerts: list[str] = []
        status = STATUS_SUCCEEDED
        reason = "completed"
        counts = {
            "search_results": 0,
            "objects_total": self.object_store.count(),
            "chunks_total": self.vector_store.count(),
            "documents_total": self.relational.count_documents(),
            "analyses_total": self.relational.count_analyses(),
        }

        force_searx_failure = scenario == "searx_failure"
        force_reader_failure = scenario == "reader_failure"
        force_storage_failure = scenario == "storage_failure"

        query = DEFAULT_SEARX_QUERY
        search_payload: dict[str, Any] | None = None
        selected_result: dict[str, Any] | None = None
        reader_result: dict[str, Any] | None = None
        reader_artifact: ArtifactRef | None = None
        previous_snapshot_before_run = self.relational.previous_snapshot_time(
            envelope["idempotency_key"]
        )

        # Step 1: search/materialize
        try:
            search_payload = self.searx.search(
                query=query,
                limit=5,
                force_failure=force_searx_failure,
            )
            result_count = len(search_payload.get("results", []))
            counts["search_results"] = result_count
            if result_count == 0:
                status = STATUS_EMPTY
                reason = "search returned zero candidates"
            raw_artifact = self.object_store.put(
                key=f"idempotency/{envelope['idempotency_key']}/search/{sha256_text(json.dumps(search_payload, sort_keys=True))[:16]}.json",
                payload=json.dumps(search_payload, indent=2, sort_keys=True).encode("utf-8"),
                content_type="application/json",
                fail=force_storage_failure,
            )
            snapshot = self.relational.upsert_search_snapshot(
                idempotency_key=envelope["idempotency_key"],
                query=query,
                payload=search_payload,
                artifact_ref=raw_artifact.ref,
                status=status if status == STATUS_EMPTY else STATUS_SUCCEEDED,
            )
            steps.append(
                {
                    "step": "search_materialize",
                    "status": status if status == STATUS_EMPTY else STATUS_SUCCEEDED,
                    "result_count": result_count,
                    "snapshot_id": snapshot["snapshot_id"],
                    "snapshot_created": snapshot["created"],
                    "artifact_ref": raw_artifact.ref,
                }
            )
            if result_count > 0:
                selected_result = search_payload["results"][0]
        except Exception as exc:  # noqa: BLE001
            status = STATUS_STORAGE_ERROR if "storage" in str(exc) else STATUS_SOURCE_ERROR
            reason = str(exc)
            steps.append({"step": "search_materialize", "status": status, "error": reason})

        # Step 2: freshness gate
        if status not in TERMINAL_FAILURE_STATUSES and status != STATUS_EMPTY:
            gate_status, gate_reason = freshness_status(
                previous_snapshot=previous_snapshot_before_run,
                now=now,
                stale_usable_hours=stale_usable_hours,
                stale_blocked_hours=stale_blocked_hours,
                force_stale_hours=force_stale_hours,
            )
            steps.append(
                {"step": "freshness_gate", "status": gate_status, "reason": gate_reason}
            )
            if gate_status == STATUS_STALE_USABLE:
                alerts.append("stale_backed=true")
            if gate_status == STATUS_STALE_BLOCKED:
                status = STATUS_STALE_BLOCKED
                reason = gate_reason

        # Step 3: reader
        if status not in TERMINAL_FAILURE_STATUSES and status != STATUS_EMPTY and selected_result:
            try:
                reader_result = self.reader.read(
                    selected_result["url"], force_failure=force_reader_failure
                )
                content = reader_result.get("content", "").strip()
                if not content:
                    raise RuntimeError("reader returned empty content")
                key_slug = slugify(canonical_document_key(selected_result["url"]))
                content_hash = sha256_text(content)
                reader_artifact = self.object_store.put(
                    key=f"documents/{key_slug}/reader/{content_hash[:16]}.md",
                    payload=content.encode("utf-8"),
                    content_type="text/markdown",
                    fail=force_storage_failure,
                )
                upsert_doc = self.relational.upsert_document(
                    canonical_key=canonical_document_key(selected_result["url"]),
                    title=selected_result["title"],
                    source_url=selected_result["url"],
                    reader_artifact_ref=reader_artifact.ref,
                    content_hash=content_hash,
                )
                steps.append(
                    {
                        "step": "read_fetch",
                        "status": STATUS_SUCCEEDED,
                        "reader_mode": reader_result["mode"],
                        "canonical_document_key": canonical_document_key(selected_result["url"]),
                        "document_created": upsert_doc["created"],
                        "artifact_ref": reader_artifact.ref,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                status = STATUS_STORAGE_ERROR if "storage" in str(exc) else STATUS_READER_ERROR
                reason = str(exc)
                steps.append({"step": "read_fetch", "status": status, "error": reason})

        # Step 4: chunk/index
        indexed_chunks: list[dict[str, Any]] = []
        if (
            status not in TERMINAL_FAILURE_STATUSES
            and status != STATUS_EMPTY
            and selected_result
            and reader_result
            and reader_artifact
        ):
            stats = self.vector_store.upsert_document_chunks(
                canonical_key=canonical_document_key(selected_result["url"]),
                artifact_ref=reader_artifact.ref,
                text=reader_result["content"],
                metadata={
                    "jurisdiction": DEFAULT_JURISDICTION,
                    "source_family": DEFAULT_SOURCE_FAMILY,
                    "source_url": selected_result["url"],
                },
            )
            indexed_chunks = self.vector_store.query("San Jose meeting minutes", top_k=5)
            steps.append(
                {
                    "step": "index_chunks",
                    "status": STATUS_SUCCEEDED,
                    "chunks_created": stats["created"],
                    "chunks_reused": stats["reused"],
                    "chunks_total_for_document": stats["total"],
                }
            )

        # Step 5: analyze
        analysis_payload: dict[str, Any] | None = None
        if (
            status not in TERMINAL_FAILURE_STATUSES
            and status != STATUS_EMPTY
            and reader_artifact
        ):
            try:
                analysis_payload = self.analysis.analyze(
                    prompt=(
                        "Summarize key municipal decisions in San Jose meeting minutes. "
                        "Return concise findings with citations."
                    ),
                    chunks=indexed_chunks,
                    artifact_ref=reader_artifact.ref,
                    force_failure=False,
                )
                analysis_artifact = self.object_store.put(
                    key=(
                        f"idempotency/{envelope['idempotency_key']}/analysis/"
                        f"{sha256_text(json.dumps(analysis_payload, sort_keys=True))[:16]}.json"
                    ),
                    payload=json.dumps(analysis_payload, indent=2, sort_keys=True).encode("utf-8"),
                    content_type="application/json",
                    fail=force_storage_failure,
                )
                upsert_analysis = self.relational.upsert_analysis(
                    idempotency_key=envelope["idempotency_key"],
                    analysis_payload=analysis_payload,
                    artifact_ref=analysis_artifact.ref,
                )
                steps.append(
                    {
                        "step": "analyze",
                        "status": STATUS_SUCCEEDED,
                        "analysis_mode": analysis_payload["mode"],
                        "analysis_created": upsert_analysis["created"],
                        "analysis_artifact_ref": analysis_artifact.ref,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                status = STATUS_STORAGE_ERROR if "storage" in str(exc) else STATUS_ANALYSIS_ERROR
                reason = str(exc)
                steps.append({"step": "analyze", "status": status, "error": reason})

        counts["objects_total"] = self.object_store.count()
        counts["chunks_total"] = self.vector_store.count()
        counts["documents_total"] = self.relational.count_documents()
        counts["analyses_total"] = self.relational.count_analyses()

        run_payload = {
            "envelope": envelope,
            "scenario": scenario,
            "status": status,
            "reason": reason,
            "alerts": alerts,
            "steps": steps,
            "counts": counts,
            "storage_snapshot": {
                "object_store": self.object_store.snapshot(),
                "vector_store": self.vector_store.snapshot(),
                "relational_store": self.relational.snapshot(),
            },
            "analysis_preview": (analysis_payload or {}).get("summary"),
            "created_at": utc_iso(now),
        }
        self.relational.write_run(run_id, run_payload)
        return run_payload


def write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def render_run_evidence(suite: dict[str, Any]) -> str:
    first = suite["runs"]["first"]
    rerun = suite["runs"]["rerun"]
    return textwrap.dedent(
        f"""
        # Path A Run Evidence

        Contract version: `{CONTRACT_VERSION}`
        Architecture path: `{ARCH_PATH}`

        ## First Run

        - status: `{first["status"]}`
        - reason: `{first["reason"]}`
        - search results: `{first["counts"]["search_results"]}`
        - objects total: `{first["counts"]["objects_total"]}`
        - chunks total: `{first["counts"]["chunks_total"]}`
        - documents total: `{first["counts"]["documents_total"]}`
        - analyses total: `{first["counts"]["analyses_total"]}`

        ## Rerun (Idempotency)

        - status: `{rerun["status"]}`
        - reason: `{rerun["reason"]}`
        - objects total: `{rerun["counts"]["objects_total"]}`
        - chunks total: `{rerun["counts"]["chunks_total"]}`
        - documents total: `{rerun["counts"]["documents_total"]}`
        - analyses total: `{rerun["counts"]["analyses_total"]}`

        Idempotency assertion:
        - canonical documents should remain stable across rerun with same idempotency key
        - vector chunks should be reused rather than duplicated
        - analysis row should be upserted by idempotency key

        Computed checks:
        - documents stable: `{suite["checks"]["documents_stable"]}`
        - chunks stable: `{suite["checks"]["chunks_stable"]}`
        - analyses stable: `{suite["checks"]["analyses_stable"]}`
        - overall idempotent: `{suite["checks"]["idempotent"]}`
        """
    ).strip()


def render_storage_snapshots(suite: dict[str, Any]) -> str:
    first = suite["runs"]["first"]["storage_snapshot"]
    rerun = suite["runs"]["rerun"]["storage_snapshot"]
    return (
        "# Path A Storage Snapshots\n\n"
        "## First Run Snapshot\n\n"
        "```json\n"
        f"{json.dumps(first, indent=2, sort_keys=True)}\n"
        "```\n\n"
        "## Rerun Snapshot\n\n"
        "```json\n"
        f"{json.dumps(rerun, indent=2, sort_keys=True)}\n"
        "```"
    )


def render_failure_drills(suite: dict[str, Any]) -> str:
    rows = []
    for name, result in suite["failures"].items():
        rows.append(f"- `{name}` => status `{result['status']}` reason `{result['reason']}`")
    bullets = "\n".join(rows)
    return (
        "# Path A Failure Drills\n\n"
        f"{bullets}\n\n"
        "Expected terminal statuses:\n"
        f"- SearXNG failure => `{STATUS_SOURCE_ERROR}`\n"
        f"- Reader failure => `{STATUS_READER_ERROR}`\n"
        f"- Storage failure => `{STATUS_STORAGE_ERROR}`"
    )


def run_suite(args: argparse.Namespace) -> dict[str, Any]:
    state_dir = Path(args.state_dir)
    if args.reset_state and state_dir.exists():
        shutil.rmtree(state_dir)
    runner = DirectStoragePipelineRunner(
        state_dir=state_dir,
        searx_endpoint=args.searx_endpoint,
        allow_live_zai=args.allow_live_zai,
    )
    run_date = args.run_date or now_utc().date().isoformat()
    first = runner.run(run_date=run_date, scenario="normal")
    rerun = runner.run(run_date=run_date, scenario="normal")
    searx_failure = runner.run(run_date=run_date, scenario="searx_failure")
    reader_failure = runner.run(run_date=run_date, scenario="reader_failure")
    storage_failure = runner.run(run_date=run_date, scenario="storage_failure")

    checks = {
        "documents_stable": first["counts"]["documents_total"] == rerun["counts"]["documents_total"],
        "chunks_stable": first["counts"]["chunks_total"] == rerun["counts"]["chunks_total"],
        "analyses_stable": first["counts"]["analyses_total"] == rerun["counts"]["analyses_total"],
    }
    checks["idempotent"] = all(checks.values())

    suite = {
        "generated_at": utc_iso(),
        "state_dir": str(state_dir),
        "run_date": run_date,
        "checks": checks,
        "runs": {"first": first, "rerun": rerun},
        "failures": {
            "searx_failure": searx_failure,
            "reader_failure": reader_failure,
            "storage_failure": storage_failure,
        },
        "live_flags": {
            "searx_endpoint_configured": bool(args.searx_endpoint),
            "allow_live_zai": bool(args.allow_live_zai),
            "zai_api_key_present": bool(os.getenv("ZAI_API_KEY")),
        },
        "live_blockers": [],
    }
    if not args.searx_endpoint:
        suite["live_blockers"].append("SEARX_ENDPOINT not configured; used deterministic SearX fixture.")
    if not args.allow_live_zai or not os.getenv("ZAI_API_KEY"):
        suite["live_blockers"].append(
            "Z.ai reader/analysis live call unavailable; used deterministic contract-shape substitutes."
        )

    evidence_dir = Path(args.evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    write_json(evidence_dir / "suite-results.json", suite)
    write_markdown(evidence_dir / "run-evidence.md", render_run_evidence(suite))
    write_markdown(evidence_dir / "storage-snapshots.md", render_storage_snapshots(suite))
    write_markdown(evidence_dir / "failure-drills.md", render_failure_drills(suite))
    return suite


def run_single(args: argparse.Namespace) -> dict[str, Any]:
    runner = DirectStoragePipelineRunner(
        state_dir=Path(args.state_dir),
        searx_endpoint=args.searx_endpoint,
        allow_live_zai=args.allow_live_zai,
    )
    run_date = args.run_date or now_utc().date().isoformat()
    result = runner.run(
        run_date=run_date,
        scenario=args.scenario,
        stale_usable_hours=args.stale_usable_hours,
        stale_blocked_hours=args.stale_blocked_hours,
        force_stale_hours=args.force_stale_hours,
    )
    if args.output_json:
        write_json(Path(args.output_json), result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Path A Windmill-heavy direct storage bakeoff runner."
    )
    sub = parser.add_subparsers(dest="mode", required=False)

    run_parser = sub.add_parser("run", help="Run one scenario.")
    run_parser.add_argument(
        "--scenario",
        choices=["normal", "searx_failure", "reader_failure", "storage_failure"],
        default="normal",
    )
    run_parser.add_argument("--run-date", default=None, help="YYYY-MM-DD idempotency date.")
    run_parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    run_parser.add_argument("--searx-endpoint", default=None)
    run_parser.add_argument("--allow-live-zai", action="store_true")
    run_parser.add_argument("--output-json", default=None)
    run_parser.add_argument("--stale-usable-hours", type=int, default=24)
    run_parser.add_argument("--stale-blocked-hours", type=int, default=72)
    run_parser.add_argument("--force-stale-hours", type=int, default=None)

    suite_parser = sub.add_parser("suite", help="Run first/rerun/failure drills and emit docs.")
    suite_parser.add_argument("--run-date", default=None, help="YYYY-MM-DD idempotency date.")
    suite_parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    suite_parser.add_argument("--evidence-dir", default=str(DEFAULT_EVIDENCE_DIR))
    suite_parser.add_argument("--searx-endpoint", default=None)
    suite_parser.add_argument("--allow-live-zai", action="store_true")
    suite_parser.add_argument("--reset-state", action="store_true")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    mode = args.mode or "run"
    if mode == "suite":
        result = run_suite(args)
    else:
        result = run_single(args)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
