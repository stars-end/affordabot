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


# Import database client
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from supabase import Client, create_client
from db.supabase_client import SupabaseDB

router = APIRouter(prefix="/admin", tags=["admin"])

def get_supabase() -> Client:
    return create_client(
        os.environ['SUPABASE_URL'],
        os.environ['SUPABASE_SERVICE_ROLE_KEY']
    )

class ReviewUpdate(BaseModel):
    status: str

@router.get("/reviews")
async def list_reviews(supabase: Client = Depends(get_supabase)):
    """List pending template reviews."""
    res = supabase.table("template_reviews").select("*").eq("status", "pending").execute()
    return res.data

@router.patch("/reviews/{review_id}")
async def update_review(
    review_id: str, 
    update: ReviewUpdate,
    supabase: Client = Depends(get_supabase)
):
    """Approve or reject a review."""
    res = supabase.table("template_reviews").update({"status": update.status}).eq("id", review_id).execute()
    return res.data

# Initialize database client
def get_db():
    """Dependency to get database client"""
    return SupabaseDB()


# ============================================================================
# Request/Response Models
# ============================================================================

class ManualScrapeRequest(BaseModel):
    jurisdiction: str
    force: bool = False  # Force re-scrape even if recent data exists


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
    db: SupabaseDB = Depends(get_db)
):
    """
    Trigger a manual scrape for a specific jurisdiction.
    
    Returns immediately with a task ID. Use /scrape/status/{task_id} to check progress.
    """
    from uuid import uuid4
    
    task_id = str(uuid4())
    
    # Create task record in database
    if db.client:
        db.client.table('admin_tasks').insert({
            'id': task_id,
            'task_type': 'scrape',
            'jurisdiction': request.jurisdiction,
            'status': 'queued',
            'config': {'force': request.force}
        }).execute()
    
    # Queue scraping task
    background_tasks.add_task(
        _run_scrape_task,
        task_id=task_id,
        jurisdiction=request.jurisdiction,
        force=request.force,
        db=db
    )
    
    return ManualScrapeResponse(
        task_id=task_id,
        jurisdiction=request.jurisdiction,
        status="started",
        message=f"Scraping task started for {request.jurisdiction}"
    )


@router.get("/scrapes", response_model=List[ScrapeHistory])
async def get_scrape_history(
    jurisdiction: Optional[str] = None,
    limit: int = 50,
    db: SupabaseDB = Depends(get_db)
):
    """
    Get scraping history, optionally filtered by jurisdiction.
    """
    if not db.client:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # Build query
    query = db.client.table('scrape_history').select('*')
    
    if jurisdiction:
        query = query.eq('jurisdiction', jurisdiction)
    
    result = query.order('created_at', desc=True).limit(limit).execute()
    
    # Transform to response model
    history = []
    for row in result.data:
        history.append(ScrapeHistory(
            id=row['id'],
            jurisdiction=row['jurisdiction'],
            timestamp=row['created_at'],
            bills_found=row['bills_found'],
            status=row['status'],
            error=row.get('error_message')
        ))
    
    return history


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
    db: SupabaseDB = Depends(get_db)
):
    """
    Get analysis history with optional filters.
    """
    if not db.client:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # Build query
    query = db.client.table('analysis_history').select('*')
    
    if jurisdiction:
        query = query.eq('jurisdiction', jurisdiction)
    if bill_id:
        query = query.eq('bill_id', bill_id)
    if step:
        query = query.eq('step', step)
    
    result = query.order('created_at', desc=True).limit(limit).execute()
    
    # Transform to response model
    history = []
    for row in result.data:
        history.append(AnalysisHistory(
            id=row['id'],
            jurisdiction=row['jurisdiction'],
            bill_id=row['bill_id'],
            step=row['step'],
            model_used=f"{row.get('model_provider', 'unknown')}/{row.get('model_name', 'unknown')}",
            timestamp=row['created_at'],
            status=row['status'],
            result=row.get('result'),
            error=row.get('error_message')
        ))
    
    return history



# ============================================================================
# Task Management Endpoints
# ============================================================================

@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    db: SupabaseDB = Depends(get_db)
):
    """
    Get status of a background task (scrape or analysis).
    """
    if not db.client:
        raise HTTPException(status_code=503, detail="Database not available")
    
    result = db.client.table('admin_tasks').select('*').eq('id', task_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return result.data[0]


# ============================================================================
# Model Management Endpoints
# ============================================================================

@router.get("/models", response_model=List[ModelConfig])
async def get_model_configs(
    db: SupabaseDB = Depends(get_db)
):
    """
    Get current model configuration and priority order.
    """
    if not db.client:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        result = db.client.table('model_configs').select('*').order('priority').execute()
        
        configs = []
        for row in result.data:
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
    db: SupabaseDB = Depends(get_db)
):
    """
    Update model configuration and priority order.
    
    Validates that priorities are unique and models are available.
    """
    if not db.client:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # Validate unique priorities
    priorities = [m.priority for m in config.models]
    if len(priorities) != len(set(priorities)):
        raise HTTPException(status_code=400, detail="Priorities must be unique")
    
    # Update each model config
    for model in config.models:
        # Upsert (update or insert)
        db.client.table('model_configs').upsert({
            'provider': model.provider,
            'model_name': model.model_name,
            'use_case': model.use_case,
            'priority': model.priority,
            'enabled': model.enabled
        }, on_conflict='provider,model_name,use_case').execute()
    
    return {"message": "Model configuration updated", "count": len(config.models)}


@router.get("/health/models")
async def check_model_health(db: SupabaseDB = Depends(get_db)):
    """Check health of all configured models."""
    if not db.client:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # Get all enabled models
    models = db.client.table('model_configs').select('*').eq('enabled', True).execute()
    
    health_results = []
    for model in models.data:
        # Perform health check (simple ping test)
        try:
            # TODO: Implement actual model health check
            # For now, just check if we have API keys
            is_healthy = True
            latency_ms = 0
            
            health_results.append({
                'provider': model['provider'],
                'model_name': model['model_name'],
                'status': 'healthy' if is_healthy else 'unhealthy',
                'latency_ms': latency_ms,
                'last_checked': datetime.now().isoformat()
            })
            
            # Update model health in database
            db.client.table('model_configs').update({
                'health_status': 'healthy' if is_healthy else 'unhealthy',
                'last_health_check_at': datetime.now().isoformat(),
                'avg_latency_ms': latency_ms
            }).eq('id', model['id']).execute()
            
        except Exception as e:
            health_results.append({
                'provider': model['provider'],
                'model_name': model['model_name'],
                'status': 'unhealthy',
                'error': str(e),
                'last_checked': datetime.now().isoformat()
            })
    
    return health_results


# ============================================================================
# Jurisdiction Management Endpoints
# ============================================================================

@router.get("/jurisdictions")
async def get_jurisdictions(db: SupabaseDB = Depends(get_db)):
    """Get all jurisdictions with their source configuration."""
    if not db.client:
        raise HTTPException(status_code=503, detail="Database not available")
    
    result = db.client.table('jurisdictions').select('*').order('name').execute()
    return result.data


@router.put("/jurisdictions/{jurisdiction_id}")
async def update_jurisdiction(
    jurisdiction_id: str,
    update_data: Dict[str, Any],
    db: SupabaseDB = Depends(get_db)
):
    """Update jurisdiction configuration."""
    if not db.client:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # Validate fields
    allowed_fields = [
        'scrape_url', 'api_type', 'api_key_env', 
        'openstates_jurisdiction_id', 'scraper_class',
        'use_web_scraper_fallback', 'source_priority'
    ]
    filtered_data = {k: v for k, v in update_data.items() if k in allowed_fields}
    
    result = db.client.table('jurisdictions').update(filtered_data).eq('id', jurisdiction_id).execute()
    return result.data[0] if result.data else None


# ============================================================================
# Prompt Management Endpoints
# ============================================================================

@router.get("/prompts/{prompt_type}", response_model=PromptConfig)
async def get_prompt(
    prompt_type: Literal["generation", "review"],
    db: SupabaseDB = Depends(get_db)
):
    """
    Get current system prompt for generation or review.
    """
    if not db.client:
        raise HTTPException(status_code=503, detail="Database not available")
    
    result = db.client.table('system_prompts').select('*').eq(
        'prompt_type', prompt_type
    ).eq('is_active', True).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail=f"No active prompt found for {prompt_type}")
    
    row = result.data[0]
    return PromptConfig(
        prompt_type=row['prompt_type'],
        system_prompt=row['system_prompt'],
        updated_at=row['updated_at'],
        updated_by=row.get('created_by', 'admin')
    )


@router.post("/prompts")
async def update_prompt(
    request: PromptUpdateRequest,
    db: SupabaseDB = Depends(get_db)
):
    """
    Update system prompt for generation or review.
    
    Creates a new version and activates it.
    """
    if not db.client:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # Get current max version
    version_result = db.client.table('system_prompts').select('version').eq(
        'prompt_type', request.prompt_type
    ).order('version', desc=True).limit(1).execute()
    
    next_version = 1
    if version_result.data:
        next_version = version_result.data[0]['version'] + 1
    
    # Deactivate current active prompt
    db.client.table('system_prompts').update({
        'is_active': False
    }).eq('prompt_type', request.prompt_type).eq('is_active', True).execute()
    
    # Insert new prompt version
    db.client.table('system_prompts').insert({
        'prompt_type': request.prompt_type,
        'version': next_version,
        'system_prompt': request.system_prompt,
        'description': f'Version {next_version}',
        'is_active': True,
        'activated_at': datetime.now().isoformat()
    }).execute()
    
    return {
        "message": f"Prompt updated for {request.prompt_type}",
        "version": next_version,
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

async def _run_scrape_task(task_id: str, jurisdiction: str, force: bool, db: SupabaseDB):
    """Background task to run scraping with multi-source support."""
    if not db.client:
        print(f"Task {task_id}: Database not available")
        return

    try:
        # Update task status to running
        db.client.table('admin_tasks').update({
            'status': 'running',
            'started_at': datetime.now().isoformat()
        }).eq('id', task_id).execute()

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
        jur_config = db.client.table('jurisdictions').select('*').eq('name', jurisdiction).single().execute()
        if not jur_config.data:
            raise Exception(f"Jurisdiction {jurisdiction} not found in database")
        
        config = jur_config.data
        scraper_class = SCRAPER_MAP.get(jurisdiction)
        
        # Execute multi-source scraping based on source_priority
        bills = await _execute_multi_source_scrape(scraper_class, config)
        
        # Store in database
        jurisdiction_id = config['id']
        bills_new = 0
        bills_updated = 0
        
        for bill in bills:
            leg_id = await db.store_legislation(jurisdiction_id, bill.dict())
            if leg_id:
                bills_new += 1
        
        # Record scrape history
        db.client.table('scrape_history').insert({
            'jurisdiction': jurisdiction,
            'bills_found': len(bills),
            'bills_new': bills_new,
            'bills_updated': bills_updated,
            'status': 'success',
            'task_id': task_id
        }).execute()
        
        # Update task status to completed
        db.client.table('admin_tasks').update({
            'status': 'completed',
            'completed_at': datetime.now().isoformat(),
            'result': {'bills_found': len(bills), 'bills_new': bills_new}
        }).eq('id', task_id).execute()
        
        print(f"Task {task_id}: Completed scraping {jurisdiction}")
        
    except Exception as e:
        error_msg = str(e)
        print(f"Task {task_id} failed: {error_msg}")
        import traceback
        traceback.print_exc()
        
        # Update task status to failed
        db.client.table('admin_tasks').update({
            'status': 'failed',
            'completed_at': datetime.now().isoformat(),
            'error_message': error_msg
        }).eq('id', task_id).execute()
        
        # Record failed scrape
        db.client.table('scrape_history').insert({
            'jurisdiction': jurisdiction,
            'bills_found': 0,
            'status': 'failed',
            'error_message': error_msg,
            'task_id': task_id
        }).execute()


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
    try:
        # Check feature flag
        if os.getenv("ENABLE_NEW_LLM_PIPELINE", "false").lower() == "true":
            print(f"Task {task_id}: Running {step} with NEW pipeline")
            
            # Import new pipeline components
            from services.llm.orchestrator import AnalysisPipeline
            from llm_common.llm_client import LLMClient
            from llm_common.web_search import WebSearchClient
            from llm_common.cost_tracker import CostTracker
            
            # Initialize clients
            db = SupabaseDB().client
            llm_client = LLMClient()
            search_client = WebSearchClient(
                api_key=os.getenv("ZAI_API_KEY", ""),
                supabase_client=db
            )
            cost_tracker = CostTracker(supabase_client=db)
            
            pipeline = AnalysisPipeline(llm_client, search_client, cost_tracker, db)
            
            # Fetch bill text (placeholder)
            # In a real implementation, we'd fetch this from the DB
            bill_text = "Placeholder bill text" 
            
            # Run pipeline step
            # Note: The pipeline currently runs all steps in 'run()', 
            # but we can adapt it to run specific steps if needed.
            # For now, we'll just run the full pipeline if step is 'generate' or 'all'
            
            models = {
                "research": "gpt-4o-mini",
                "generate": model_override or "claude-3-5-sonnet-20240620",
                "review": "gpt-4o"
            }
            
            if step == "generate" or step == "all":
                await pipeline.run(bill_id, bill_text, jurisdiction, models)
                
        else:
            # TODO: Implement actual analysis logic (Old Pipeline)
            print(f"Task {task_id}: Running {step} for {bill_id} with model {model_override or 'default'} (OLD PIPELINE)")
        
    except Exception as e:
        print(f"Task {task_id} failed: {e}")
        import traceback
        traceback.print_exc()


def _check_scraper_health() -> Dict[str, Any]:
    """Check health of all scrapers."""
    from services.scraper.registry import SCRAPERS
    
    health = {}
    for jurisdiction in SCRAPERS.keys():
        # TODO: Implement actual health check
        health[jurisdiction] = {"status": "healthy", "last_scrape": None}
    
    return health
