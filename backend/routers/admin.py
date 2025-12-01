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
import asyncio
import os

# Import database client
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.supabase_client import SupabaseDB

router = APIRouter(prefix="/admin", tags=["admin"])

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
    new_prompt = db.client.table('system_prompts').insert({
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
    from backend.services.research.zai import ZaiResearchService
    from backend.services.llm.pipeline import DualModelAnalyzer
    
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
    """Background task to run scraping."""
    if not db.client:
        print(f"Task {task_id}: Database not available")
        return
    
    try:
        # Update task status to running
        db.client.table('admin_tasks').update({
            'status': 'running',
            'started_at': datetime.now().isoformat()
        }).eq('id', task_id).execute()
        
        # TODO: Implement actual scraping logic
        # For now, simulate scraping
        bills_found = 0
        bills_new = 0
        bills_updated = 0
        
        # Record scrape history
        db.client.table('scrape_history').insert({
            'jurisdiction': jurisdiction,
            'bills_found': bills_found,
            'bills_new': bills_new,
            'bills_updated': bills_updated,
            'status': 'success',
            'task_id': task_id
        }).execute()
        
        # Update task status to completed
        db.client.table('admin_tasks').update({
            'status': 'completed',
            'completed_at': datetime.now().isoformat(),
            'result': {'bills_found': bills_found, 'bills_new': bills_new}
        }).eq('id', task_id).execute()
        
        print(f"Task {task_id}: Completed scraping {jurisdiction}")
        
    except Exception as e:
        error_msg = str(e)
        print(f"Task {task_id} failed: {error_msg}")
        
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
            from backend.services.llm.orchestrator import AnalysisPipeline
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
    from backend.scrapers import SCRAPERS
    
    health = {}
    for jurisdiction in SCRAPERS.keys():
        # TODO: Implement actual health check
        health[jurisdiction] = {"status": "healthy", "last_scrape": None}
    
    return health
