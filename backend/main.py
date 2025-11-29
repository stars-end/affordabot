from fastapi import FastAPI, HTTPException
from services.scraper.saratoga import SaratogaScraper
from services.scraper.san_jose import SanJoseScraper
from services.scraper.santa_clara_county import SantaClaraCountyScraper
from services.scraper.california_state import CaliforniaStateScraper
from services.llm.analyzer import LegislationAnalyzer
from db.supabase_client import SupabaseDB
from typing import Dict, Any

app = FastAPI(title="AffordaBot API")
db = SupabaseDB()

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
        "jurisdictions": list(SCRAPERS.keys())
    }

@app.post("/scrape/{jurisdiction}")
async def scrape_and_analyze(jurisdiction: str) -> Dict[str, Any]:
    """
    Scrape legislation from a jurisdiction, analyze with LLM, and store in database.
    """
    if jurisdiction not in SCRAPERS:
        raise HTTPException(status_code=404, detail=f"Jurisdiction '{jurisdiction}' not supported")
    
    scraper_class, jur_type = SCRAPERS[jurisdiction]
    scraper = scraper_class()
    analyzer = LegislationAnalyzer()
    
    try:
        # 1. Scrape legislation
        bills = await scraper.scrape()
        
        if not bills:
            return {"status": "no bills found", "jurisdiction": jurisdiction}
        
        # 2. Get or create jurisdiction in DB
        jurisdiction_id = await db.get_or_create_jurisdiction(
            name=scraper.jurisdiction_name,
            type=jur_type
        )
        
        results = []
        
        # 3. Process each bill
        for bill in bills[:3]:  # Limit to 3 bills for MVP to save LLM costs
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
                
                results.append({
                    "bill": bill.dict(),
                    "analysis": analysis.dict(),
                    "stored": legislation_id is not None
                })
            
            except Exception as e:
                print(f"Error processing bill {bill.bill_number}: {e}")
                results.append({
                    "bill": bill.dict(),
                    "error": str(e),
                    "stored": False
                })
        
        return {
            "status": "success",
            "jurisdiction": jurisdiction,
            "bills_processed": len(results),
            "results": results
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

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
