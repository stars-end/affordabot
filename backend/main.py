from fastapi import FastAPI, HTTPException, BackgroundTasks
from services.scraper.saratoga import SaratogaScraper
from services.scraper.san_jose import SanJoseScraper
from services.scraper.santa_clara_county import SantaClaraCountyScraper
from services.scraper.california_state import CaliforniaStateScraper
from services.llm.analyzer import LegislationAnalyzer
from services.notifications.email import EmailNotificationService
from middleware.rate_limit import RateLimiter
from db.supabase_client import SupabaseDB
from typing import Dict, Any
import os
import logging
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

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

app = FastAPI(title="AffordaBot API")
db = SupabaseDB()
email_service = EmailNotificationService()

# Add rate limiting middleware (60 requests/minute per IP)
app.middleware("http")(RateLimiter(requests_per_minute=60))

# Jurisdiction mapping
SCRAPERS = {
    "saratoga": (SaratogaScraper, "city"),
    "san-jose": (SanJoseScraper, "city"),
    "santa-clara-county": (SantaClaraCountyScraper, "county"),
    "california": (CaliforniaStateScraper, "state")
}

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
    return {
        "status": "healthy",
        "database": "connected" if db.client else "disconnected"
    }

async def process_jurisdiction(jurisdiction: str, scraper_class, jur_type: str):
    """Background task to process a single jurisdiction."""
    logger.info(f"Starting scrape for {jurisdiction}")
    
    scraper = scraper_class()
    analyzer = LegislationAnalyzer()
    
    try:
        # 1. Scrape legislation
        bills = await scraper.scrape()
        logger.info(f"{jurisdiction}: Found {len(bills)} bills")
        
        if not bills:
            return {"jurisdiction": jurisdiction, "status": "no bills"}
        
        # 2. Get or create jurisdiction in DB
        jurisdiction_id = await db.get_or_create_jurisdiction(
            name=scraper.jurisdiction_name,
            type=jur_type
        )
        
        processed = 0
        
        # 3. Process each bill (limit to 3 for cost control)
        for bill in bills[:3]:
            try:
                # Store legislation
                legislation_id = await db.store_legislation(
                    jurisdiction_id=jurisdiction_id,
                    bill_data={
                        "bill_number": bill.bill_number,
                        "title": bill.title,
                        "text": bill.text,
                        "introduced_date": bill.introduced_date.isoformat() if bill.introduced_date else None,
                        "status": bill.status,
                        "raw_html": bill.raw_html
                    }
                ) if jurisdiction_id else None
                
                # Analyze with LLM
                analysis = await analyzer.analyze(
                    bill_text=bill.text,
                    bill_number=bill.bill_number,
                    jurisdiction=scraper.jurisdiction_name
                )
                
                # Store impacts
                if legislation_id and analysis.impacts:
                    await db.store_impacts(
                        legislation_id=legislation_id,
                        impacts=[impact.dict() for impact in analysis.impacts]
                    )
                    
                    # Send email notification for high-impact bills (>$500/year)
                    if analysis.total_impact_p50 > 500:
                        # TODO: Get subscriber emails from database
                        # For now, log that we would send an email
                        logger.info(f"High-impact bill detected: {bill.bill_number} (${analysis.total_impact_p50:,.0f}/year)")
                        # await email_service.send_high_impact_alert(
                        #     to_email="subscriber@example.com",
                        #     jurisdiction=scraper.jurisdiction_name,
                        #     bill_number=bill.bill_number,
                        #     bill_title=bill.title,
                        #     total_impact=analysis.total_impact_p50,
                        #     impacts=[impact.dict() for impact in analysis.impacts]
                        # )
                
                processed += 1
                logger.info(f"{jurisdiction}: Processed {bill.bill_number}")
            
            except Exception as e:
                logger.error(f"{jurisdiction}: Error processing {bill.bill_number}: {e}")
        
        return {"jurisdiction": jurisdiction, "processed": processed}
    
    except Exception as e:
        logger.error(f"{jurisdiction}: Scraping failed: {e}")
        return {"jurisdiction": jurisdiction, "error": str(e)}

@app.post("/cron/daily-scrape")
async def daily_scrape(background_tasks: BackgroundTasks):
    """
    Cron endpoint to scrape all jurisdictions daily.
    Triggered by Railway Cron at 6 AM PT.
    """
    logger.info("Starting daily scrape for all jurisdictions")
    
    results = []
    for jurisdiction, (scraper_class, jur_type) in SCRAPERS.items():
        # Run in background to avoid timeout
        background_tasks.add_task(process_jurisdiction, jurisdiction, scraper_class, jur_type)
        results.append({"jurisdiction": jurisdiction, "status": "queued"})
    
    return {
        "status": "success",
        "message": "Daily scrape initiated for all jurisdictions",
        "jurisdictions": results
    }

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
    
    legislation = await db.get_legislation_by_jurisdiction(
        jurisdiction_name=scraper.jurisdiction_name,
        limit=limit
    )
    
    return {
        "jurisdiction": jurisdiction,
        "count": len(legislation),
        "legislation": legislation
    }
