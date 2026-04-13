from fastapi import APIRouter, Depends, Request, HTTPException
from typing import Any, List, Optional
from pydantic import BaseModel
import json
import os
from services.glass_box import GlassBoxService, AgentStep, PipelineStep
from auth.clerk import require_admin_user
from db.postgres_client import PostgresDB
from services.pipeline.domain.constants import CONTRACT_VERSION
from scripts.substrate.substrate_inspection_report import (
    build_substrate_inspection_report,
    fetch_raw_scrapes_for_run,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_user)],
)

DEFAULT_SOURCE_FAMILY = "meeting_minutes"
FRESHNESS_POLICY_BY_SOURCE_FAMILY: dict[str, dict[str, int]] = {
    "meeting_minutes": {
        "fresh_hours": 24,
        "stale_usable_ceiling_hours": 72,
        "fail_closed_ceiling_hours": 168,
    },
    "agendas": {
        "fresh_hours": 24,
        "stale_usable_ceiling_hours": 72,
        "fail_closed_ceiling_hours": 168,
    },
    "legislation": {
        "fresh_hours": 24,
        "stale_usable_ceiling_hours": 48,
        "fail_closed_ceiling_hours": 120,
    },
    "general_web_reference": {
        "fresh_hours": 48,
        "stale_usable_ceiling_hours": 168,
        "fail_closed_ceiling_hours": 336,
    },
}


# Dependency to get the database client
def get_db(request: Request) -> PostgresDB:
    """Get database client from app state."""
    db = getattr(request.app.state, "db", None)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    return db


def get_glass_box_service(db: PostgresDB = Depends(get_db)) -> GlassBoxService:
    """Get GlassBoxService instance with DB client."""
    return GlassBoxService(db_client=db, trace_dir=".traces")


# Pydantic models for API responses
class Jurisdiction(BaseModel):
    id: str
    name: str
    type: str


class JurisdictionDetail(BaseModel):
    id: str
    name: str
    type: str
    bill_count: int = 0
    source_count: int = 0
    last_scrape: Optional[str] = None


class Prompt(BaseModel):
    id: Optional[str] = None
    prompt_type: str
    system_prompt: str
    description: Optional[str] = None
    version: int = 1
    is_active: bool = True


class PromptUpdate(BaseModel):
    type: str
    system_prompt: str


# ============================================================================
# Helper Functions
# ============================================================================
async def find_jurisdiction(db: PostgresDB, jurisdiction_id: str):
    """Find a jurisdiction by ID or slug-like name."""
    search_term = jurisdiction_id.replace("-", " ")
    query = """
        SELECT id, name, type FROM jurisdictions 
        WHERE id::text = $1 
           OR LOWER(name) = LOWER($1)
           OR LOWER(name) = LOWER($2)
           OR LOWER(name) LIKE '%' || LOWER($2) || '%'
        LIMIT 1
    """
    row = await db._fetchrow(query, jurisdiction_id, search_term)
    if not row:
        raise HTTPException(
            status_code=404, detail=f"Jurisdiction '{jurisdiction_id}' not found"
        )
    return row


async def get_count(db: PostgresDB, query: str, *args):
    """Execute a count query and return the result or 0."""
    try:
        result = await db._fetchrow(query, *args)
        return result["count"] if result else 0
    except Exception:
        return 0


def _to_json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _safe_preview(value: Any, *, max_chars: int) -> str:
    text = _to_text(value)
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}..."


def _serialize_substrate_row(
    row: dict[str, Any],
    *,
    preview_chars: int = 320,
    include_full_metadata: bool = False,
) -> dict[str, Any]:
    metadata = _to_json_dict(row.get("metadata"))
    truth = _to_json_dict(metadata.get("ingestion_truth"))
    data = _to_json_dict(row.get("data"))
    content = data.get("content")

    payload = {
        "id": str(row["id"]),
        "created_at": str(row["created_at"]) if row.get("created_at") else None,
        "url": row.get("url"),
        "source_url": row.get("source_url"),
        "source_name": row.get("source_name"),
        "source_type": row.get("source_type"),
        "jurisdiction_name": row.get("jurisdiction_name"),
        "storage_uri": row.get("storage_uri"),
        "document_id": str(row["document_id"]) if row.get("document_id") else None,
        "canonical_document_key": row.get("canonical_document_key"),
        "previous_raw_scrape_id": str(row["previous_raw_scrape_id"]) if row.get("previous_raw_scrape_id") else None,
        "revision_number": int(row["revision_number"]) if row.get("revision_number") is not None else None,
        "last_seen_at": str(row["last_seen_at"]) if row.get("last_seen_at") else None,
        "seen_count": int(row["seen_count"]) if row.get("seen_count") is not None else None,
        "error_message": row.get("error_message"),
        "document_type": metadata.get("document_type"),
        "content_class": metadata.get("content_class"),
        "trust_tier": metadata.get("trust_tier"),
        "promotion_state": metadata.get("promotion_state"),
        "promotion_reason_category": metadata.get("promotion_reason_category"),
        "ingestion_truth_stage": truth.get("stage"),
        "ingestion_truth_retrievable": _to_bool(truth.get("retrievable")),
        "content_preview": _safe_preview(content, max_chars=preview_chars),
        "content_length": len(content) if isinstance(content, str) else 0,
    }

    if include_full_metadata:
        payload["metadata"] = metadata
        payload["ingestion_truth"] = truth

    return payload


def _coerce_int(value: Any, default: int = 0) -> int:
    if isinstance(value, int):
        return value
    if value is None:
        return default
    try:
        return int(value)
    except Exception:
        return default


def _normalize_source_family(source_family: Optional[str]) -> str:
    text = _to_text(source_family).lower()
    return text if text else DEFAULT_SOURCE_FAMILY


def _freshness_policy(source_family: str) -> dict[str, int]:
    return FRESHNESS_POLICY_BY_SOURCE_FAMILY.get(
        source_family, FRESHNESS_POLICY_BY_SOURCE_FAMILY[DEFAULT_SOURCE_FAMILY]
    )


def _extract_counts(result: dict[str, Any]) -> dict[str, int]:
    search_results = _coerce_int(
        result.get("search_results_count")
        or result.get("search_results")
        or result.get("discovered_sources")
        or result.get("source_count")
    )
    raw_scrapes = _coerce_int(
        result.get("raw_scrapes_count")
        or result.get("raw_scrapes")
        or result.get("captured_count")
        or result.get("sources_processed")
    )
    chunks = _coerce_int(
        result.get("chunks")
        or result.get("chunk_count")
        or result.get("rag_chunks_retrieved")
        or result.get("validated_evidence_count")
    )
    artifacts = _coerce_int(result.get("artifact_count") or result.get("artifacts"))
    if artifacts == 0 and _to_bool(result.get("source_text_present")):
        artifacts = 1

    analysis_obj = result.get("analysis")
    analyses = 1 if isinstance(analysis_obj, dict) and analysis_obj else 0

    return {
        "search_results": search_results,
        "raw_scrapes": raw_scrapes,
        "artifacts": artifacts,
        "chunks": chunks,
        "analyses": analyses,
    }


def _extract_latest_analysis(result: dict[str, Any], counts: dict[str, int]) -> dict[str, Any]:
    analysis = result.get("analysis")
    ready = isinstance(analysis, dict) and bool(analysis)
    evidence_count = _coerce_int(result.get("validated_evidence_count") or counts.get("chunks"))
    if ready:
        status = "ready"
    elif evidence_count > 0:
        status = "not_ready"
    else:
        status = "blocked"

    sufficiency_state = result.get("sufficiency_state")
    if not sufficiency_state:
        if _to_bool(result.get("quantification_eligible")):
            sufficiency_state = "quantitative_ready"
        elif evidence_count > 0:
            sufficiency_state = "qualitative_only"
        else:
            sufficiency_state = "insufficient_evidence"

    return {
        "status": status,
        "sufficiency_state": sufficiency_state,
        "evidence_count": evidence_count,
    }


def _extract_pipeline_alerts(result: dict[str, Any]) -> list[str]:
    alerts_raw = result.get("alerts")
    if isinstance(alerts_raw, list):
        return [_to_text(item) for item in alerts_raw if _to_text(item)]
    alerts: list[str] = []
    insufficiency_reason = _to_text(result.get("insufficiency_reason"))
    if insufficiency_reason:
        alerts.append(f"insufficiency:{insufficiency_reason}")
    if _coerce_int(result.get("rag_chunks_retrieved")) == 0 and _to_bool(
        result.get("retriever_invoked")
    ):
        alerts.append("retriever_returned_no_chunks")
    return alerts


def _derive_pipeline_status(run_status: str, freshness_status: str) -> str:
    if freshness_status and freshness_status != "unknown":
        return freshness_status
    if run_status in {"completed"}:
        return "fresh"
    if run_status in {"failed", "prefix_halted", "interrupted", "fixture_invalid"}:
        return "stale_blocked"
    return "unknown"


def _build_windmill_run_url(windmill_run_id: Optional[str]) -> Optional[str]:
    run_id = _to_text(windmill_run_id)
    if not run_id:
        return None
    base = _to_text(os.getenv("WINDMILL_BASE_URL"))
    if not base:
        return f"/windmill/runs/{run_id}"
    return f"{base.rstrip('/')}/runs/{run_id}"


def _json_payload(value: Any) -> dict[str, Any]:
    return _to_json_dict(value)


# ============================================================================
# JURISDICTION ENDPOINTS
# ============================================================================


@router.get("/jurisdictions", response_model=List[Jurisdiction])
async def list_jurisdictions(db: PostgresDB = Depends(get_db)):
    """List all jurisdictions."""
    try:
        rows = await db._fetch("SELECT id, name, type FROM jurisdictions ORDER BY name")
        return [
            Jurisdiction(id=str(row["id"]), name=row["name"], type=row["type"])
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch jurisdictions: {str(e)}"
        )


@router.get("/jurisdictions/{jurisdiction_id}", response_model=JurisdictionDetail)
async def get_jurisdiction(jurisdiction_id: str, db: PostgresDB = Depends(get_db)):
    """Get jurisdiction detail by ID or slug."""
    try:
        row = await find_jurisdiction(db, jurisdiction_id)
        jur_id_str = str(row["id"])

        bill_count = await get_count(
            db,
            "SELECT COUNT(*) as count FROM raw_scrapes rs JOIN sources s ON rs.source_id = s.id WHERE s.jurisdiction_id::text = $1",
            jur_id_str,
        )
        source_count = await get_count(
            db,
            "SELECT COUNT(*) as count FROM sources WHERE jurisdiction_id::text = $1",
            jur_id_str,
        )

        return JurisdictionDetail(
            id=jur_id_str,
            name=row["name"],
            type=row["type"],
            bill_count=bill_count,
            source_count=source_count,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch jurisdiction: {str(e)}"
        )


@router.get("/jurisdiction/{jurisdiction_id}/dashboard")
async def get_jurisdiction_dashboard(
    jurisdiction_id: str, db: PostgresDB = Depends(get_db)
):
    """Get jurisdiction dashboard stats."""
    try:
        row = await find_jurisdiction(db, jurisdiction_id)
        jur_id_str = str(row["id"])

        total_raw_scrapes = await get_count(
            db,
            "SELECT COUNT(*) as count FROM raw_scrapes rs JOIN sources s ON rs.source_id = s.id WHERE s.jurisdiction_id::text = $1",
            jur_id_str,
        )
        processed_scrapes = await get_count(
            db,
            "SELECT COUNT(*) as count FROM legislation WHERE jurisdiction_id::text = $1",
            jur_id_str,
        )

        last_scrape_result = await db._fetchrow(
            "SELECT MAX(rs.created_at) as last_scrape FROM raw_scrapes rs JOIN sources s ON rs.source_id = s.id WHERE s.jurisdiction_id::text = $1",
            jur_id_str,
        )
        last_scrape = (
            str(last_scrape_result["last_scrape"])
            if last_scrape_result and last_scrape_result["last_scrape"]
            else None
        )

        pipeline_status = "unknown"
        if total_raw_scrapes > 0 and last_scrape:
            pipeline_status = "healthy"
        elif total_raw_scrapes > 0:
            pipeline_status = "degraded"

        return {
            "jurisdiction": row["name"],
            "last_scrape": last_scrape,
            "total_raw_scrapes": total_raw_scrapes,
            "processed_scrapes": processed_scrapes,
            "total_bills": processed_scrapes,
            "pipeline_status": pipeline_status,
            "active_alerts": [],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch dashboard: {str(e)}"
        )


# ============================================================================
# PROMPTS ENDPOINTS
# ============================================================================


@router.get("/prompts", response_model=List[Prompt])
async def list_prompts(db: PostgresDB = Depends(get_db)):
    """List all active prompts."""
    try:
        query = "SELECT id, prompt_type, system_prompt, description, version, is_active FROM system_prompts WHERE is_active = true ORDER BY prompt_type"
        rows = await db._fetch(query)
        return [Prompt(**row) for row in rows]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch prompts: {str(e)}"
        )


@router.get("/prompts/{prompt_type}", response_model=Prompt)
async def get_prompt(prompt_type: str, db: PostgresDB = Depends(get_db)):
    """Get a specific prompt by type."""
    try:
        query = "SELECT id, prompt_type, system_prompt, description, version, is_active FROM system_prompts WHERE prompt_type = $1 AND is_active = true"
        row = await db._fetchrow(query, prompt_type)
        if not row:
            raise HTTPException(
                status_code=404, detail=f"Prompt type '{prompt_type}' not found"
            )
        return Prompt(**row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch prompt: {str(e)}")


@router.post("/prompts")
async def update_prompt(prompt: PromptUpdate, db: PostgresDB = Depends(get_db)):
    """Update or create a prompt."""
    try:
        version = await db.update_system_prompt(prompt.type, prompt.system_prompt)
        return {"success": True, "message": "Prompt updated", "version": version}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update prompt: {str(e)}"
        )


# ============================================================================
# SCRAPES ENDPOINTS
# ============================================================================


@router.get("/scrapes")
async def list_scrapes(db: PostgresDB = Depends(get_db), limit: int = 50):
    """List recent scrapes."""
    try:
        query = """
            SELECT rs.id, rs.url, rs.created_at, rs.metadata, s.jurisdiction_id, j.name as jurisdiction_name
            FROM raw_scrapes rs
            LEFT JOIN sources s ON rs.source_id = s.id
            LEFT JOIN jurisdictions j ON s.jurisdiction_id::text = j.id::text
            ORDER BY rs.created_at DESC
            LIMIT $1
        """
        rows = await db._fetch(query, limit)
        return [
            {
                "id": str(row["id"]),
                "url": row["url"],
                "scraped_at": str(row["created_at"]) if row.get("created_at") else None,
                "jurisdiction_id": str(row["jurisdiction_id"])
                if row.get("jurisdiction_id")
                else None,
                "jurisdiction_name": row["jurisdiction_name"],
                "metadata": row["metadata"],
            }
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch scrapes: {str(e)}"
        )


# ============================================================================
# SUBSTRATE VIEWER ENDPOINTS (bd-afqp)
# ============================================================================


@router.get("/substrate/runs")
async def list_substrate_runs(
    db: PostgresDB = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
    run_id_key: str = "manual_run_id",
):
    """List substrate runs grouped by metadata.run_id_key."""
    try:
        rows = await db._fetch(
            """
            WITH stamped AS (
                SELECT
                    rs.created_at,
                    rs.error_message,
                    rs.metadata,
                    COALESCE(rs.metadata->>$1, '') AS run_id
                FROM raw_scrapes rs
                WHERE COALESCE(rs.metadata->>$1, '') <> ''
            )
            SELECT
                run_id,
                MIN(created_at) AS first_created_at,
                MAX(created_at) AS last_created_at,
                COUNT(*) AS raw_scrapes_total,
                COUNT(*) FILTER (
                    WHERE COALESCE(metadata->>'promotion_state', '') = 'promoted_substrate'
                ) AS promoted_substrate_count,
                COUNT(*) FILTER (
                    WHERE COALESCE(metadata->>'promotion_state', '') = 'durable_raw'
                ) AS durable_raw_count,
                COUNT(*) FILTER (
                    WHERE COALESCE(metadata->>'promotion_state', '') = 'captured_candidate'
                ) AS captured_candidate_count,
                COUNT(*) FILTER (
                    WHERE COALESCE(COALESCE(metadata->'ingestion_truth', '{}'::jsonb)->>'stage', '') = 'retrievable'
                       OR LOWER(
                            COALESCE(
                                COALESCE(metadata->'ingestion_truth', '{}'::jsonb)->>'retrievable',
                                'false'
                            )
                        ) IN ('true', '1', 'yes')
                ) AS retrievable_count,
                COUNT(*) FILTER (WHERE COALESCE(error_message, '') <> '') AS raw_capture_error_count
            FROM stamped
            GROUP BY run_id
            ORDER BY last_created_at DESC
            LIMIT $2 OFFSET $3
            """,
            run_id_key,
            limit,
            offset,
        )

        runs = []
        for row in rows:
            errors = int(row.get("raw_capture_error_count") or 0)
            retrievable = int(row.get("retrievable_count") or 0)
            status = "captured_only"
            if errors > 0:
                status = "has_errors"
            elif retrievable > 0:
                status = "healthy"

            runs.append(
                {
                    "run_id": row["run_id"],
                    "first_created_at": str(row["first_created_at"])
                    if row.get("first_created_at")
                    else None,
                    "last_created_at": str(row["last_created_at"])
                    if row.get("last_created_at")
                    else None,
                    "status": status,
                    "raw_scrapes_total": int(row.get("raw_scrapes_total") or 0),
                    "promoted_substrate_count": int(
                        row.get("promoted_substrate_count") or 0
                    ),
                    "durable_raw_count": int(row.get("durable_raw_count") or 0),
                    "captured_candidate_count": int(
                        row.get("captured_candidate_count") or 0
                    ),
                    "retrievable_count": retrievable,
                    "raw_capture_error_count": errors,
                }
            )

        return {"run_id_key": run_id_key, "limit": limit, "offset": offset, "runs": runs}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch substrate runs: {str(e)}"
        )


@router.get("/substrate/runs/{run_id}")
async def get_substrate_run_detail(
    run_id: str,
    db: PostgresDB = Depends(get_db),
    run_id_key: str = "manual_run_id",
):
    """Get inspection-style summary for a substrate run."""
    try:
        rows = await fetch_raw_scrapes_for_run(db=db, run_id=run_id, run_id_key=run_id_key)
        if not rows:
            raise HTTPException(status_code=404, detail=f"Substrate run '{run_id}' not found")

        report = build_substrate_inspection_report(
            run_id=run_id,
            rows=rows,
            run_id_key=run_id_key,
        )
        jurisdiction_names = sorted(
            {
                _to_text(row.get("jurisdiction_name"))
                for row in rows
                if _to_text(row.get("jurisdiction_name"))
            }
        )

        return {
            "run_id": run_id,
            "run_id_key": run_id_key,
            "summary": report,
            "failure_buckets": report.get("top_failure_buckets", []),
            "jurisdiction_names": jurisdiction_names,
            "raw_scrapes_total": report.get("raw_scrapes_total", 0),
            "latest_created_at": str(rows[0]["created_at"]) if rows and rows[0].get("created_at") else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch substrate run detail: {str(e)}"
        )


@router.get("/substrate/runs/{run_id}/failure-buckets")
async def get_substrate_run_failure_buckets(
    run_id: str,
    db: PostgresDB = Depends(get_db),
    run_id_key: str = "manual_run_id",
):
    """Get failure buckets for a substrate run."""
    try:
        rows = await fetch_raw_scrapes_for_run(db=db, run_id=run_id, run_id_key=run_id_key)
        if not rows:
            raise HTTPException(status_code=404, detail=f"Substrate run '{run_id}' not found")

        report = build_substrate_inspection_report(
            run_id=run_id,
            rows=rows,
            run_id_key=run_id_key,
        )
        return {
            "run_id": run_id,
            "run_id_key": run_id_key,
            "raw_scrapes_total": report.get("raw_scrapes_total", 0),
            "failure_buckets": report.get("top_failure_buckets", []),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch substrate failure buckets: {str(e)}"
        )


@router.get("/substrate/runs/{run_id}/raw-scrapes")
async def list_substrate_run_raw_scrapes(
    run_id: str,
    db: PostgresDB = Depends(get_db),
    run_id_key: str = "manual_run_id",
    limit: int = 50,
    offset: int = 0,
    jurisdiction_name: str = "",
    document_type: str = "",
    promotion_state: str = "",
    trust_tier: str = "",
    content_class: str = "",
):
    """List substrate raw rows for a run with optional filters."""
    try:
        rows = await db._fetch(
            """
            SELECT
                rs.id,
                rs.created_at,
                rs.url,
                rs.data,
                rs.error_message,
                rs.storage_uri,
                rs.document_id,
                rs.canonical_document_key,
                rs.previous_raw_scrape_id,
                rs.revision_number,
                rs.last_seen_at,
                rs.seen_count,
                rs.metadata,
                s.url AS source_url,
                s.type AS source_type,
                s.name AS source_name,
                j.name AS jurisdiction_name
            FROM raw_scrapes rs
            LEFT JOIN sources s ON s.id = rs.source_id
            LEFT JOIN jurisdictions j ON j.id::text = s.jurisdiction_id
            WHERE COALESCE(rs.metadata->>$1, '') = $2
              AND ($3 = '' OR LOWER(COALESCE(j.name, '')) = LOWER($3))
              AND ($4 = '' OR LOWER(COALESCE(rs.metadata->>'document_type', '')) = LOWER($4))
              AND ($5 = '' OR LOWER(COALESCE(rs.metadata->>'promotion_state', '')) = LOWER($5))
              AND ($6 = '' OR LOWER(COALESCE(rs.metadata->>'trust_tier', '')) = LOWER($6))
              AND ($7 = '' OR LOWER(COALESCE(rs.metadata->>'content_class', '')) = LOWER($7))
            ORDER BY rs.created_at DESC
            LIMIT $8 OFFSET $9
            """,
            run_id_key,
            run_id,
            jurisdiction_name,
            document_type,
            promotion_state,
            trust_tier,
            content_class,
            limit,
            offset,
        )
        serialized_rows = [
            _serialize_substrate_row(dict(row), preview_chars=320) for row in rows
        ]
        return {
            "run_id": run_id,
            "run_id_key": run_id_key,
            "limit": limit,
            "offset": offset,
            "filters": {
                "jurisdiction_name": jurisdiction_name or None,
                "document_type": document_type or None,
                "promotion_state": promotion_state or None,
                "trust_tier": trust_tier or None,
                "content_class": content_class or None,
            },
            "raw_scrapes": serialized_rows,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch substrate raw rows: {str(e)}"
        )


@router.get("/substrate/raw-scrapes/{raw_scrape_id}")
async def get_substrate_raw_scrape_detail(
    raw_scrape_id: str,
    db: PostgresDB = Depends(get_db),
):
    """Get detailed substrate row payload for operator debugging."""
    try:
        row = await db._fetchrow(
            """
            SELECT
                rs.id,
                rs.created_at,
                rs.url,
                rs.data,
                rs.error_message,
                rs.storage_uri,
                rs.document_id,
                rs.canonical_document_key,
                rs.previous_raw_scrape_id,
                rs.revision_number,
                rs.last_seen_at,
                rs.seen_count,
                rs.metadata,
                s.url AS source_url,
                s.type AS source_type,
                s.name AS source_name,
                j.name AS jurisdiction_name
            FROM raw_scrapes rs
            LEFT JOIN sources s ON s.id = rs.source_id
            LEFT JOIN jurisdictions j ON j.id::text = s.jurisdiction_id
            WHERE rs.id::text = $1
            LIMIT 1
            """,
            raw_scrape_id,
        )
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Substrate raw scrape '{raw_scrape_id}' not found",
            )

        payload = _serialize_substrate_row(
            dict(row),
            preview_chars=4000,
            include_full_metadata=True,
        )
        return payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch substrate raw row detail: {str(e)}"
        )


# ============================================================================
# DASHBOARD STATS ENDPOINT
# ============================================================================


@router.get("/stats")
async def get_dashboard_stats(db: PostgresDB = Depends(get_db)):
    """Get dashboard statistics."""
    try:
        return {
            "jurisdictions": await get_count(
                db, "SELECT COUNT(*) as count FROM jurisdictions"
            ),
            "scrapes": await get_count(db, "SELECT COUNT(*) as count FROM raw_scrapes"),
            "sources": await get_count(db, "SELECT COUNT(*) as count FROM sources"),
            "chunks": await get_count(
                db, "SELECT COUNT(*) as count FROM document_chunks"
            ),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")


# ============================================================================
# GLASS BOX ENDPOINTS (existing)
# ============================================================================


@router.get("/traces/{query_id}", response_model=List[AgentStep])
async def get_agent_traces(
    query_id: str, service: GlassBoxService = Depends(get_glass_box_service)
):
    """Get full execution trace for a specific agent session."""
    return await service.get_traces_for_query(query_id)


@router.get("/traces", response_model=List[str])
async def list_agent_sessions(
    service: GlassBoxService = Depends(get_glass_box_service),
):
    """List all recorded agent sessions."""
    return await service.list_queries()


@router.get("/runs/{run_id}/steps", response_model=List[PipelineStep])
async def get_run_steps(
    run_id: str, service: GlassBoxService = Depends(get_glass_box_service)
):
    """
    Get granular execution steps for a pipeline run.
    """
    return await service.get_pipeline_steps(run_id)


@router.get("/pipeline-runs")
async def list_pipeline_runs(service: GlassBoxService = Depends(get_glass_box_service)):
    """List recent pipeline runs."""
    return await service.list_pipeline_runs()


@router.get("/pipeline-runs/{run_id}")
async def get_pipeline_run_details(
    run_id: str, service: GlassBoxService = Depends(get_glass_box_service)
):
    """Get details of a specific pipeline run."""
    run = await service.get_pipeline_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    # Also fetch steps
    steps = await service.get_pipeline_steps(run_id)
    run["steps"] = [step.model_dump() for step in steps]

    return run


@router.get("/alerts")
async def list_alerts(db: PostgresDB = Depends(get_db)):
    """
    List system alerts derived from canonical truth fields.

    Consumes pipeline_runs result data to produce deterministic alerts
    without a second truth store (bd-tytc.8).
    """
    try:
        from services.alerting import AlertingService

        service = AlertingService(db_client=db)
        alerts = await service.evaluate_recent_runs(limit=50)
        return {
            "alerts": [
                {
                    "id": f"{a.rule}-{a.run_id}",
                    "type": "error" if a.severity == "high" else "warning",
                    "severity": a.severity,
                    "rule": a.rule,
                    "message": a.message,
                    "jurisdiction": a.jurisdiction,
                    "bill_id": a.bill_id,
                    "run_id": a.run_id,
                    "created_at": a.created_at,
                    "acknowledged": False,
                }
                for a in alerts
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to compute alerts: {str(e)}"
        )


# ============================================================================
# DOCUMENT HEALTH (bd-tytc.5)
# ============================================================================


@router.get("/document-health")
async def get_document_health(db: PostgresDB = Depends(get_db)):
    """
    Document health view: static ingestion/vector status for scraped documents.
    Separate from dynamic pipeline run traces (bd-tytc.5).
    """
    try:
        query = """
            SELECT
                rs.id,
                rs.url,
                rs.created_at,
                rs.content_hash,
                rs.metadata,
                s.jurisdiction_id,
                j.name as jurisdiction_name,
                dc.chunk_count,
                dc.document_id
            FROM raw_scrapes rs
            LEFT JOIN sources s ON rs.source_id = s.id
            LEFT JOIN jurisdictions j ON s.jurisdiction_id::text = j.id::text
            LEFT JOIN (
                SELECT document_id, COUNT(*) as chunk_count
                FROM document_chunks
                GROUP BY document_id
            ) dc ON dc.document_id = rs.metadata::json->>'document_id'
            ORDER BY rs.created_at DESC
            LIMIT 50
        """
        rows = await db._fetch(query)
        documents = []
        for r in rows:
            metadata = (
                json.loads(r["metadata"])
                if isinstance(r["metadata"], str)
                else (r["metadata"] or {})
            )
            documents.append(
                {
                    "id": str(r["id"]),
                    "url": r["url"],
                    "jurisdiction": r["jurisdiction_name"],
                    "jurisdiction_id": str(r["jurisdiction_id"])
                    if r.get("jurisdiction_id")
                    else None,
                    "scraped_at": str(r["created_at"]) if r.get("created_at") else None,
                    "content_hash": r["content_hash"],
                    "chunk_count": r["chunk_count"] or 0,
                    "document_id": metadata.get("document_id"),
                    "extraction_status": metadata.get("extraction_status"),
                    "source_type": metadata.get("source_type"),
                    "bill_number": metadata.get("bill_number"),
                    "has_vector_chunks": (r["chunk_count"] or 0) > 0,
                }
            )
        return {"documents": documents, "total": len(documents)}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch document health: {str(e)}"
        )


@router.get("/bill-truth/{jurisdiction}/{bill_id}")
async def get_bill_truth(
    jurisdiction: str, bill_id: str, db: PostgresDB = Depends(get_db)
):
    """
    Bill-level truth diagnostic: trace a bill through Scrape -> Raw Text -> Vector Chunks -> Research.

    Used by operators and verification scripts to quickly diagnose
    data gaps for specific bills (bd-tytc.7).
    """
    try:
        scrape_query = """
            SELECT rs.id, rs.url, rs.created_at, rs.content_hash, rs.metadata, rs.data
            FROM raw_scrapes rs
            LEFT JOIN sources s ON rs.source_id = s.id
            LEFT JOIN jurisdictions j ON s.jurisdiction_id::text = j.id::text
            WHERE LOWER(j.name) = LOWER($1)
              AND rs.metadata::json->>'bill_number' ILIKE $2
            ORDER BY rs.created_at DESC
            LIMIT 1
        """
        scrape_row = await db._fetchrow(scrape_query, jurisdiction, f"%{bill_id}%")
        scrape_info = None
        if scrape_row:
            metadata = (
                json.loads(scrape_row["metadata"])
                if isinstance(scrape_row["metadata"], str)
                else (scrape_row["metadata"] or {})
            )
            content_len = 0
            try:
                data = (
                    json.loads(scrape_row.get("data", "{}"))
                    if isinstance(scrape_row.get("data"), str)
                    else (scrape_row.get("data") or {})
                )
                content_len = len(data.get("content", ""))
            except Exception:
                content_len = 0
            scrape_info = {
                "raw_scrape_id": str(scrape_row["id"]),
                "url": scrape_row["url"],
                "scraped_at": str(scrape_row["created_at"])
                if scrape_row.get("created_at")
                else None,
                "content_length": content_len,
                "extraction_status": metadata.get("extraction_status"),
                "source_type": metadata.get("source_type"),
                "source_url": metadata.get("source_url"),
            }

        legislation_query = """
            SELECT l.id, l.bill_number, l.title, l.analysis_status, l.sufficiency_state,
                   l.insufficiency_reason, l.quantification_eligible
            FROM legislation l
            LEFT JOIN jurisdictions j ON l.jurisdiction_id = j.id
            WHERE LOWER(j.name) = LOWER($1)
              AND LOWER(l.bill_number) LIKE LOWER($2)
            ORDER BY l.created_at DESC
            LIMIT 1
        """
        leg_row = await db._fetchrow(legislation_query, jurisdiction, f"%{bill_id}%")
        leg_info = None
        if leg_row:
            leg_info = {
                "legislation_id": str(leg_row["id"]),
                "bill_number": leg_row["bill_number"],
                "title": leg_row["title"],
                "analysis_status": leg_row.get("analysis_status"),
                "sufficiency_state": leg_row.get("sufficiency_state"),
                "insufficiency_reason": leg_row.get("insufficiency_reason"),
                "quantification_eligible": leg_row.get("quantification_eligible"),
            }

        pipeline_query = """
            SELECT id, bill_id, status, started_at, completed_at, error, result, trigger_source
            FROM pipeline_runs
            WHERE LOWER(bill_id) LIKE LOWER($1)
            ORDER BY started_at DESC
            LIMIT 50
        """
        pipe_rows = await db._fetch(pipeline_query, f"%{bill_id}%")
        glass_box = GlassBoxService(db_client=db)

        def _pipe_info(row):
            if not row:
                return None
            result = (
                json.loads(row["result"])
                if isinstance(row["result"], str)
                else (row["result"] or {})
            )
            analysis = result.get("analysis", {})
            trigger_source = row.get("trigger_source", "manual")
            is_prefix_run = str(trigger_source).startswith("prefix:") or row.get(
                "status"
            ) == "prefix_halted"
            is_fixture_run = str(trigger_source).startswith("fixture:") or row.get(
                "status"
            ) == "fixture_invalid"
            run_label = None
            if str(trigger_source).startswith("prefix:"):
                run_label = str(trigger_source).split("prefix:", 1)[1]
            elif str(trigger_source).startswith("fixture:"):
                run_label = str(trigger_source).split("fixture:", 1)[1]
            return {
                "run_id": str(row["id"]),
                "status": row["status"],
                "started_at": str(row["started_at"]) if row.get("started_at") else None,
                "completed_at": str(row["completed_at"])
                if row.get("completed_at")
                else None,
                "error": row.get("error"),
                "trigger_source": trigger_source,
                "is_prefix_run": is_prefix_run,
                "is_fixture_run": is_fixture_run,
                "run_label": run_label,
                "sufficiency_breakdown": result.get("sufficiency_breakdown"),
                "source_text_present": result.get("source_text_present"),
                "rag_chunks_retrieved": result.get("rag_chunks_retrieved", 0),
                "quantification_eligible": result.get("quantification_eligible"),
                "aggregate_scenario_bounds": analysis.get("aggregate_scenario_bounds"),
            }

        latest_run = pipe_rows[0] if pipe_rows else None
        latest_completed_run = next(
            (row for row in pipe_rows if row.get("status") == "completed"), None
        )
        latest_failed_run = next(
            (row for row in pipe_rows if row.get("status") == "failed"), None
        )

        latest_run_info = _pipe_info(latest_run)

        async def _enrich_run(run_info):
            if not run_info:
                return None
            run_details = await glass_box.get_pipeline_run(run_info["run_id"])
            if run_details:
                run_info["prefix_boundary"] = run_details.get("prefix_boundary")
                run_info["mechanism_trace"] = run_details.get("mechanism_trace")
            return run_info

        latest_run_info = await _enrich_run(latest_run_info)
        latest_completed_info = await _enrich_run(_pipe_info(latest_completed_run))
        latest_failed_info = await _enrich_run(_pipe_info(latest_failed_run))

        return {
            "jurisdiction": jurisdiction,
            "bill_id": bill_id,
            "scrape": scrape_info,
            "legislation": leg_info,
            "pipeline_run": latest_run_info,
            "pipeline_runs": {
                "latest_run": latest_run_info,
                "latest_completed_run": latest_completed_info,
                "latest_failed_run": latest_failed_info,
            },
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Bill truth diagnostic failed: {str(e)}"
        )


# ============================================================================
# PIPELINE READ MODEL ENDPOINTS (bd-9qjof.5)
# ============================================================================


@router.get("/pipeline/jurisdictions/{jurisdiction_id}/status")
async def get_pipeline_jurisdiction_status(
    jurisdiction_id: str,
    source_family: str = DEFAULT_SOURCE_FAMILY,
    db: PostgresDB = Depends(get_db),
):
    """Backend-authored pipeline status for admin/frontend consumption."""
    try:
        jurisdiction = await find_jurisdiction(db, jurisdiction_id)
        jur_name = _to_text(jurisdiction["name"])
        jur_id = _to_text(jurisdiction["id"])
        normalized_source_family = _normalize_source_family(source_family)
        policy = _freshness_policy(normalized_source_family)

        run_query = """
            SELECT
                id,
                jurisdiction,
                status,
                started_at,
                completed_at,
                error,
                result,
                windmill_run_id
            FROM pipeline_runs
            WHERE LOWER(COALESCE(jurisdiction, '')) IN (LOWER($1), LOWER($2))
            ORDER BY started_at DESC
            LIMIT 1
        """
        latest_run = await db._fetchrow(run_query, jur_name, jur_id)

        latest_success_query = """
            SELECT completed_at
            FROM pipeline_runs
            WHERE LOWER(COALESCE(jurisdiction, '')) IN (LOWER($1), LOWER($2))
              AND status = 'completed'
              AND completed_at IS NOT NULL
            ORDER BY completed_at DESC
            LIMIT 1
        """
        latest_success = await db._fetchrow(latest_success_query, jur_name, jur_id)

        result = _json_payload(latest_run.get("result")) if latest_run else {}
        run_status = _to_text(latest_run.get("status")) if latest_run else ""
        counts = _extract_counts(result)
        latest_analysis = _extract_latest_analysis(result, counts)

        freshness_result = _json_payload(result.get("freshness"))
        freshness_status = _to_text(freshness_result.get("status")) or "unknown"
        freshness_alerts = freshness_result.get("alerts")
        if not isinstance(freshness_alerts, list):
            freshness_alerts = _extract_pipeline_alerts(result)
        pipeline_status = _derive_pipeline_status(run_status, freshness_status)

        response = {
            "contract_version": CONTRACT_VERSION,
            "jurisdiction_id": jur_id,
            "jurisdiction_name": jur_name,
            "source_family": normalized_source_family,
            "pipeline_status": pipeline_status,
            "last_success_at": str(latest_success["completed_at"])
            if latest_success and latest_success.get("completed_at")
            else None,
            "freshness": {
                "status": freshness_status,
                "fresh_hours": policy["fresh_hours"],
                "stale_usable_ceiling_hours": policy["stale_usable_ceiling_hours"],
                "fail_closed_ceiling_hours": policy["fail_closed_ceiling_hours"],
                "alerts": [_to_text(alert) for alert in freshness_alerts if _to_text(alert)],
            },
            "counts": counts,
            "latest_analysis": latest_analysis,
            "alerts": _extract_pipeline_alerts(result),
            "operator_links": {
                "windmill_run_url": _build_windmill_run_url(
                    latest_run.get("windmill_run_id") if latest_run else None
                ),
            },
        }
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch pipeline jurisdiction status: {str(e)}"
        )


@router.get("/pipeline/runs/{run_id}")
async def get_pipeline_run_read_model(run_id: str, db: PostgresDB = Depends(get_db)):
    """Return backend-authored run summary for pipeline UI."""
    try:
        row = await db._fetchrow(
            """
            SELECT
                id,
                bill_id,
                jurisdiction,
                status,
                started_at,
                completed_at,
                error,
                result,
                trigger_source,
                windmill_workspace,
                windmill_run_id,
                source_family
            FROM pipeline_runs
            WHERE id::text = $1
            LIMIT 1
            """,
            run_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Pipeline run not found")

        result = _json_payload(row.get("result"))
        counts = _extract_counts(result)
        return {
            "contract_version": CONTRACT_VERSION,
            "run_id": _to_text(row.get("id")),
            "status": _to_text(row.get("status")),
            "jurisdiction": _to_text(row.get("jurisdiction")),
            "source_family": _to_text(row.get("source_family")) or DEFAULT_SOURCE_FAMILY,
            "bill_id": _to_text(row.get("bill_id")) or None,
            "started_at": str(row["started_at"]) if row.get("started_at") else None,
            "completed_at": str(row["completed_at"]) if row.get("completed_at") else None,
            "error": _to_text(row.get("error")) or None,
            "trigger_source": _to_text(row.get("trigger_source")) or None,
            "counts": counts,
            "latest_analysis": _extract_latest_analysis(result, counts),
            "alerts": _extract_pipeline_alerts(result),
            "operator_links": {
                "windmill_workspace": _to_text(row.get("windmill_workspace")) or "affordabot",
                "windmill_run_url": _build_windmill_run_url(row.get("windmill_run_id")),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch pipeline run details: {str(e)}"
        )


@router.get("/pipeline/runs/{run_id}/steps")
async def get_pipeline_run_steps_read_model(
    run_id: str, db: PostgresDB = Depends(get_db)
):
    """Return run steps in a stable read-model shape."""
    try:
        rows = await db._fetch(
            """
            SELECT
                id,
                run_id,
                command,
                step_name,
                status,
                duration_ms,
                input_context,
                output_result,
                retry_class,
                decision_reason,
                alerts,
                refs,
                created_at
            FROM pipeline_steps
            WHERE run_id::text = $1
            ORDER BY created_at ASC
            """,
            run_id,
        )
        steps: list[dict[str, Any]] = []
        for row in rows:
            output_result = _json_payload(row.get("output_result"))
            step_alerts = output_result.get("alerts")
            if not isinstance(step_alerts, list):
                step_alerts = row.get("alerts")
            if not isinstance(step_alerts, list):
                step_alerts = []
            refs = output_result.get("refs")
            if not isinstance(refs, dict):
                refs = row.get("refs")
            if not isinstance(refs, dict):
                refs = {}
            decision_reason = _to_text(row.get("decision_reason")) or _to_text(
                output_result.get("decision_reason")
            )
            retry_class = _to_text(row.get("retry_class")) or _to_text(
                output_result.get("retry_class")
            )

            steps.append(
                {
                    "contract_version": CONTRACT_VERSION,
                    "step_id": _to_text(row.get("id")),
                    "run_id": _to_text(row.get("run_id")),
                    "command": _to_text(row.get("command"))
                    or _to_text(row.get("step_name")),
                    "status": _to_text(row.get("status")),
                    "decision_reason": decision_reason or None,
                    "retry_class": retry_class or "none",
                    "alerts": [_to_text(item) for item in step_alerts if _to_text(item)],
                    "counts": output_result.get("counts")
                    if isinstance(output_result.get("counts"), dict)
                    else {},
                    "refs": refs,
                    "duration_ms": _coerce_int(row.get("duration_ms")),
                    "error": _to_text(output_result.get("error")) or None,
                    "timestamp": str(row["created_at"]) if row.get("created_at") else None,
                }
            )
        return {"contract_version": CONTRACT_VERSION, "run_id": run_id, "steps": steps}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch pipeline run steps: {str(e)}"
        )


@router.get("/pipeline/runs/{run_id}/evidence")
async def get_pipeline_run_evidence(run_id: str, db: PostgresDB = Depends(get_db)):
    """Return evidence refs for a run without exposing storage internals."""
    try:
        row = await db._fetchrow(
            """
            SELECT id, result
            FROM pipeline_runs
            WHERE id::text = $1
            LIMIT 1
            """,
            run_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Pipeline run not found")

        result = _json_payload(row.get("result"))
        analysis = result.get("analysis")
        evidence_items: list[dict[str, Any]] = []
        if isinstance(analysis, dict):
            citations = analysis.get("citations")
            if isinstance(citations, list):
                for idx, citation in enumerate(citations):
                    citation_dict = citation if isinstance(citation, dict) else {"value": citation}
                    evidence_items.append(
                        {
                            "id": f"citation-{idx + 1}",
                            "type": _to_text(citation_dict.get("type")) or "citation",
                            "label": _to_text(citation_dict.get("label"))
                            or _to_text(citation_dict.get("source"))
                            or f"Citation {idx + 1}",
                            "confidence": citation_dict.get("confidence"),
                            "source_ref": _to_text(citation_dict.get("source_ref"))
                            or _to_text(citation_dict.get("source"))
                            or None,
                        }
                    )

        if not evidence_items:
            evidence_count = _coerce_int(result.get("validated_evidence_count"))
            for idx in range(evidence_count):
                evidence_items.append(
                    {
                        "id": f"evidence-{idx + 1}",
                        "type": "validated_chunk",
                        "label": f"Evidence {idx + 1}",
                        "confidence": None,
                        "source_ref": None,
                    }
                )

        return {
            "contract_version": CONTRACT_VERSION,
            "run_id": run_id,
            "evidence_count": len(evidence_items),
            "items": evidence_items,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch pipeline run evidence: {str(e)}"
        )


@router.post("/pipeline/jurisdictions/{jurisdiction_id}/refresh")
async def refresh_pipeline_jurisdiction(
    jurisdiction_id: str,
    source_family: str = DEFAULT_SOURCE_FAMILY,
    db: PostgresDB = Depends(get_db),
):
    """
    Backend-mediated manual refresh request.

    In Wave 2 this is an accepted contract endpoint; live Windmill trigger wiring
    is implemented in the integration wave.
    """
    try:
        jurisdiction = await find_jurisdiction(db, jurisdiction_id)
        normalized_source_family = _normalize_source_family(source_family)
        return {
            "contract_version": CONTRACT_VERSION,
            "status": "accepted",
            "decision_reason": "manual_refresh_queued",
            "jurisdiction_id": _to_text(jurisdiction["id"]),
            "jurisdiction_name": _to_text(jurisdiction["name"]),
            "source_family": normalized_source_family,
            "message": "Manual refresh accepted. Windmill dispatch wiring is pending integration.",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to queue manual refresh: {str(e)}"
        )


# ============================================================================
# STUB ENDPOINTS (Prevent 404s - TODO: Implement fully)
# ============================================================================


@router.get("/reviews")
async def list_reviews(request: Request):
    """List pipeline reviews. Stub endpoint."""
    db = get_db(request)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    # Return empty list for now - can be expanded later
    return {"reviews": [], "message": "Reviews endpoint - implementation pending"}


@router.post("/reviews/{review_id}")
async def update_review(review_id: str, request: Request):
    """Update a review. Stub endpoint."""
    return {
        "status": "success",
        "message": f"Review {review_id} update - implementation pending",
    }


@router.get("/models")
async def list_models(request: Request):
    """List available LLM models. Stub endpoint."""
    import os
    from services.llm.orchestrator import DEFAULT_OPENROUTER_FALLBACK_MODEL

    openrouter_model = (
        os.getenv("LLM_MODEL_FALLBACK_OPENROUTER")
        or DEFAULT_OPENROUTER_FALLBACK_MODEL
    )

    # Return configured models from environment
    return {
        "models": [
            {
                "id": "glm-4.7",
                "name": "GLM-4.7",
                "provider": "zai",
                "status": "active" if os.getenv("ZAI_API_KEY") else "unconfigured",
            },
            {
                "id": openrouter_model,
                "name": "OpenRouter Fallback",
                "provider": "openrouter",
                "status": "active"
                if os.getenv("OPENROUTER_API_KEY")
                else "unconfigured",
            },
        ]
    }


@router.get("/health/models")
async def check_model_health(request: Request):
    """Check health of LLM models. Stub endpoint."""
    import os

    return {
        "zai": "healthy" if os.getenv("ZAI_API_KEY") else "missing_key",
        "openrouter": "healthy" if os.getenv("OPENROUTER_API_KEY") else "missing_key",
    }


@router.post("/analyze")
async def run_analysis(request: Request):
    """Run ad-hoc analysis. Stub endpoint."""
    return {
        "status": "pending",
        "message": "Analysis endpoint - implementation pending. Use /scrape/{jurisdiction} for full pipeline.",
    }
