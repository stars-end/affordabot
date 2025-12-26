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
        # Try to find by ID first, then by name/slug
        row = await db._fetchrow(
            "SELECT id, name, type FROM jurisdictions WHERE id::text = $1 OR LOWER(name) = LOWER($1)",
            jurisdiction_id
        )
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Jurisdiction '{jurisdiction_id}' not found")
        
        # Get related counts
        jur_id = row["id"]
        bill_count = await db._fetchrow(
            "SELECT COUNT(*) as count FROM raw_scrapes WHERE jurisdiction_id = $1",
            jur_id
        )
        source_count = await db._fetchrow(
            "SELECT COUNT(*) as count FROM sources WHERE jurisdiction_id = $1",
            jur_id
        )
        
        return {
            "id": str(row["id"]),
            "name": row["name"],
            "type": row["type"],
            "bill_count": bill_count["count"] if bill_count else 0,
            "source_count": source_count["count"] if source_count else 0
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch jurisdiction: {str(e)}")


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
            LEFT JOIN jurisdictions j ON s.jurisdiction_id = j.id
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

