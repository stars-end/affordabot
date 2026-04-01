from fastapi import APIRouter, Depends, Request, HTTPException
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
import json
from services.glass_box import GlassBoxService, AgentStep, PipelineStep
from auth.clerk import require_admin_user
from db.postgres_client import PostgresDB

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_user)],
)


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


def _parse_json_object(value: Any) -> Dict[str, Any]:
    """Parse a JSON-ish value into an object without raising."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _collect_recent_errors(*values: Any) -> List[str]:
    """Return unique, compact error strings in first-seen order."""
    seen = set()
    errors: List[str] = []
    for raw in values:
        text = str(raw or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        errors.append(text)
    return errors[:5]


def _is_failure_stage(stage: Optional[str]) -> bool:
    normalized = (stage or "").strip().lower()
    if not normalized:
        return False
    if normalized.endswith("_failed") or normalized.endswith("_exception"):
        return True
    return normalized in {
        "parse_failed_no_text",
        "validation_failed",
        "chunk_failed_empty",
        "vector_upserted_not_retrievable",
    }


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


@router.get("/substrate-health")
async def get_substrate_health(
    db: PostgresDB = Depends(get_db),
    limit: int = 100,
    promotion_state: Optional[str] = None,
    trust_tier: Optional[str] = None,
    ingestion_stage: Optional[str] = None,
    include_legacy: bool = True,
):
    """Operator QA surface: promotion truth + ingestion truth in one place."""
    try:
        safe_limit = max(1, min(limit, 500))
        rows = await db._fetch(
            """
            SELECT
                rs.id,
                rs.created_at,
                rs.url AS scrape_url,
                rs.content_hash,
                rs.error_message,
                rs.processed,
                rs.document_id::text AS scrape_document_id,
                rs.metadata AS scrape_metadata,
                s.name AS source_name,
                s.url AS source_url,
                s.metadata AS source_metadata,
                s.jurisdiction_id,
                j.name AS jurisdiction_name,
                COALESCE(dc.chunk_count, 0) AS chunk_count
            FROM raw_scrapes rs
            LEFT JOIN sources s ON rs.source_id = s.id
            LEFT JOIN jurisdictions j ON s.jurisdiction_id::text = j.id::text
            LEFT JOIN (
                SELECT document_id::text AS document_id, COUNT(*) AS chunk_count
                FROM document_chunks
                GROUP BY document_id::text
            ) dc ON dc.document_id = COALESCE(
                rs.document_id::text,
                rs.metadata::jsonb #>> '{ingestion_truth,document_id}',
                rs.metadata::jsonb->>'document_id'
            )
            ORDER BY rs.created_at DESC
            LIMIT $1
            """,
            safe_limit,
        )

        records = []
        promoted_count = 0
        preserved_count = 0
        candidate_count = 0
        failed_count = 0
        legacy_unknown_count = 0
        retrievable_count = 0

        state_filter = (promotion_state or "").strip().lower()
        tier_filter = (trust_tier or "").strip().lower()
        stage_filter = (ingestion_stage or "").strip().lower()

        for row in rows:
            scrape_metadata = _parse_json_object(row.get("scrape_metadata"))
            source_metadata = _parse_json_object(row.get("source_metadata"))
            ingestion_truth = _parse_json_object(scrape_metadata.get("ingestion_truth"))

            record_promotion_state = scrape_metadata.get("promotion_state")
            record_promotion_method = scrape_metadata.get("promotion_method")
            record_promotion_reason = scrape_metadata.get("promotion_reason_category")
            record_trust_tier = (
                scrape_metadata.get("trust_tier")
                or source_metadata.get("trust_tier")
                or "unknown"
            )
            record_ingestion_stage = (
                ingestion_truth.get("stage")
                or scrape_metadata.get("extraction_status")
                or "unknown"
            )
            retrievable_value = ingestion_truth.get("retrievable")
            chunk_count = int(row.get("chunk_count") or 0)
            retrievable = (
                bool(retrievable_value)
                if isinstance(retrievable_value, (bool, int))
                else chunk_count > 0
            )
            recent_errors = _collect_recent_errors(
                row.get("error_message"),
                scrape_metadata.get("promotion_error"),
                scrape_metadata.get("extraction_error"),
                ingestion_truth.get("last_error"),
                ingestion_truth.get("ingest_skipped_reason"),
            )
            last_error = recent_errors[0] if recent_errors else None
            legacy_unknown = bool(
                record_promotion_reason == "legacy_unknown"
                or (
                    not ingestion_truth
                    and record_promotion_state is None
                    and record_ingestion_stage == "unknown"
                )
            )

            if state_filter and (record_promotion_state or "").strip().lower() != state_filter:
                continue
            if tier_filter and (record_trust_tier or "").strip().lower() != tier_filter:
                continue
            if stage_filter and (record_ingestion_stage or "").strip().lower() != stage_filter:
                continue
            if not include_legacy and legacy_unknown:
                continue

            if record_promotion_state == "promoted_substrate":
                promoted_count += 1
            elif record_promotion_state == "durable_raw":
                preserved_count += 1
            elif record_promotion_state == "captured_candidate":
                candidate_count += 1

            if legacy_unknown:
                legacy_unknown_count += 1
            if retrievable:
                retrievable_count += 1
            if _is_failure_stage(record_ingestion_stage) or bool(last_error):
                failed_count += 1

            document_id = (
                row.get("scrape_document_id")
                or ingestion_truth.get("document_id")
                or scrape_metadata.get("document_id")
            )

            records.append(
                {
                    "id": str(row["id"]),
                    "scraped_at": str(row["created_at"]) if row.get("created_at") else None,
                    "jurisdiction": row.get("jurisdiction_name"),
                    "jurisdiction_id": str(row["jurisdiction_id"])
                    if row.get("jurisdiction_id")
                    else None,
                    "source_name": row.get("source_name") or scrape_metadata.get("source_name"),
                    "source_url": row.get("source_url"),
                    "canonical_url": scrape_metadata.get("canonical_url")
                    or scrape_metadata.get("source_url")
                    or row.get("scrape_url")
                    or row.get("source_url"),
                    "document_id": str(document_id) if document_id else None,
                    "document_type": scrape_metadata.get("document_type") or "unknown",
                    "content_class": scrape_metadata.get("content_class") or "unknown",
                    "trust_host_classification": scrape_metadata.get("trust_host_classification")
                    or "unknown",
                    "trust_tier": record_trust_tier,
                    "promotion_state": record_promotion_state,
                    "promotion_method": record_promotion_method,
                    "promotion_reason_category": record_promotion_reason,
                    "ingestion_stage": record_ingestion_stage,
                    "retrievable": retrievable,
                    "processed": row.get("processed"),
                    "chunk_count": chunk_count,
                    "content_hash": row.get("content_hash"),
                    "last_error": last_error,
                    "recent_errors": recent_errors,
                    "legacy_unknown": legacy_unknown,
                }
            )

        total_records = len(records)
        return {
            "summary": {
                "total_records": total_records,
                "captured_candidate_count": candidate_count,
                "durable_raw_count": preserved_count,
                "promoted_substrate_count": promoted_count,
                "failed_count": failed_count,
                "legacy_unknown_count": legacy_unknown_count,
                "retrievable_count": retrievable_count,
                "non_retrievable_count": total_records - retrievable_count,
            },
            "filters": {
                "limit": safe_limit,
                "promotion_state": promotion_state,
                "trust_tier": trust_tier,
                "ingestion_stage": ingestion_stage,
                "include_legacy": include_legacy,
            },
            "records": records,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch substrate health: {str(e)}"
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
