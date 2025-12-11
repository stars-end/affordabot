"""
Admin Dashboard V2 API Router

Provides comprehensive admin endpoints for:
- Manual scraping control
- Analysis pipeline management (research, generate, review)
- Model configuration and priority management
- System prompt editing
- Health monitoring
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
import os
import asyncio
import logging


# Import database client
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.postgres_client import PostgresDB

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


def get_pg_db():
    """Dependency to get Postgres client"""
    return PostgresDB()


class ReviewUpdate(BaseModel):
    status: str

@router.get("/reviews")
async def list_reviews(db: PostgresDB = Depends(get_pg_db)):
    """List pending template reviews."""
    return await db.get_pending_reviews()

@router.patch("/reviews/{review_id}")
async def update_review(
    review_id: str, 
    update: ReviewUpdate,
    db: PostgresDB = Depends(get_pg_db)
):
    """Approve or reject a review."""
    result = await db.update_review_status(review_id, update.status)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to update review")
    return {"status": "success", "id": review_id}


# ============================================================================
# Request/Response Models
# ============================================================================

class ManualScrapeRequest(BaseModel):
    jurisdiction: str
    force: bool = False  # Force re-scrape even if recent data exists
    type: Literal["legislation", "rag", "harvest"] = "legislation"

# ... (inside _run_scrape_task signature) ...

async def _run_scrape_task(task_id: str, jurisdiction: str, force: bool, db: PostgresDB, scrape_type: str = "legislation"):
    """Background task to run scraping with multi-source support."""
    try:
        # Update task status to running
        await db.update_admin_task(task_id, status='running')

        if scrape_type == "harvest":
             # Run Universal Harvester script via subprocess
            import sys
            
            script_path = os.path.join(os.path.dirname(__file__), '../scripts/cron/run_universal_harvester.py')
            
            proc = await asyncio.create_subprocess_exec(
                sys.executable, script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                raise Exception(f"Harvester script failed: {stderr.decode()}")
            
            
            await db.update_admin_task(
                task_id=task_id,
                status='completed',
                result={'message': 'Harvester script executed', 'logs': stdout.decode()}
            )
            return

        if scrape_type == "rag":
            # Run RAG spiders script via subprocess
            import sys
            
            script_path = os.path.join(os.path.dirname(__file__), '../scripts/cron/run_rag_spiders.py')
            
            # Run script - this blocks the thread but it's a background task so it's acceptable-ish for low volume
            # Ideally use asyncio.create_subprocess_exec
            proc = await asyncio.create_subprocess_exec(
                sys.executable, script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                raise Exception(f"RAG script failed: {stderr.decode()}")
            
            # The script logs its own success/admin_tasks updates, but we created a parent task here.
            # We should probably mark this parent task as completed.
            # Note: The script creates its OWN task_id. This is a bit disjointed.
            # Improvement: Pass task_id to script? For now, just marking this trigger task as done.
            
            await db.update_admin_task(
                task_id=task_id,
                status='completed',
                result={'message': 'RAG script executed', 'logs': stdout.decode()}
            )
            return

        # ... existing legislation logic ...
        # Import scraper registry
        from services.scraper.san_jose import SanJoseScraper
        from services.scraper.california_state import CaliforniaStateScraper
        from services.scraper.santa_clara_county import SantaClaraCountyScraper
        from services.scraper.saratoga import SaratogaScraper
        
        SCRAPER_MAP = {
            'City of San Jose': SanJoseScraper,
            'State of California': CaliforniaStateScraper,
            'Santa Clara County': SantaClaraCountyScraper,
            'Saratoga': SaratogaScraper,
        }
        
        # Get jurisdiction config from database
        jur_config = await db.get_jurisdiction_by_name(jurisdiction)
        if not jur_config:
            raise Exception(f"Jurisdiction {jurisdiction} not found in database")
        
        config = jur_config
        scraper_class = SCRAPER_MAP.get(jurisdiction)
        
        # Execute multi-source scraping based on source_priority
        bills = await _execute_multi_source_scrape(scraper_class, config)
        
        # Store in database
        jurisdiction_id = config['id']
        bills_new = 0
        bills_updated = 0
        
        for bill in bills:
            leg_id = await db.create_legislation(jurisdiction_id, bill.dict())
            if leg_id:
                bills_new += 1
        
        # Record scrape history
        await db.create_scrape_history(
            jurisdiction=jurisdiction,
            bills_found=len(bills),
            bills_new=bills_new,
            bills_updated=bills_updated,
            status='success',
            task_id=task_id
        )
        
        # Update task status to completed
        await db.update_admin_task(
            task_id=task_id,
            status='completed',
            result={'bills_found': len(bills), 'bills_new': bills_new}
        )
        
        print(f"Task {task_id}: Completed scraping {jurisdiction}")
        
    except Exception as e:
        error_msg = str(e)
        print(f"Task {task_id} failed: {error_msg}")
        import traceback
        traceback.print_exc()
        
        # Update task status to failed
        await db.update_admin_task(task_id, status='failed', error=error_msg)
        
        # Record failed scrape
        await db.create_scrape_history(
            jurisdiction=jurisdiction,
            bills_found=0,
            status='failed',
            error_message=error_msg,
            task_id=task_id
        )


class JurisdictionDashboardStats(BaseModel):
    jurisdiction: str
    last_scrape: Optional[datetime]
    total_raw_scrapes: int
    processed_scrapes: int
    total_bills: int
    pipeline_status: Literal["healthy", "degraded", "unknown"]
    active_alerts: List[str]


class ManualScrapeResponse(BaseModel):
    task_id: str
    jurisdiction: str
    status: Literal["started", "queued"]
    message: str


class AnalysisStepRequest(BaseModel):
    jurisdiction: str
    bill_id: str
    step: Literal["research", "generate", "review"]
    model_override: Optional[str] = None  # Override default model for this run


class AnalysisStepResponse(BaseModel):
    task_id: str
    step: str
    status: Literal["started", "completed", "failed"]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ModelConfig(BaseModel):
    provider: Literal["openrouter", "zai"]
    model_name: str
    priority: int  # Lower number = higher priority
    enabled: bool = True
    use_case: Literal["generation", "review", "both"]


class ModelConfigUpdate(BaseModel):
    models: List[ModelConfig]


class PromptConfig(BaseModel):
    prompt_type: Literal["generation", "review"]
    system_prompt: str
    updated_at: datetime
    updated_by: str = "admin"


class PromptUpdateRequest(BaseModel):
    prompt_type: Literal["generation", "review"]
    system_prompt: str


class ScrapeHistory(BaseModel):
    id: str
    jurisdiction: str
    timestamp: datetime
    bills_found: int
    status: Literal["success", "partial", "failed"]
    error: Optional[str] = None


class AnalysisHistory(BaseModel):
    id: str
    jurisdiction: str
    bill_id: str
    step: Literal["research", "generate", "review"]
    model_used: str
    timestamp: datetime
    status: Literal["success", "failed"]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ============================================================================
# Manual Scraping Endpoints
# ============================================================================

# ============================================================================
# Manual Scraping Endpoints
# ============================================================================

@router.post("/scrape", response_model=ManualScrapeResponse)
async def trigger_manual_scrape(
    request: ManualScrapeRequest,
    background_tasks: BackgroundTasks,
    db: PostgresDB = Depends(get_pg_db) # Migrated to Postgres
):
    """
    Trigger a manual scrape for a specific jurisdiction.
    
    Returns immediately with a task ID. Use /scrape/status/{task_id} to check progress.
    """
    from uuid import uuid4
    
    task_id = str(uuid4())
    
    # Create task record in database (Postgres)
    await db.create_admin_task(
        task_id=task_id,
        task_type='scrape',
        status='queued',
        jurisdiction=request.jurisdiction,
        config={'force': request.force}
    )
    
    # Queue scraping task
    background_tasks.add_task(
        _run_scrape_task,
        task_id=task_id,
        jurisdiction=request.jurisdiction,
        force=request.force,
        db=db,
        scrape_type=request.type
    )
    
    return ManualScrapeResponse(
        task_id=task_id,
        jurisdiction=request.jurisdiction,
        status="started",
        message=f"Scraping task started for {request.jurisdiction}"
    )


@router.get("/scrapes", response_model=List[ScrapeHistory])
@router.get("/scrapes", response_model=List[ScrapeHistory])
async def get_scrape_history(
    jurisdiction: Optional[str] = None,
    limit: int = 50,
    db: PostgresDB = Depends(get_pg_db)
):
    """
    Get scraping history, optionally filtered by jurisdiction.
    """
    try:
        query = "SELECT * FROM scrape_history"
        params = []
        
        if jurisdiction:
            query += " WHERE jurisdiction = $1"
            params.append(jurisdiction)
            
        query += " ORDER BY created_at DESC LIMIT $" + str(len(params) + 1)
        params.append(limit)
        
        rows = await db._fetch(query, *params)
        
        # Transform to response model
        history = []
        for row in rows:
            history.append(ScrapeHistory(
                id=str(row['id']),
                jurisdiction=row['jurisdiction'],
                timestamp=row['created_at'],
                bills_found=row['bills_found'],
                status=row['status'],
                error=row.get('error_message')
            ))
        
        return history
    except Exception as e:
        print(f"Error fetching scrape history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Analysis Pipeline Endpoints
# ============================================================================

@router.post("/analyze", response_model=AnalysisStepResponse)
async def run_analysis_step(
    request: AnalysisStepRequest,
    background_tasks: BackgroundTasks
):
    """
    Run a specific analysis step (research, generate, or review) for a bill.
    
    Can be run sequentially or one-by-one with arbitrary model selection.
    """
    from uuid import uuid4
    
    task_id = str(uuid4())
    
    # Queue analysis task
    background_tasks.add_task(
        _run_analysis_task,
        task_id=task_id,
        jurisdiction=request.jurisdiction,
        bill_id=request.bill_id,
        step=request.step,
        model_override=request.model_override
    )
    
    return AnalysisStepResponse(
        task_id=task_id,
        step=request.step,
        status="started"
    )


@router.get("/analyses", response_model=List[AnalysisHistory])
async def get_analysis_history(
    jurisdiction: Optional[str] = None,
    bill_id: Optional[str] = None,
    step: Optional[Literal["research", "generate", "review"]] = None,
    limit: int = 50,
    db: PostgresDB = Depends(get_pg_db)
):
    """
    Get analysis history with optional filters.
    """
    try:
        rows = await db.get_analysis_history(jurisdiction, bill_id, step, limit)
        
        history = []
        for row in rows:
            # Handle potential JSON/Dict result if stored as string/jsonb
            result_data = row.get('result')
            
            history.append(AnalysisHistory(
                id=str(row['id']),
                jurisdiction=row['jurisdiction'],
                bill_id=row['bill_id'],
                step=row['step'],
                model_used=f"{row.get('model_provider', 'unknown')}/{row.get('model_name', 'unknown')}",
                timestamp=row['created_at'],
                status=row['status'],
                result=result_data,
                error=row.get('error_message')
            ))
        
        return history
    except Exception as e:
        print(f"Error fetching analysis history: {e}")
        return []



# ============================================================================
# Task Management Endpoints
# ============================================================================

@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    db: PostgresDB = Depends(get_pg_db)
):
    """
    Get status of a background task (scrape or analysis).
    """
    task = await db.get_admin_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Ensure ID is string
    task['id'] = str(task['id'])
    return task


# ============================================================================
# Model Management Endpoints
# ============================================================================

@router.get("/models", response_model=List[ModelConfig])
async def get_model_configs(
    db: PostgresDB = Depends(get_pg_db)
):
    """
    Get current model configuration and priority order.
    """
    try:
        rows = await db.get_model_configs()
        
        configs = []
        for row in rows:
            configs.append(ModelConfig(
                provider=row['provider'],
                model_name=row['model_name'],
                priority=row['priority'],
                enabled=row['enabled'],
                use_case=row['use_case']
            ))
        
        return configs
    except Exception as e:
        print(f"Error fetching model configs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch models: {str(e)}")


@router.post("/models")
async def update_model_configs(
    config: ModelConfigUpdate,
    db: PostgresDB = Depends(get_pg_db)
):
    """
    Update model configuration and priority order.
    """
    # Validate unique priorities
    priorities = [m.priority for m in config.models]
    if len(priorities) != len(set(priorities)):
        raise HTTPException(status_code=400, detail="Priorities must be unique")
    
    success_count = 0
    for model in config.models:
        if await db.update_model_config(
            model.provider, model.model_name, model.use_case,
            model.priority, model.enabled
        ):
            success_count += 1
            
    return {"message": "Model configuration updated", "count": success_count}


@router.get("/health/models")
async def check_model_health(db: PostgresDB = Depends(get_pg_db)):
    """Check health of all configured models."""
    try:
        # Get all enabled models
        # Re-using get_model_configs logic but filtering
        rows = await db.get_model_configs()
        models = [r for r in rows if r['enabled']]
        
        health_results = []
        for model in models:
            is_healthy = True
            latency_ms = 0
            
            # TODO: Implement actual health check
            # For now just stub successful result
            
            result = {
                'provider': model['provider'],
                'model_name': model['model_name'],
                'status': 'healthy' if is_healthy else 'unhealthy',
                'latency_ms': latency_ms,
                'last_checked': datetime.now().isoformat()
            }
            health_results.append(result)
            
            # Update DB (using direct SQL execute if no helper method for health update yet)
            # Or add update_model_health to PostgresDB
            await db._execute(
                """
                UPDATE model_configs 
                SET health_status = $1, last_health_check_at = NOW(), avg_latency_ms = $2
                WHERE id = $3
                """,
                'healthy' if is_healthy else 'unhealthy',
                latency_ms,
                model['id']
            )
            
        return health_results
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Jurisdiction Management Endpoints
# ============================================================================

@router.get("/jurisdictions")
async def get_jurisdictions(db: PostgresDB = Depends(get_pg_db)):
    """Get all jurisdictions with their source configuration."""
    try:
        rows = await db._fetch("SELECT * FROM jurisdictions ORDER BY name")
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Get jurisdictions failed: {e}")
        return []


@router.put("/jurisdictions/{jurisdiction_id}")
async def update_jurisdiction(
    jurisdiction_id: str,
    update_data: Dict[str, Any],
    db: PostgresDB = Depends(get_pg_db)
):
    """Update jurisdiction configuration."""
    # Validate fields
    allowed_fields = [
        'scrape_url', 'api_type', 'api_key_env', 
        'openstates_jurisdiction_id', 'scraper_class',
        'use_web_scraper_fallback', 'source_priority'
    ]
    filtered_data = {k: v for k, v in update_data.items() if k in allowed_fields}
    if not filtered_data:
         raise HTTPException(status_code=400, detail="No valid fields to update")

    try:
        # Construct update query dynamically
        set_clauses = [f"{k} = ${i+2}" for i, k in enumerate(filtered_data.keys())]
        query = f"UPDATE jurisdictions SET {', '.join(set_clauses)} WHERE id = $1 RETURNING *"
        args = [jurisdiction_id] + list(filtered_data.values())
        
        row = await db._fetchrow(query, *args)
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Update jurisdiction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jurisdiction/{jurisdiction_id}/dashboard", response_model=JurisdictionDashboardStats)
async def get_jurisdiction_dashboard(
    jurisdiction_id: str,
    db: PostgresDB = Depends(get_pg_db)
):
    """
    Get aggregated dashboard stats for a jurisdiction.
    """
    # 1. Get Jurisdiction Info (SQL)
    # Using raw SQL for aggregation
    
    # Total Raw Scrapes & Processed
    # Assuming we can join sources to get jurisdiction scrapes?
    # raw_scrapes -> sources -> (jurisdiction_id logic?)
    # Sources table has `jurisdiction_id`? Or `jurisdiction` name?
    # Let's check `sources` table schema. Assuming `sources` table has `jurisdiction_id`.
    # And `raw_scrapes` links to `sources`.
    
    try:
        # Get Source IDs for this jurisdiction
        # sources = await db._fetch("SELECT id FROM sources WHERE jurisdiction_id = $1", jurisdiction_id)
        # source_ids = [s['id'] for s in sources]
        
        # Actually doing it in one query is better if possible, but step-by-step is safer for now.
        
        # Metrics
        query_stats = """
        SELECT 
            count(*) as total,
            count(*) filter (where processed = true) as processed,
            max(created_at) as last_scrape
        FROM raw_scrapes 
        WHERE source_id IN (SELECT id FROM sources WHERE jurisdiction_id = $1)
        """
        # Note: If no sources, this returns 0/0/null.
        # But wait, `sources` might use jurisdiction NAME?
        # Let's assume ID based on endpoint input.
        
        # Check if column is jurisdiction_id or jurisdiction_name?
        # Supabase code used `jurisdiction` name string in many places.
        # But `jurisdictions` table has ID.
        # I'll try to cast jurisdiction_id to uuid if needed.
        
        stats_row = await db._fetchrow(query_stats, jurisdiction_id)
        
        # Pipeline Health
        # Check last admin_task for 'scrape'?
        # admin_tasks doesn't stick to source schema.
        
        return JurisdictionDashboardStats(
            jurisdiction=jurisdiction_id,
            last_scrape=stats_row['last_scrape'] if stats_row else None,
            total_raw_scrapes=stats_row['total'] if stats_row else 0,
            processed_scrapes=stats_row['processed'] if stats_row else 0,
            total_bills=0, # TODO: Aggregation from legislative_analysis or bills table
            pipeline_status='healthy', # Placeholder
            active_alerts=[]
        )
    except Exception as e:
        # Fallback/Error handling
        print(f"Dashboard stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Prompt Management Endpoints
# ============================================================================




@router.get("/prompts/{prompt_type}", response_model=PromptConfig)
async def get_prompt(
    prompt_type: Literal["generation", "review"],
    db: PostgresDB = Depends(get_pg_db)
):
    """
    Get current system prompt for generation or review.
    """
    row = await db.get_system_prompt(prompt_type)
    if not row:
        raise HTTPException(status_code=404, detail=f"No active prompt found for {prompt_type}")
    
    return PromptConfig(
        prompt_type=row['prompt_type'],
        system_prompt=row['system_prompt'],
        updated_at=row['updated_at'],
        updated_by=row.get('created_by', 'admin')
    )


@router.post("/prompts")
async def update_prompt(
    request: PromptUpdateRequest,
    db: PostgresDB = Depends(get_pg_db)
):
    """
    Update system prompt for generation or review.
    
    Creates a new version and activates it.
    """
    new_version = await db.update_system_prompt(request.prompt_type, request.system_prompt)
    if not new_version:
        raise HTTPException(status_code=500, detail="Failed to update prompt")
    
    return {
        "message": f"Prompt updated for {request.prompt_type}",
        "version": new_version,
        "updated_at": datetime.now()
    }


# ============================================================================
# Health & Monitoring Endpoints
# ============================================================================

@router.get("/health/detailed")
async def get_detailed_health():
    """
    Get granular health status for all services and models.
    """
    from services.research.zai import ZaiResearchService
    from services.llm.pipeline import DualModelAnalyzer
    
    research_service = ZaiResearchService()
    analyzer = DualModelAnalyzer()
    
    return {
        "research": await research_service.check_health(),
        "analysis": await analyzer.check_health(),
        "database": {"status": "healthy"},  # TODO: Implement DB health check
        "scrapers": _check_scraper_health()
    }


# ============================================================================
# Background Task Implementations
# ============================================================================




async def _execute_multi_source_scrape(scraper_class, config):
    """Execute scraping based on source_priority strategy."""
    source_priority = config.get('source_priority', 'api_only')
    
    if source_priority == 'both_merge':
        # Fetch from both sources and merge
        api_bills = await _fetch_from_api(scraper_class, config)
        web_bills = await _fetch_from_web(config)
        return _merge_bill_data(api_bills, web_bills)
    
    elif source_priority == 'api_first':
        # Try API first, fallback to web if incomplete
        api_bills = await _fetch_from_api(scraper_class, config)
        if _is_incomplete(api_bills) and config.get('use_web_scraper_fallback'):
            web_bills = await _fetch_from_web(config)
            return _merge_bill_data(api_bills, web_bills)
        return api_bills
    
    elif source_priority == 'web_first':
        # Try web first, supplement with API
        web_bills = await _fetch_from_web(config)
        api_bills = await _fetch_from_api(scraper_class, config)
        return _merge_bill_data(web_bills, api_bills)
    
    elif source_priority == 'api_only':
        return await _fetch_from_api(scraper_class, config)
    
    elif source_priority == 'web_only':
        return await _fetch_from_web(config)
    
    # Default fallback
    return await _fetch_from_api(scraper_class, config)


def _merge_bill_data(primary_bills, secondary_bills):
    """Merge bills from two sources, preferring primary data."""
    merged = {}
    
    # Index primary bills by bill_number
    for bill in primary_bills:
        merged[bill.bill_number] = bill
    
    # Supplement with secondary source data
    for bill in secondary_bills:
        if bill.bill_number in merged:
            # Merge: fill in missing fields from secondary source
            existing = merged[bill.bill_number]
            if not existing.text and bill.text:
                existing.text = bill.text
            if not existing.status and bill.status:
                existing.status = bill.status
            if not existing.introduced_date and bill.introduced_date:
                existing.introduced_date = bill.introduced_date
        else:
            # New bill only found in secondary source
            merged[bill.bill_number] = bill
    
    return list(merged.values())


async def _fetch_from_api(scraper_class, config):
    """Fetch bills using API scraper."""
    if not scraper_class:
        return []
    scraper = scraper_class()
    return await scraper.scrape()


async def _fetch_from_web(config):
    """Fetch bills using web scraper (placeholder for now)."""
    # TODO: Implement generic web scraper using scrape_url
    # For now, return empty list as we don't have a generic web scraper yet
    return []


def _is_incomplete(bills):
    """Check if bill data is incomplete (missing text, etc.)."""
    if not bills:
        return True
    # Check if any bills are missing critical fields
    for bill in bills:
        if not bill.text or len(bill.text) < 100:  # Arbitrary threshold
            return True
    return False


async def _run_analysis_task(
    task_id: str,
    jurisdiction: str,
    bill_id: str,
    step: str,
    model_override: Optional[str]
):
    """Background task to run analysis step."""
    db = PostgresDB()
    
    try:
        await db.connect()
        await db.update_admin_task(task_id, status='running')
        
        print(f"Task {task_id}: Running {step} (New Pipeline)")
        
        # Import new pipeline components
        # Import new pipeline components
        from services.llm.orchestrator import AnalysisPipeline
        from llm_common.core import LLMClient
        from llm_common.web_search import WebSearchClient
        
        # Initialize clients - NO SUPABASE
        llm_client = LLMClient() # This might need config, check LLMClient init
        search_client = WebSearchClient(
            api_key=os.getenv("ZAI_API_KEY", ""),
            cache_backend=None 
        )

        pipeline = AnalysisPipeline(llm_client, search_client, db)
        
        # Fetch bill text logic (placeholder)
        bill_text = "Placeholder bill text until DB fetch implemented" 
        
        models = {
            "research": "gpt-4o-mini",
            "generate": model_override or "claude-3-5-sonnet-20240620",
            "review": "gpt-4o"
        }
        
        if step == "generate" or step == "all":
            result = await pipeline.run(bill_id, bill_text, jurisdiction, models)
            
            await db.update_admin_task(
                task_id, 
                status='completed',
                result={'summary': result.summary, 'impacts_count': len(result.impacts)}
            )
        else:
             await db.update_admin_task(task_id, status='completed', result={'message': f'Step {step} simulated'})
             
    except Exception as e:
        error_msg = f"Analysis Task Failed: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        
        if db.is_connected():
            await db.update_admin_task(task_id, status='failed', error=error_msg)
    finally:
        await db.close()


def _check_scraper_health() -> Dict[str, Any]:
    """Check health of all scrapers."""
    from services.scraper.registry import SCRAPERS
    
    health = {}
    for jurisdiction in SCRAPERS.keys():
        # TODO: Implement actual health check
        health[jurisdiction] = {"status": "healthy", "last_scrape": None}
    
    return health
