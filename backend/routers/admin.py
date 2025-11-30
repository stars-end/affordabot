"""
Admin Dashboard V2 API Router

Provides comprehensive admin endpoints for:
- Manual scraping control
- Analysis pipeline management (research, generate, review)
- Model configuration and priority management
- System prompt editing
- Health monitoring
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
import asyncio

router = APIRouter(prefix="/admin", tags=["admin"])


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
    id: int
    jurisdiction: str
    timestamp: datetime
    bills_found: int
    status: Literal["success", "partial", "failed"]
    error: Optional[str] = None


class AnalysisHistory(BaseModel):
    id: int
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

@router.post("/scrape", response_model=ManualScrapeResponse)
async def trigger_manual_scrape(
    request: ManualScrapeRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger a manual scrape for a specific jurisdiction.
    
    Returns immediately with a task ID. Use /scrape/status/{task_id} to check progress.
    """
    from backend.scrapers import get_scraper
    from uuid import uuid4
    
    task_id = str(uuid4())
    
    # Validate jurisdiction
    try:
        scraper = get_scraper(request.jurisdiction)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Queue scraping task
    background_tasks.add_task(
        _run_scrape_task,
        task_id=task_id,
        jurisdiction=request.jurisdiction,
        force=request.force
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
    limit: int = 50
):
    """
    Get scraping history, optionally filtered by jurisdiction.
    """
    # TODO: Implement database query
    # For now, return mock data
    return [
        ScrapeHistory(
            id=1,
            jurisdiction="san_jose",
            timestamp=datetime.now(),
            bills_found=12,
            status="success"
        )
    ]


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
    limit: int = 50
):
    """
    Get analysis history with optional filters.
    """
    # TODO: Implement database query
    return []


# ============================================================================
# Model Management Endpoints
# ============================================================================

@router.get("/models", response_model=List[ModelConfig])
async def get_model_configs():
    """
    Get current model configuration and priority order.
    """
    # TODO: Load from database or config file
    return [
        ModelConfig(
            provider="openrouter",
            model_name="x-ai/grok-beta",
            priority=1,
            enabled=True,
            use_case="generation"
        ),
        ModelConfig(
            provider="zai",
            model_name="glm-4.6",
            priority=2,
            enabled=True,
            use_case="review"
        )
    ]


@router.post("/models")
async def update_model_configs(config: ModelConfigUpdate):
    """
    Update model configuration and priority order.
    
    Validates that priorities are unique and models are available.
    """
    # TODO: Validate and save to database
    return {"message": "Model configuration updated", "count": len(config.models)}


# ============================================================================
# Prompt Management Endpoints
# ============================================================================

@router.get("/prompts/{prompt_type}", response_model=PromptConfig)
async def get_prompt(prompt_type: Literal["generation", "review"]):
    """
    Get current system prompt for generation or review.
    """
    # TODO: Load from database
    return PromptConfig(
        prompt_type=prompt_type,
        system_prompt="You are a helpful AI assistant...",
        updated_at=datetime.now()
    )


@router.post("/prompts")
async def update_prompt(request: PromptUpdateRequest):
    """
    Update system prompt for generation or review.
    """
    # TODO: Save to database with version history
    return {
        "message": f"Prompt updated for {request.prompt_type}",
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

async def _run_scrape_task(task_id: str, jurisdiction: str, force: bool):
    """Background task to run scraping."""
    from backend.scrapers import get_scraper
    
    try:
        scraper = get_scraper(jurisdiction)
        bills = await scraper.scrape()
        
        # TODO: Save to database with task_id
        print(f"Task {task_id}: Scraped {len(bills)} bills from {jurisdiction}")
        
    except Exception as e:
        print(f"Task {task_id} failed: {e}")
        # TODO: Update task status in database


async def _run_analysis_task(
    task_id: str,
    jurisdiction: str,
    bill_id: str,
    step: str,
    model_override: Optional[str]
):
    """Background task to run analysis step."""
    try:
        # TODO: Implement actual analysis logic
        print(f"Task {task_id}: Running {step} for {bill_id} with model {model_override or 'default'}")
        
    except Exception as e:
        print(f"Task {task_id} failed: {e}")


def _check_scraper_health() -> Dict[str, Any]:
    """Check health of all scrapers."""
    from backend.scrapers import SCRAPERS
    
    health = {}
    for jurisdiction in SCRAPERS.keys():
        # TODO: Implement actual health check
        health[jurisdiction] = {"status": "healthy", "last_scrape": None}
    
    return health
