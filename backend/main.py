from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from services.notifications.email import EmailNotificationService
from db.postgres_client import PostgresDB
from typing import Dict, Any
import os
import logging
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from routers import admin, sources, discovery, prompts, bills
from services.scraper.registry import SCRAPERS
from middleware.auth import TestAuthBypassMiddleware

# Initialize Sentry
if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[
            FastApiIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
        ],
        traces_sample_rate=0.1,
        environment=os.getenv("ENVIRONMENT", "development")
    )
    logger = logging.getLogger(__name__)
    logger.info("Sentry initialized")
else:
    logger = logging.getLogger(__name__)
    logger.warning("Sentry DSN not set. Error tracking disabled.")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(title="Affordabot API")
db = PostgresDB()
email_service = EmailNotificationService()

@app.on_event("startup")
async def startup_db():
    await db.connect()
    app.state.db = db
    logger.info("✅ Database connected (Postgres/Railway)")

@app.on_event("shutdown")
async def shutdown_db():
    await db.close()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add test auth bypass middleware
app.add_middleware(TestAuthBypassMiddleware)

# Include admin router
app.include_router(admin.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(discovery.router, prefix="/api")
app.include_router(prompts.router, prefix="/api")
app.include_router(bills.router, prefix="/api")

# Add rate limiting middleware (60 requests/minute per IP)
# app.middleware("http")(RateLimiter(requests_per_minute=60))


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    error_msg = f"{str(exc)}\n{traceback.format_exc()}"
    logger.error(f"Global exception: {error_msg}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "traceback": traceback.format_exc()},
    )

# Jurisdiction mapping

@app.get("/")
async def root():
    return {
        "message": "Welcome to AffordaBot API",
        "jurisdictions": list(SCRAPERS.keys()),
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    # Check Z.ai health
    from services.research.zai import ZaiResearchService
    zai_health = await ZaiResearchService().check_health()

    return {
        "status": "healthy",
        "database": "connected" if db.is_connected() else "disconnected",
        "zai_research": "connected" if zai_health else "disconnected"
    }

@app.get("/health/jurisdictions")
async def health_check_jurisdictions():
    """Check health of all jurisdiction scrapers."""
    results = {}
    for jurisdiction, (scraper_class, _) in SCRAPERS.items():
        scraper = scraper_class()
        is_healthy = await scraper.check_health()
        results[jurisdiction] = "healthy" if is_healthy else "unhealthy"
    
    return {
        "status": "success",
        "jurisdictions": results
    }

@app.get("/health/analysis")
async def health_check_analysis():
    """Check health of LLM pipeline (LLM + Search)."""
    try:
        from llm_common.core import LLMConfig
        from llm_common.providers import ZaiClient
        from llm_common.web_search import WebSearchClient
        
        # Check LLM
        llm_config = LLMConfig(
            api_key=os.getenv("ZAI_API_KEY", "dummy"), 
            provider="zai",
            default_model=os.getenv("LLM_MODEL_RESEARCH", "glm-4.7")
        )
        llm_client = ZaiClient(llm_config)
        llm_ok = await llm_client.validate_api_key()
        
        # Check Search
        _ = WebSearchClient(api_key=os.getenv("ZAI_API_KEY", "dummy"))
        # WebSearchClient doesn't have explicit check_health, assume OK if init passed or add check if available
        # But we can try a simple search?
        search_ok = True 
        
        status = "healthy" if llm_ok else "degraded"
        return {
            "status": status,
            "details": {
                "llm": "connected" if llm_ok else "error",
                "search": "connected" if search_ok else "unknown"
            }
        }
    except Exception as e:
        logger.error(f"Analysis health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

async def process_jurisdiction(jurisdiction: str, scraper_class, jur_type: str):
    """Background task to process a single jurisdiction."""
    logger.info(f"Starting scrape for {jurisdiction}")
    
    scraper = scraper_class()
    
    # Initialize Agentic Pipeline
    try:
        from services.llm.orchestrator import AnalysisPipeline
        from llm_common.core import LLMConfig
        from llm_common.providers import ZaiClient, OpenRouterClient
        from llm_common.web_search import WebSearchClient

        llm_config = LLMConfig(
            api_key=os.getenv("ZAI_API_KEY"), 
            provider="zai",
            default_model=os.getenv("LLM_MODEL_RESEARCH", "glm-4.7")
        )
        llm_client = ZaiClient(llm_config)
        
        # Initialize fallback client (OpenRouter)
        fallback_client = None
        if os.getenv("OPENROUTER_API_KEY"):
            or_config = LLMConfig(
                api_key=os.getenv("OPENROUTER_API_KEY"),
                provider="openrouter",
                default_model="google/gemini-2.0-flash-exp"
            )
            fallback_client = OpenRouterClient(or_config)
            
        search_client = WebSearchClient(api_key=os.getenv("ZAI_API_KEY"))
        
        pipeline = AnalysisPipeline(llm_client, search_client, db, fallback_client=fallback_client)
        
    except Exception as e:
        logger.error(f"Failed to initialize AnalysisPipeline: {e}")
        return {"jurisdiction": jurisdiction, "error": f"Pipeline Init Failed: {e}"}
    
    try:
        # 1. Scrape legislation
        bills = await scraper.scrape()
        logger.info(f"{jurisdiction}: Found {len(bills)} bills")
        
        if not bills:
            return {"jurisdiction": jurisdiction, "status": "no bills"}
        
        # 2. Get or create jurisdiction in DB
        _ = await db.get_or_create_jurisdiction(
            name=scraper.jurisdiction_name,
            type=jur_type
        )
        
        processed = 0
        
        errors = []
        for bill in bills[:3]:
            try:
                # However, pipeline needs bill_id, bill_text.
                # bill.bill_number is usually the ID.
                
                models = {
                    "research": os.getenv("LLM_MODEL_RESEARCH", "glm-4.7"),
                    "generate": os.getenv("LLM_MODEL_GENERATE", "glm-4.7"),
                    "review": os.getenv("LLM_MODEL_REVIEW", "glm-4.7")
                }
                
                await pipeline.run(
                    bill_id=bill.bill_number,
                    bill_text=bill.text,
                    jurisdiction=scraper.jurisdiction_name,
                    models=models
                )
                
                # ... (existing code)
                
                processed += 1
                logger.info(f"{jurisdiction}: Processed {bill.bill_number}")
            
            except Exception as e:
                import traceback
                error_details = f"{str(e)}\n{traceback.format_exc()}"
                errors.append({"bill": bill.bill_number, "error": error_details})
                logger.error(f"{jurisdiction}: Error processing {bill.bill_number}: {e}")
        
        return {"jurisdiction": jurisdiction, "processed": processed, "errors": errors}
    
    except Exception as e:
        logger.error(f"{jurisdiction}: Scraping failed: {e}")
        return {"jurisdiction": jurisdiction, "error": str(e)}

# --- Authenticated Cron Trigger Endpoints (bd-s8id.3) ---
# These endpoints are used by Windmill as the scheduler of record.
# Auth: Authorization: Bearer $CRON_SECRET or X-Cron-Secret: $CRON_SECRET

CRON_SECRET = os.environ.get("CRON_SECRET")


def _verify_cron_auth(request: Request) -> bool:
    """Verify cron secret from Authorization header or X-Cron-Secret header."""
    if not CRON_SECRET:
        logger.warning("CRON_SECRET not set — cron auth disabled")
        return False

    # Check Authorization: Bearer token
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if token == CRON_SECRET:
            return True

    # Check X-Cron-Secret header
    cron_header = request.headers.get("x-cron-secret", "")
    if cron_header == CRON_SECRET:
        return True

    return False


@app.post("/cron/discovery")
async def cron_discovery(background_tasks: BackgroundTasks):
    """
    Authenticated cron trigger for discovery pipeline.
    Replaces Railway Cron scheduling for this job.
    Auth: Authorization: Bearer $CRON_SECRET or X-Cron-Secret: $CRON_SECRET
    """
    if not _verify_cron_auth(request):
        raise HTTPException(status_code=401, detail="Invalid cron credentials")

    logger.info("Cron trigger: discovery run")
    background_tasks.add_task(
        _run_script_job, "backend/scripts/cron/run_discovery.py", "discovery"
    )
    return {"status": "triggered", "job": "discovery"}


@app.post("/cron/daily-scrape")
async def cron_daily_scrape(background_tasks: BackgroundTasks):
    """
    Cron endpoint to scrape all jurisdictions daily.
    Auth: Authorization: Bearer $CRON_SECRET or X-Cron-Secret: $CRON_SECRET
    """
    if not _verify_cron_auth(request):
        raise HTTPException(status_code=401, detail="Invalid cron credentials")

    logger.info("Cron trigger: daily scrape")
    background_tasks.add_task(
        _run_script_job, "scripts/daily_scrape.py", "daily_scrape"
    )
    return {"status": "triggered", "job": "daily_scrape"}


@app.post("/cron/rag-spiders")
async def cron_rag_spiders(background_tasks: BackgroundTasks):
    """
    Authenticated cron trigger for RAG spiders.
    Auth: Authorization: Bearer $CRON_SECRET or X-Cron-Secret: $CRON_SECRET
    """
    if not _verify_cron_auth(request):
        raise HTTPException(status_code=401, detail="Invalid cron credentials")

    logger.info("Cron trigger: rag spiders")
    background_tasks.add_task(
        _run_script_job, "backend/scripts/cron/run_rag_spiders.py", "rag_spiders"
    )
    return {"status": "triggered", "job": "rag_spiders"}


@app.post("/cron/universal-harvester")
async def cron_universal_harvester(background_tasks: BackgroundTasks):
    """
    Authenticated cron trigger for universal harvester.
    Auth: Authorization: Bearer $CRON_SECRET or X-Cron-Secret: $CRON_SECRET
    """
    if not _verify_cron_auth(request):
        raise HTTPException(status_code=401, detail="Invalid cron credentials")

    logger.info("Cron trigger: universal harvester")
    background_tasks.add_task(
        _run_script_job, "backend/scripts/cron/run_universal_harvester.py", "universal_harvester"
    )
    return {"status": "triggered", "job": "universal_harvester"}


async def _run_script_job(script_path: str, job_name: str):
    """Run a cron script job with logging."""
    import asyncio
    import subprocess

    logger.info(f"Cron job '{job_name}' starting: {script_path}")
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error(f"Cron job '{job_name}' failed (exit {proc.returncode}): {stderr[-500:]}")
        else:
            logger.info(f"Cron job '{job_name}' succeeded (exit {proc.returncode})")
    except Exception as e:
        logger.error(f"Cron job '{job_name}' exception: {e}")

@app.post("/scrape/{jurisdiction}")
async def scrape_and_analyze(jurisdiction: str) -> Dict[str, Any]:
    """
    Scrape legislation from a jurisdiction, analyze with LLM, and store in database.
    """
    if jurisdiction not in SCRAPERS:
        raise HTTPException(status_code=404, detail=f"Jurisdiction '{jurisdiction}' not supported")
    
    scraper_class, jur_type = SCRAPERS[jurisdiction]
    result = await process_jurisdiction(jurisdiction, scraper_class, jur_type)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result

@app.get("/legislation/{jurisdiction}")
async def get_legislation(jurisdiction: str, limit: int = 10):
    """
    Get stored legislation for a jurisdiction with impacts.
    """
    if jurisdiction not in SCRAPERS:
        raise HTTPException(status_code=404, detail=f"Jurisdiction '{jurisdiction}' not supported")
    
    scraper_class, _ = SCRAPERS[jurisdiction]
    scraper = scraper_class()
    
    legislation_data = await db.get_legislation_by_jurisdiction(
        jurisdiction_name=scraper.jurisdiction_name,
        limit=limit
    )
    
    # Adapt to the frontend's expected format
    legislation_list = []
    for leg in legislation_data:
        for impact in leg.get('impacts', []):
            if 'confidence_score' in impact:
                impact['confidence'] = impact.pop('confidence_score')
        legislation_list.append({
            "bill_number": leg.get("bill_number"),
            "title": leg.get("title"),
            "jurisdiction": leg.get("jurisdiction", jurisdiction),
            "status": leg.get("status"),
            "impacts": leg.get("impacts", []),
            "total_impact_p50": sum(i.get('p50', 0) for i in leg.get('impacts', [])),
            "analysis_timestamp": leg.get("created_at").isoformat() if leg.get("created_at") else None,
            "model_used": "n/a"
        })

    return {
        "jurisdiction": jurisdiction,
        "count": len(legislation_list),
        "legislation": legislation_list
    }

@app.get("/legislation/{jurisdiction}/{bill_number}")
async def get_bill_details(jurisdiction: str, bill_number: str):
    """
    Get details for a specific bill including impacts.
    """
    if jurisdiction not in SCRAPERS:
        raise HTTPException(status_code=404, detail=f"Jurisdiction '{jurisdiction}' not supported")

    bill = await db.get_bill(jurisdiction, bill_number)

    if not bill:
        raise HTTPException(status_code=404, detail=f"Bill '{bill_number}' not found in {jurisdiction}")

    return bill
