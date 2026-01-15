from fastapi import APIRouter, Depends, Request, HTTPException
from typing import List, Optional
from pydantic import BaseModel
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
    search_term = jurisdiction_id.replace('-', ' ')
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
        raise HTTPException(status_code=404, detail=f"Jurisdiction '{jurisdiction_id}' not found")
    return row

async def get_count(db: PostgresDB, query: str, *args):
    """Execute a count query and return the result or 0."""
    try:
        result = await db._fetchrow(query, *args)
        return result["count"] if result else 0
    except Exception:
        return 0

# ============================================================================
# JURISDICTION ENDPOINTS
# ============================================================================

@router.get("/jurisdictions", response_model=List[Jurisdiction])
async def list_jurisdictions(db: PostgresDB = Depends(get_db)):
    """List all jurisdictions."""
    try:
        rows = await db._fetch("SELECT id, name, type FROM jurisdictions ORDER BY name")
        return [Jurisdiction(id=str(row["id"]), name=row["name"], type=row["type"]) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch jurisdictions: {str(e)}")


@router.get("/jurisdictions/{jurisdiction_id}", response_model=JurisdictionDetail)
async def get_jurisdiction(jurisdiction_id: str, db: PostgresDB = Depends(get_db)):
    """Get jurisdiction detail by ID or slug."""
    try:
        row = await find_jurisdiction(db, jurisdiction_id)
        jur_id_str = str(row["id"])
        
        bill_count = await get_count(
            db,
            "SELECT COUNT(*) as count FROM raw_scrapes rs JOIN sources s ON rs.source_id = s.id WHERE s.jurisdiction_id::text = $1",
            jur_id_str
        )
        source_count = await get_count(db, "SELECT COUNT(*) as count FROM sources WHERE jurisdiction_id::text = $1", jur_id_str)
        
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
        raise HTTPException(status_code=500, detail=f"Failed to fetch jurisdiction: {str(e)}")


@router.get("/jurisdiction/{jurisdiction_id}/dashboard")
async def get_jurisdiction_dashboard(jurisdiction_id: str, db: PostgresDB = Depends(get_db)):
    """Get jurisdiction dashboard stats."""
    try:
        row = await find_jurisdiction(db, jurisdiction_id)
        jur_id_str = str(row["id"])

        total_raw_scrapes = await get_count(
            db,
            "SELECT COUNT(*) as count FROM raw_scrapes rs JOIN sources s ON rs.source_id = s.id WHERE s.jurisdiction_id::text = $1",
            jur_id_str,
        )
        processed_scrapes = await get_count(db, "SELECT COUNT(*) as count FROM legislation WHERE jurisdiction_id::text = $1", jur_id_str)
        
        last_scrape_result = await db._fetchrow(
            "SELECT MAX(rs.created_at) as last_scrape FROM raw_scrapes rs JOIN sources s ON rs.source_id = s.id WHERE s.jurisdiction_id::text = $1",
            jur_id_str
        )
        last_scrape = str(last_scrape_result["last_scrape"]) if last_scrape_result and last_scrape_result["last_scrape"] else None
        
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
        raise HTTPException(status_code=500, detail=f"Failed to fetch dashboard: {str(e)}")

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
        raise HTTPException(status_code=500, detail=f"Failed to fetch prompts: {str(e)}")

@router.get("/prompts/{prompt_type}", response_model=Prompt)
async def get_prompt(prompt_type: str, db: PostgresDB = Depends(get_db)):
    """Get a specific prompt by type."""
    try:
        query = "SELECT id, prompt_type, system_prompt, description, version, is_active FROM system_prompts WHERE prompt_type = $1 AND is_active = true"
        row = await db._fetchrow(query, prompt_type)
        if not row:
            raise HTTPException(status_code=404, detail=f"Prompt type '{prompt_type}' not found")
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
        raise HTTPException(status_code=500, detail=f"Failed to update prompt: {str(e)}")

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
            LEFT JOIN jurisdictions j ON s.jurisdiction_id = j.id
            ORDER BY rs.created_at DESC
            LIMIT $1
        """
        rows = await db._fetch(query, limit)
        return [
            {
                "id": str(row["id"]),
                "url": row["url"],
                "scraped_at": str(row["created_at"]) if row.get("created_at") else None,
                "jurisdiction_id": str(row["jurisdiction_id"]) if row.get("jurisdiction_id") else None,
                "jurisdiction_name": row["jurisdiction_name"],
                "metadata": row["metadata"],
            }
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch scrapes: {str(e)}")

# ============================================================================
# DASHBOARD STATS ENDPOINT
# ============================================================================

@router.get("/stats")
async def get_dashboard_stats(db: PostgresDB = Depends(get_db)):
    """Get dashboard statistics."""
    try:
        return {
            "jurisdictions": await get_count(db, "SELECT COUNT(*) as count FROM jurisdictions"),
            "scrapes": await get_count(db, "SELECT COUNT(*) as count FROM raw_scrapes"),
            "sources": await get_count(db, "SELECT COUNT(*) as count FROM sources"),
            "chunks": await get_count(db, "SELECT COUNT(*) as count FROM document_chunks"),
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
    return {"status": "success", "message": f"Review {review_id} update - implementation pending"}


@router.get("/models")
async def list_models(request: Request):
    """List available LLM models. Stub endpoint."""
    import os
    
    # Return configured models from environment
    return {
        "models": [
            {
                "id": "glm-4.7",
                "name": "GLM-4.7",
                "provider": "zai",
                "status": "active" if os.getenv("ZAI_API_KEY") else "unconfigured"
            },
            {
                "id": "gemini-2.0-flash-exp",
                "name": "Gemini 2.0 Flash",
                "provider": "openrouter",
                "status": "active" if os.getenv("OPENROUTER_API_KEY") else "unconfigured"
            }
        ]
    }


@router.get("/health/models")
async def check_model_health(request: Request):
    """Check health of LLM models. Stub endpoint."""
    import os
    
    return {
        "zai": "healthy" if os.getenv("ZAI_API_KEY") else "missing_key",
        "openrouter": "healthy" if os.getenv("OPENROUTER_API_KEY") else "missing_key"
    }


@router.post("/analyze")
async def run_analysis(request: Request):
    """Run ad-hoc analysis. Stub endpoint."""
    return {
        "status": "pending",
        "message": "Analysis endpoint - implementation pending. Use /scrape/{jurisdiction} for full pipeline."
    }

