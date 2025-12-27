from fastapi import APIRouter, Depends, Request, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from services.glass_box import GlassBoxService, AgentStep, PipelineStep

router = APIRouter(prefix="/admin", tags=["admin"])


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
    system_prompt: str  # actual column name in DB
    description: Optional[str] = None
    version: int = 1
    is_active: bool = True


class PromptUpdate(BaseModel):
    type: str
    system_prompt: str  # match DB column name


def get_db(request: Request):
    """Get database client from app state."""
    return getattr(request.app.state, "db", None)


def get_glass_box_service(request: Request):
    # Retrieve DB from app state if initialized in main.py
    db = getattr(request.app.state, "db", None)
    return GlassBoxService(db_client=db, trace_dir=".traces")


# ============================================================================
# JURISDICTION ENDPOINTS
# ============================================================================

@router.get("/jurisdictions", response_model=List[Jurisdiction])
async def list_jurisdictions(request: Request):
    """List all jurisdictions."""
    db = get_db(request)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        rows = await db._fetch("SELECT id, name, type FROM jurisdictions ORDER BY name")
        return [
            Jurisdiction(
                id=str(row["id"]),
                name=row["name"],
                type=row["type"]
            )
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch jurisdictions: {str(e)}")


@router.get("/jurisdictions/{jurisdiction_id}")
async def get_jurisdiction(jurisdiction_id: str, request: Request):
    """Get jurisdiction detail by ID or slug."""
    db = get_db(request)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Normalize the input: convert slug-style to match partial names
        # e.g., 'california' matches 'State of California', 'san-jose' matches 'San Jose'
        search_term = jurisdiction_id.replace('-', ' ')
        
        # Try multiple matching strategies:
        # 1. Exact match by UUID id
        # 2. Exact name match (case-insensitive)
        # 3. Name contains the search term (for slugs like 'california' → 'State of California')
        row = await db._fetchrow(
            """
            SELECT id, name, type FROM jurisdictions 
            WHERE id::text = $1 
               OR LOWER(name) = LOWER($1)
               OR LOWER(name) = LOWER($2)
               OR LOWER(name) LIKE '%' || LOWER($2) || '%'
            LIMIT 1
            """,
            jurisdiction_id,
            search_term
        )
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Jurisdiction '{jurisdiction_id}' not found")
        
        # Get related counts - use string UUID for compatibility
        jur_id_str = str(row["id"])
        
        # Use try/except for counts to gracefully handle any schema issues
        try:
            # raw_scrapes doesn't have jurisdiction_id directly - join via sources
            bill_result = await db._fetchrow(
                """
                SELECT COUNT(*) as count FROM raw_scrapes rs
                JOIN sources s ON rs.source_id = s.id
                WHERE s.jurisdiction_id::text = $1
                """,
                jur_id_str
            )
            bill_count = bill_result["count"] if bill_result else 0
        except Exception:
            bill_count = 0
            
        try:
            source_result = await db._fetchrow(
                "SELECT COUNT(*) as count FROM sources WHERE jurisdiction_id::text = $1",
                jur_id_str
            )
            source_count = source_result["count"] if source_result else 0
        except Exception:
            source_count = 0
        
        return {
            "id": jur_id_str,
            "name": row["name"],
            "type": row["type"],
            "bill_count": bill_count,
            "source_count": source_count
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch jurisdiction: {str(e)}")


@router.get("/jurisdiction/{jurisdiction_id}/dashboard")
async def get_jurisdiction_dashboard(jurisdiction_id: str, request: Request):
    """Get jurisdiction dashboard stats - endpoint expected by frontend."""
    db = get_db(request)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Normalize the input: convert slug-style to match partial names
        search_term = jurisdiction_id.replace('-', ' ')
        
        # Find the jurisdiction
        row = await db._fetchrow(
            """
            SELECT id, name, type FROM jurisdictions 
            WHERE id::text = $1 
               OR LOWER(name) = LOWER($1)
               OR LOWER(name) = LOWER($2)
               OR LOWER(name) LIKE '%' || LOWER($2) || '%'
            LIMIT 1
            """,
            jurisdiction_id,
            search_term
        )
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Jurisdiction '{jurisdiction_id}' not found")
        
        jur_id_str = str(row["id"])
        jurisdiction_name = row["name"]
        
        # Get raw scrapes count
        try:
            raw_result = await db._fetchrow(
                """
                SELECT COUNT(*) as count FROM raw_scrapes rs
                JOIN sources s ON rs.source_id = s.id
                WHERE s.jurisdiction_id::text = $1
                """,
                jur_id_str
            )
            total_raw_scrapes = raw_result["count"] if raw_result else 0
        except Exception:
            total_raw_scrapes = 0
        
        # Get processed scrapes (legislation count)
        try:
            processed_result = await db._fetchrow(
                "SELECT COUNT(*) as count FROM legislation WHERE jurisdiction_id::text = $1",
                jur_id_str
            )
            processed_scrapes = processed_result["count"] if processed_result else 0
        except Exception:
            processed_scrapes = 0
        
        # Get total bills (same as legislation for now)
        total_bills = processed_scrapes
        
        # Get last scrape timestamp
        try:
            last_scrape_result = await db._fetchrow(
                """
                SELECT MAX(rs.created_at) as last_scrape FROM raw_scrapes rs
                JOIN sources s ON rs.source_id = s.id
                WHERE s.jurisdiction_id::text = $1
                """,
                jur_id_str
            )
            last_scrape = str(last_scrape_result["last_scrape"]) if last_scrape_result and last_scrape_result["last_scrape"] else None
        except Exception:
            last_scrape = None
        
        # Determine pipeline status based on data
        if total_raw_scrapes > 0 and last_scrape:
            pipeline_status = "healthy"
        elif total_raw_scrapes > 0:
            pipeline_status = "degraded"
        else:
            pipeline_status = "unknown"
        
        # Check for alerts (no active scraping issues for now)
        active_alerts = []
        
        return {
            "jurisdiction": jurisdiction_name,
            "last_scrape": last_scrape,
            "total_raw_scrapes": total_raw_scrapes,
            "processed_scrapes": processed_scrapes,
            "total_bills": total_bills,
            "pipeline_status": pipeline_status,
            "active_alerts": active_alerts
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch dashboard: {str(e)}")


# ============================================================================
# PROMPTS ENDPOINTS
# ============================================================================

@router.get("/prompts", response_model=List[Prompt])
async def list_prompts(request: Request):
    """List all active prompts."""
    db = get_db(request)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        rows = await db._fetch(
            "SELECT id, prompt_type, system_prompt, description, version, is_active FROM system_prompts WHERE is_active = true ORDER BY prompt_type"
        )
        return [
            Prompt(
                id=str(row["id"]) if row.get("id") else None,
                prompt_type=row["prompt_type"],
                system_prompt=row["system_prompt"],
                description=row.get("description"),
                version=row["version"],
                is_active=row["is_active"]
            )
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch prompts: {str(e)}")


@router.get("/prompts/{prompt_type}")
async def get_prompt(prompt_type: str, request: Request):
    """Get a specific prompt by type."""
    db = get_db(request)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        row = await db._fetchrow(
            "SELECT id, prompt_type, system_prompt, description, version, is_active FROM system_prompts WHERE prompt_type = $1 AND is_active = true",
            prompt_type
        )
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Prompt type '{prompt_type}' not found")
        
        return Prompt(
            id=str(row["id"]) if row.get("id") else None,
            prompt_type=row["prompt_type"],
            system_prompt=row["system_prompt"],
            description=row.get("description"),
            version=row["version"],
            is_active=row["is_active"]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch prompt: {str(e)}")


@router.post("/prompts")
async def update_prompt(prompt: PromptUpdate, request: Request):
    """Update or create a prompt."""
    db = get_db(request)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Use the existing update_system_prompt method
        result = await db.update_system_prompt(prompt.type, prompt.system_prompt)
        return {"success": True, "message": "Prompt updated", "version": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update prompt: {str(e)}")


# ============================================================================
# SCRAPES ENDPOINTS
# ============================================================================

@router.get("/scrapes")
async def list_scrapes(request: Request, limit: int = 50):
    """List recent scrapes."""
    db = get_db(request)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # raw_scrapes has: id, source_id, content_hash, content_type, data, url, metadata, storage_uri, document_id, created_at
        rows = await db._fetch(
            """
            SELECT rs.id, rs.url, rs.created_at, rs.metadata, s.jurisdiction_id, j.name as jurisdiction_name
            FROM raw_scrapes rs
            LEFT JOIN sources s ON rs.source_id = s.id
            LEFT JOIN jurisdictions j ON s.jurisdiction_id = j.id::text
            ORDER BY rs.created_at DESC
            LIMIT $1
            """,
            limit
        )
        return [
            {
                "id": str(row["id"]),
                "url": row["url"],
                "scraped_at": str(row["created_at"]) if row.get("created_at") else None,
                "jurisdiction_id": str(row["jurisdiction_id"]) if row.get("jurisdiction_id") else None,
                "jurisdiction_name": row["jurisdiction_name"],
                "metadata": row["metadata"]
            }
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch scrapes: {str(e)}")


# ============================================================================
# DASHBOARD STATS ENDPOINT
# ============================================================================

@router.get("/stats")
async def get_dashboard_stats(request: Request):
    """Get dashboard statistics."""
    db = get_db(request)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Get counts from various tables
        jurisdiction_count = await db._fetchrow("SELECT COUNT(*) as count FROM jurisdictions")
        scrape_count = await db._fetchrow("SELECT COUNT(*) as count FROM raw_scrapes")
        source_count = await db._fetchrow("SELECT COUNT(*) as count FROM sources")
        chunk_count = await db._fetchrow("SELECT COUNT(*) as count FROM document_chunks")
        
        return {
            "jurisdictions": jurisdiction_count["count"] if jurisdiction_count else 0,
            "scrapes": scrape_count["count"] if scrape_count else 0,
            "sources": source_count["count"] if source_count else 0,
            "chunks": chunk_count["count"] if chunk_count else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")


# ============================================================================
# GLASS BOX ENDPOINTS (existing)
# ============================================================================

@router.get("/traces/{query_id}", response_model=List[AgentStep])
async def get_agent_traces(
    query_id: str,
    service: GlassBoxService = Depends(get_glass_box_service)
):
    """Get full execution trace for a specific agent session."""
    return await service.get_traces_for_query(query_id)


@router.get("/traces", response_model=List[str])
async def list_agent_sessions(
    service: GlassBoxService = Depends(get_glass_box_service)
):
    """List all recorded agent sessions."""
    return await service.list_queries()


@router.get("/runs/{run_id}/steps", response_model=List[PipelineStep])
async def get_run_steps(
    run_id: str,
    service: GlassBoxService = Depends(get_glass_box_service)
):
    """
    Get granular execution steps for a pipeline run.
    """
    return await service.get_pipeline_steps(run_id)
